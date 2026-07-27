import re

from constants import (
    PATTERN_RULES,
    COUNTRY_REGION_MAP,
    ALWAYS_MULTIPLE_COMPOUNDS,
    BROAD_IDENTITY_KEYWORDS,
    ORG_NAME_ETHNICITY_MAP,
    OTHER_ETHNIC,
    INDIGENOUS_L1,
    NON_ETHNIC_SENSE_BEFORE_PATTERNS,
    BYZANTINE_FESTIVAL_AFTER_PATTERN,
)
from ethnic_taggerv3 import (infer_role, indigenous_topic_keep_role, matches_any,
                             SELF_ID_ROLE, is_served_role)

"""
extractors.py
-------------
Signal Extraction Layer — Layer 1 of the 3-layer classification pipeline.

Responsibility:
    Detect the PRESENCE of ethnic signals in text, and tag each with an
    evidence role: 'served' (strong, default) or a
    weak role ('org_name' | 'provider' | 'example' | 'aspirational' |
    'negated') inferred from the text immediately around the match.

Constraint:
    NO filtering or suppression — every match becomes a candidate
    regardless of role. Deciding what to do with a weak-role candidate
    is the resolver's responsibility (Layer 3), not this layer's.

NOTE on imports:
    Constants (PATTERN_RULES, COUNTRY_REGION_MAP, etc.) currently live in
    ethnic_taggerv3.py. When ethnic_taggerv3.py is wired to import this
    module, those constants must move to a shared constants.py to break
    the circular dependency. That refactor is deferred until the resolver
    layer is implemented.
"""

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

ROLE_CONTEXT_WINDOW = 60

def _candidate(level1: str, level2: str, level3: str, depth: int, source: str,
               role: str = "served", span: str = "", context: str = "") -> dict:
    # SELF_ID_ROLE is normalized back to plain "served" here, with the
    # provenance kept as a separate flag. Every consumer that asks
    # role == "served" (resolver.dedup, classify_row's corroboration gate,
    # identity_markers, the ML arbiter) therefore keeps working unchanged,
    # while classify_row can still tell that a row's ONLY served evidence was
    # the organization naming itself -- and flag it accordingly.
    self_id = (role == SELF_ID_ROLE)
    if self_id:
        role = "served"
    return {
        "level1": level1,
        "level2": level2,
        "level3": level3,
        "depth":  depth,
        "source": source,
        "role":   role,
        "self_id": self_id,
        # span/context: the matched text and its local window, kept so the
        # ML role arbiter can re-score this exact
        # occurrence later without re-running extraction. Empty for
        # org_lookup candidates (not span-anchored, see extract_org_candidates).
        "span":    span,
        "context": context,
    }

def _local_context(text: str, start: int, end: int, window: int = ROLE_CONTEXT_WINDOW) -> str:
    return text[max(0, start - window):end + window]

# ---------------------------------------------------------------------------
# Public extraction functions
# ---------------------------------------------------------------------------

def extract_taxonomy_candidates(text: str, taxonomy_entries: list, name_text: str = "") -> list:
    """
    Cases 1-3: raw taxonomy keyword presence scan.

    Returns one candidate per OCCURRENCE of a matching keyword (not just
    per keyword), each tagged with its evidence role, so a group mentioned
    both as served population and, elsewhere, as an org name/provider still
    keeps its "served" candidate (see resolver.dedup — it prefers "served"
    when collapsing duplicates). The trailing s? handles common plural
    forms (Somalis, Africans) without a separate entry per variant.

    No negation or example-mention FILTERING is applied here — negated/
    example-role candidates are still returned, weak-tagged.
    """
    candidates = []
    for entry in taxonomy_entries:
        kw = entry["keyword"]
        if not kw:
            continue
        pattern = re.compile(r'\b' + re.escape(kw) + r's?\b', re.IGNORECASE)
        non_ethnic_before = NON_ETHNIC_SENSE_BEFORE_PATTERNS.get(kw)
        for m in pattern.finditer(text):
            # A spurious non-ethnic sense of this exact
            # keyword ("final polish" on a video edit, not the Polish
            # people) is skipped entirely at this occurrence: there is no
            # ethnic claim here at all, so it must not even become a weak
            # candidate (which would still surface a "verify" note).
            if non_ethnic_before and matches_any(non_ethnic_before, text[max(0, m.start() - 20):m.start()]):
                continue
            role = infer_role(text, m.start(), m.end(), name_text)
            if is_served_role(role) and entry["level1"] == INDIGENOUS_L1:
                role = indigenous_topic_keep_role(text, m.start(), m.end()) or role
            candidates.append(_candidate(
                entry["level1"],
                entry["level2"] or "",
                entry["level3"] or "",
                entry["depth"],
                "taxonomy",
                role,
                span=m.group(0),
                context=_local_context(text, m.start(), m.end()),
            ))
    return candidates

