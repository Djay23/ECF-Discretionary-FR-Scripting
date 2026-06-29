from typing import List, Tuple

"""
resolver.py
-----------
State Machine Resolver — Layer 3 of the 3-layer classification pipeline.

Responsibility:
    All classification decision logic lives here and only here.

Constraints:
    - Context flags MUST NOT suppress, override, or influence any decision.
    - Context flags are appended to the output flag string only.
    - No external helpers. All logic is self-contained.
    - Fully deterministic and testable in isolation.

Input:
    states : List[State]  — pre-filtered candidate signals from extractors
    context_flags : List[str] — annotations from the context layer (read-only)
    bipoc_present : bool — BIPOC signal detected upstream

Output:
    (Ethnic1: str, Ethnic2: str, Ethnic3: str, Flag: str)

NOTE on 'states' contract:
    The resolver trusts that states have already been passed through a
    negation/example-mention filter before reaching this function.
    Org-lookup candidates (source == "org_lookup") are separated internally
    and treated as last-resort fallback only.
"""

# ---------------------------------------------------------------------------
# Type definitions
# ---------------------------------------------------------------------------

# A State is a dict produced by extractors.py:
#   { level1: str, level2: str, level3: str, depth: int, source: str }
State = dict

ContextFlags = List[str]
Resolution   = Tuple[str, str, str, str]   # (Ethnic1, Ethnic2, Ethnic3, Flag)

# ---------------------------------------------------------------------------
# Classification outcome constants
# (mirrored from ethnic_taggerv3.py — move to constants.py when shared)
# ---------------------------------------------------------------------------

MULTIPLE_ETHNIC = "Multiple Ethnic and Cultural Origins"
OTHER_ETHNIC = "Other Ethnic and Cultural Origins"
GENERAL_POP = "General Population (No specific ethnic and cultural origin group served)"

# ---------------------------------------------------------------------------
# Internal helpers — private to this module
# ---------------------------------------------------------------------------

def build_output(l1: str, l2: str, l3: str,
                  primary_flag: str,
                  context_flags: ContextFlags) -> Resolution:
    """
    Combine the primary classification flag with any context annotations.
    Context flags are appended, never prepended — classification is always
    the leading signal in the flag column.
    """
    parts = [f for f in ([primary_flag] + context_flags) if f]
    return (l1, l2, l3, "; ".join(parts))

def source_flag(source: str) -> str:
    """
    Map a candidate source label to its human-readable flag string.
    Taxonomy and org_lookup matches produce no primary flag of their own
    (taxonomy is the default path; org is annotated by the caller branch).
    """
    return {
        "pattern": "Pattern rule match (structured phrase)",
        "country": "Country/nationality mapping match",
        "compound": "Compound identity term match",
        "broad_identity": "Broad identity term - review recommended",
    }.get(source, "")

def dedup(states: List[State]) -> List[State]:
    """
    Collapse candidates that resolve to the identical (L1, L2, L3) outcome.
    Two detection methods landing on the same conclusion are a single
    confirmed answer, not a multi-group signal.
    The first-seen entry is kept so the source label is preserved.
    """
    seen: set = set()
    result: List[State] = []
    for s in states:
        key = (s["level1"], s["level2"], s["level3"])
        if key not in seen:
            seen.add(key)
            result.append(s)
    return result

# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def resolve(states: List[State], context_flags: ContextFlags, bipoc_present: bool,) -> Resolution:
    """
    Deterministic state machine resolver.

    Decision order (preserved from ethnic_taggerv3.classify_row):

        1. BIPOC signal present              → MULTIPLE_ETHNIC
        2. No primary candidates             → org fallback or GENERAL_POP
        3. Multiple distinct L1 groups       → MULTIPLE_ETHNIC
        4. Tied deepest candidates (same L1) → MULTIPLE_ETHNIC
        5. Single deepest candidate          → that candidate's L1/L2/L3

    Context flags are appended to whichever branch fires. They never alter
    which branch fires.
    """

    # -----------------------------------------------------------------------
    # Separate org-lookup candidates from primary signal candidates.
    # Org lookup is a last-resort fallback — it is only consulted when no
    # primary candidates exist after deduplication.
    # -----------------------------------------------------------------------
    primary = dedup([s for s in states if s["source"] != "org_lookup"])
    org = [s for s in states if s["source"] == "org_lookup"]

    # -----------------------------------------------------------------------
    # Step 1 — BIPOC signal
    # BIPOC is checked before the "no candidates" gate because it produces
    # MULTIPLE_ETHNIC regardless of whether other ethnic signals are present.
    # -----------------------------------------------------------------------
    if bipoc_present:
        if primary:
            groups = sorted(set(s["level1"] for s in primary))
            flag = ("Ambiguous: BIPOC mentioned alongside specific group(s) (" + ", ".join(groups) + ") - verify manually"
            )
        else:
            flag = "BIPOC signal detected"
        return build_output(MULTIPLE_ETHNIC, "", "", flag, context_flags)

    # -----------------------------------------------------------------------
    # Step 2 — No primary candidates
    # Try org fallback first; fall through to General Population if none.
    # -----------------------------------------------------------------------
    if not primary:
        if org:
            best = org[0]
            return build_output(
                best["level1"], best["level2"], best["level3"],
                "Matched via known organization name lookup",
                context_flags,
            )
        return build_output(GENERAL_POP, "", "", "", context_flags)

    # -----------------------------------------------------------------------
    # Step 3 — Multiple distinct Level 1 groups
    # Any two candidates from different L1 branches → Multiple.
    # Deduplication already collapsed same-outcome duplicates, so two
    # surviving entries with different L1 are genuinely different groups.
    # -----------------------------------------------------------------------
    distinct_l1 = set(s["level1"] for s in primary)
    if len(distinct_l1) >= 2:
        return build_output(
            MULTIPLE_ETHNIC, "", "",
            "Review: multiple distinct groups detected",
            context_flags,
        )

    # -----------------------------------------------------------------------
    # Step 4 — Depth resolution within a single L1
    # Deepest match wins. If two or more candidates tie at the deepest level
    # with different L2/L3 paths, that is still Multiple within one origin.
    # -----------------------------------------------------------------------
    max_depth = max(s["depth"] for s in primary)
    deepest = [s for s in primary if s["depth"] == max_depth]

    if len(deepest) >= 2:
        return build_output(
            MULTIPLE_ETHNIC, "", "",
            "Review: multiple sub-groups within same origin",
            context_flags,
        )

    # -----------------------------------------------------------------------
    # Step 5 — Single best candidate
    # -----------------------------------------------------------------------
    best = deepest[0]
    return build_output(
        best["level1"], best["level2"], best["level3"],
        source_flag(best["source"]),
        context_flags,
    )
