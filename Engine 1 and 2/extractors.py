import re

from ethnic_taggerv3 import (
    PATTERN_RULES,
    COUNTRY_REGION_MAP,
    ALWAYS_MULTIPLE_COMPOUNDS,
    BROAD_IDENTITY_KEYWORDS,
    ORG_NAME_ETHNICITY_MAP,
    OTHER_ETHNIC,
)

"""
extractors.py
-------------
Signal Extraction Layer — Layer 1 of the 3-layer classification pipeline.

Responsibility:
    Detect the PRESENCE of ethnic signals in text.

Constraint:
    NO filtering, suppression, negation, or context logic.
    Each function is a "dumb sensor" — it reports every match it sees.
    Negation filtering, example-mention guards, and context annotation
    all live in downstream layers.

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

def _candidate(level1: str, level2: str, level3: str, depth: int, source: str) -> dict:
    return {
        "level1": level1,
        "level2": level2,
        "level3": level3,
        "depth":  depth,
        "source": source,
    }

# ---------------------------------------------------------------------------
# Public extraction functions
# ---------------------------------------------------------------------------

def extract_taxonomy_candidates(text: str, taxonomy_entries: list) -> list:
    """
    Cases 1-3: raw taxonomy keyword presence scan.

    Iterates the full sorted taxonomy list and returns one candidate for
    every keyword that appears in the text. The trailing s? handles common
    plural forms (Somalis, Africans) without a separate entry per variant.

    No negation or example-mention filtering is applied here.
    """
    candidates = []
    for entry in taxonomy_entries:
        kw = entry["keyword"]
        if not kw:
            continue
        pattern = re.compile(r'\b' + re.escape(kw) + r's?\b', re.IGNORECASE)
        if not pattern.search(text):
            continue
        candidates.append(_candidate(
            entry["level1"],
            entry["level2"] or "",
            entry["level3"] or "",
            entry["depth"],
            "taxonomy",
        ))
    return candidates

def extract_pattern_candidates(text: str) -> list:
    """
    Case 4: structured/directional phrase scan.

    Scans ALL PATTERN_RULES and returns a candidate for every match.
    Unlike the current find_pattern_match(), this returns ALL matching
    patterns, not just the first — deduplication and priority are the
    resolver's responsibility.

    No negation filtering is applied here.
    """
    candidates = []
    for pattern, l1, l2, l3 in PATTERN_RULES:
        if re.search(pattern, text, re.IGNORECASE):
            depth = 3 if l3 else (2 if l2 else 1)
            candidates.append(_candidate(l1, l2, l3, depth, "pattern"))
    return candidates

def extract_country_candidates(text: str) -> list:
    """
    Cases 6 & 7: nationality and 'from <country>' phrase scan.

    Checks both the bare demonym form (Jamaicans) and the prepositional
    form (from Jamaica) for every entry in COUNTRY_REGION_MAP. Returns
    a candidate for every match found.

    No negation filtering is applied here.
    """
    candidates = []
    for country, (l1, l2, l3) in COUNTRY_REGION_MAP.items():
        direct     = re.search(r'\b' + re.escape(country) + r's?\b', text, re.IGNORECASE)
        from_phrase = re.search(r'\bfrom\s+' + re.escape(country) + r's?\b',  text, re.IGNORECASE)
        if direct or from_phrase:
            depth = 3 if l3 else (2 if l2 else 1)
            candidates.append(_candidate(l1, l2, l3, depth, "country"))
    return candidates

def extract_compound_candidates(text: str) -> list:
    """
    Afro-Caribbean / Afro-Latino compound identity scan.

    Each matched compound pattern expands into two candidates — one per
    component L1 group — so they combine into Multiple the same way two
    separately mentioned groups would.
    """
    candidates = []
    for compound_pattern, group_tuples in ALWAYS_MULTIPLE_COMPOUNDS.items():
        if re.search(compound_pattern, text, re.IGNORECASE):
            for l1, l2, l3 in group_tuples:
                candidates.append(_candidate(l1, l2, l3, 1, "compound"))
    return candidates

def extract_broad_identity_candidates(text: str) -> list:
    """
    Case 9b: broad identity label scan (mixed heritage, multiracial, etc.).

    Returns a single OTHER_ETHNIC candidate if any keyword is matched.
    Only one candidate is produced regardless of how many keywords match,
    because all keywords in this list map to the same classification outcome.
    """
    for kw_pattern in BROAD_IDENTITY_KEYWORDS:
        if re.search(kw_pattern, text, re.IGNORECASE):
            return [_candidate(OTHER_ETHNIC, "", "", 1, "broad_identity")]
    return []

def extract_org_candidates(text: str) -> list:
    """
    Case 10: known organization name scan.

    Checks ORG_NAME_ETHNICITY_MAP against the full text. Returns all
    matching entries (in practice at most one, but the function makes no
    assumption about cardinality — that constraint belongs in the resolver).
    """
    candidates = []
    for org_name, (l1, l2, l3) in ORG_NAME_ETHNICITY_MAP.items():
        if re.search(r'\b' + re.escape(org_name) + r'\b', text, re.IGNORECASE):
            depth = 3 if l3 else (2 if l2 else 1)
            candidates.append(_candidate(l1, l2, l3, depth, "org_lookup"))
    return candidates