def extract_pattern_candidates(text: str, name_text: str = "") -> list:
    """
    Case 4: structured/directional phrase scan.

    Scans ALL PATTERN_RULES and returns a candidate per OCCURRENCE of every
    matching pattern (not just the first) — deduplication/role-rescue and
    priority are the resolver's responsibility (resolver.dedup prefers a
    "served" occurrence over a weak one for the same outcome).

    No negation filtering is applied here.
    """
    candidates = []
    for pattern, l1, l2, l3 in PATTERN_RULES:
        depth = 3 if l3 else (2 if l2 else 1)
        for m in re.finditer(pattern, text, re.IGNORECASE):
            role = infer_role(text, m.start(), m.end(), name_text)
            if is_served_role(role) and l1 == INDIGENOUS_L1:
                role = indigenous_topic_keep_role(text, m.start(), m.end()) or role
            candidates.append(_candidate(
                l1, l2, l3, depth, "pattern", role,
                span=m.group(0),
                context=_local_context(text, m.start(), m.end()),
            ))
    return candidates

def extract_country_candidates(text: str, name_text: str = "") -> list:
    """
    Cases 6 & 7: nationality and 'from <country>' phrase scan.

    Checks both the bare demonym form (Jamaicans) and the prepositional
    form (from Jamaica) for every entry in COUNTRY_REGION_MAP, returning a
    candidate per occurrence (deduplication/role-rescue is the resolver's
    responsibility).

    No negation filtering is applied here.
    """
    candidates = []
    for country, (l1, l2, l3) in COUNTRY_REGION_MAP.items():
        depth = 3 if l3 else (2 if l2 else 1)
        pattern = r'\b(?:' + re.escape(country) + r's?|from\s+' + re.escape(country) + r's?)\b'
        for m in re.finditer(pattern, text, re.IGNORECASE):
            role = infer_role(text, m.start(), m.end(), name_text)
            candidates.append(_candidate(
                l1, l2, l3, depth, "country", role,
                span=m.group(0),
                context=_local_context(text, m.start(), m.end()),
            ))
    return candidates

def extract_compound_candidates(text: str, name_text: str = "") -> list:
    """
    Afro-Caribbean / Afro-Latino compound identity scan.

    Each matched compound pattern expands into two candidates — one per
    component L1 group — so they combine into Multiple the same way two
    separately mentioned groups would.
    """
    candidates = []
    for compound_pattern, group_tuples in ALWAYS_MULTIPLE_COMPOUNDS.items():
        m = re.search(compound_pattern, text, re.IGNORECASE)
        if m:
            role = infer_role(text, m.start(), m.end(), name_text)
            # "byzantine" is the one ALWAYS_MULTIPLE_COMPOUNDS entry naming a
            # historical/defunct civilization with no living modern
            # population; "Byzantine ... Festival" is reliably a themed/branded
            # event name (e.g. a "Byzantine Winter Festival"), not a
            # served-population claim.
            # Scoped to this one compound (not a generic frame — see
            # BYZANTINE_FESTIVAL_AFTER_PATTERN's constants.py docstring) so a
            # real ethnocultural org's own "[Ethnicity] ... Festival" (e.g.
            # "Ukrainian Dance Festival") is untouched.
            if is_served_role(role) and m.group(0).lower() == "byzantine":
                after = text[m.end():m.end() + 60]
                if matches_any([BYZANTINE_FESTIVAL_AFTER_PATTERN], after):
                    role = "topic"
            span = m.group(0)
            context = _local_context(text, m.start(), m.end())
            for l1, l2, l3 in group_tuples:
                candidates.append(_candidate(l1, l2, l3, 1, "compound", role, span=span, context=context))
    return candidates

def extract_broad_identity_candidates(text: str, name_text: str = "") -> list:
    """
    Case 9b: broad identity label scan (mixed heritage, multiracial, etc.).

    Returns a single OTHER_ETHNIC candidate if any keyword is matched.
    Only one candidate is produced regardless of how many keywords match,
    because all keywords in this list map to the same classification outcome.
    """
    for kw_pattern in BROAD_IDENTITY_KEYWORDS:
        m = re.search(kw_pattern, text, re.IGNORECASE)
        if m:
            role = infer_role(text, m.start(), m.end(), name_text)
            return [_candidate(
                OTHER_ETHNIC, "", "", 1, "broad_identity", role,
                span=m.group(0),
                context=_local_context(text, m.start(), m.end()),
            )]
    return []

def extract_org_candidates(text: str) -> list:
    """
    Case 10: known organization name scan.

    Checks ORG_NAME_ETHNICITY_MAP against the full text. Returns all
    matching entries. A map value may be a single (L1, L2, L3) tuple, or a
    list of tuples for an org whose curated fallback spans more than one
    group (e.g. "Council of Canadians of African and Caribbean Heritage" ->
    African + Caribbean, which the resolver's distinct-L1 check turns into
    Multiple).

    Not role-tagged: a known-org match is always treated as a definitive
    last-resort lookup by the resolver, independent of served/weak tiering.
    """
    candidates = []
    for org_name, mapping in ORG_NAME_ETHNICITY_MAP.items():
        if not re.search(r'\b' + re.escape(org_name) + r'\b', text, re.IGNORECASE):
            continue
        tuples = mapping if isinstance(mapping, list) else [mapping]
        for l1, l2, l3 in tuples:
            depth = 3 if l3 else (2 if l2 else 1)
            candidates.append(_candidate(l1, l2, l3, depth, "org_lookup"))
    return candidates
