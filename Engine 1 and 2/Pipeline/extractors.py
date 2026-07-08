import re

from constants import (
    PATTERN_RULES,
    COUNTRY_REGION_MAP,
    ALWAYS_MULTIPLE_COMPOUNDS,
    BROAD_IDENTITY_KEYWORDS,
    ORG_NAME_ETHNICITY_MAP,
    OTHER_ETHNIC,
)
from ethnic_taggerv3 import infer_role

"""
extractors.py
-------------
Signal Extraction Layer — Layer 1 of the 3-layer classification pipeline.

Responsibility:
    Detect the PRESENCE of ethnic signals in text, and tag each with an
    evidence role (Plan.md Fix 1 Phase 2): 'served' (strong, default) or a
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

def _candidate(level1: str, level2: str, level3: str, depth: int, source: str,
               role: str = "served") -> dict:
    return {
        "level1": level1,
        "level2": level2,
        "level3": level3,
        "depth":  depth,
        "source": source,
        "role":   role,
    }

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
        for m in pattern.finditer(text):
            role = infer_role(text, m.start(), m.end(), name_text)
            candidates.append(_candidate(
                entry["level1"],
                entry["level2"] or "",
                entry["level3"] or "",
                entry["depth"],
                "taxonomy",
                role,
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
            candidates.append(_candidate(l1, l2, l3, depth, "pattern", role))
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
            candidates.append(_candidate(l1, l2, l3, depth, "country", role))
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
            for l1, l2, l3 in group_tuples:
                candidates.append(_candidate(l1, l2, l3, 1, "compound", role))
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
            return [_candidate(OTHER_ETHNIC, "", "", 1, "broad_identity", role)]
    return []

def extract_org_candidates(text: str) -> list:
    """
    Case 10: known organization name scan.

    Checks ORG_NAME_ETHNICITY_MAP against the full text. Returns all
    matching entries (in practice at most one, but the function makes no
    assumption about cardinality — that constraint belongs in the resolver).

    Not role-tagged: a known-org match is always treated as a definitive
    last-resort lookup by the resolver, independent of served/weak tiering.
    """
    candidates = []
    for org_name, (l1, l2, l3) in ORG_NAME_ETHNICITY_MAP.items():
        if re.search(r'\b' + re.escape(org_name) + r'\b', text, re.IGNORECASE):
            depth = 3 if l3 else (2 if l2 else 1)
            candidates.append(_candidate(l1, l2, l3, depth, "org_lookup"))
    return candidates
