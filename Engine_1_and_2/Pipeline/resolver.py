from typing import List, Tuple
from constants import (
    MULTIPLE_ETHNIC, OTHER_ETHNIC, GENERAL_POP, INDIGENOUS_L1, INDIGENOUS_UMBRELLA_FLAG,
    FLAG_INDIGENOUS_TOPIC_VERIFY,
)

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

def source_flag(source: str, level1: str = "") -> str:
    """
    Map a candidate source label to its human-readable flag string.
    Taxonomy and org_lookup matches produce no primary flag of their own
    (taxonomy is the default path; org is annotated by the caller branch).

    the "pattern" source covers both the directional-
    region rules (North African, South Asian, ...) AND the Indigenous terms
    (indigenous/aboriginal/metis/treaty 6/...) in PATTERN_RULES; a shared
    "Directional Region, e.g. North African" flag text was wrong for the
    Indigenous rows, so Indigenous gets its own text keyed on level1.
    """
    if source == "pattern" and level1 == INDIGENOUS_L1:
        return ("General Indigenous term matched (e.g. \"Indigenous\"/\"Aboriginal\"/"
                "\"First Nations\") - no specific nation or community named in the text")
    return {
        "pattern": ("Regional phrase matched (e.g. \"North African\", \"South Asian\") "
                    "- resolves to a sub-region, not a specific country or group"),
        "country": ("Country/nationality recognized via a supplementary list, not the "
                    "taxonomy sheet - confirm the assigned region is correct"),
        "compound": "Matched a known dual-identity phrase (e.g. \"Afro-Caribbean\") as a single component",
        "broad_identity": ("Broad, non-specific identity term matched (e.g. \"multiracial\", "
                           "\"mixed heritage\") - no specific ethnic group named in the text"),
    }.get(source, "")

def _role_rank(role: str) -> int:
    """Higher rank wins when dedup picks a representative occurrence for a
    group. "served" (a genuine served-population claim) always outranks
    "topic_keep" (a topic/partnership mention that keeps the classification
    but only via a verify flag), which in turn outranks any other weak role
    (org_name/provider/example/aspirational/topic)."""
    if role == "served":
        return 2
    if role == "topic_keep":
        return 1
    return 0

def dedup(states: List[State]) -> List[State]:
    """
    Collapse candidates that resolve to the identical (L1, L2, L3) outcome.
    Two detection methods landing on the same conclusion are a single
    confirmed answer, not a multi-group signal.

    Evidence-role rescue: if ANY occurrence of a group was matched with role
    "served", that group counts as served even if OTHER occurrences of the
    same group were weak (org_name/provider/example/aspirational/negated) --
    e.g. a group named once as the served population and again only as the
    delivering provider still counts as served via the first mention. The
    first-seen entry is kept as the representative (preserving its source
    label) unless a later "served" (or, failing that, "topic_keep")
    occurrence needs to promote it.
    """
    best: dict = {}
    order: List[tuple] = []
    for s in states:
        key = (s["level1"], s["level2"], s["level3"])
        if key not in best:
            best[key] = s
            order.append(key)
        elif _role_rank(s.get("role", "served")) > _role_rank(best[key].get("role", "served")):
            best[key] = s
    return [best[k] for k in order]

# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def resolve(states: List[State], context_flags: ContextFlags, bipoc_present: bool,) -> Resolution:
    """
    Deterministic state machine resolver.

    Decision order:

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
    # Evidence-role split: classify from "served"
    # candidates only. dedup() already rescued any group with at least one
    # served occurrence, so a group surviving in `weak` here was NEVER
    # mentioned as served population -- only as an org name, provider,
    # example, aspiration, or negation.
    #
    # "topic_keep" counts as served for classification
    # purposes -- a topic/partnership mention keeps the group in the running
    # -- but is tracked separately so a plain-served group can be told apart
    # from a topic_keep-only one when deciding whether to add
    # FLAG_INDIGENOUS_TOPIC_VERIFY below.
    # -----------------------------------------------------------------------
    served = [s for s in primary if s.get("role", "served") in ("served", "topic_keep")]
    weak   = [s for s in primary if s.get("role", "served") not in ("served", "topic_keep")]

    # -----------------------------------------------------------------------
    # Step 1 — BIPOC signal
    #
    # BIPOC is checked before the "no candidates" gate because when it is the
    # ONLY signal present it still has to produce MULTIPLE_ETHNIC.
    #
    #   BIPOC + NO other served group     -> Multiple. "BIPOC" spells out
    #       Black + Indigenous + People of Colour, so standing alone it is
    #       definitionally Multiple. Left unflagged: nothing to adjudicate.
    #
    #   BIPOC + exactly ONE named group   -> classify AS that group, not
    #       Multiple: the named group is the served population and BIPOC is
    #       only umbrella framing around it. A low-priority verify note is
    #       kept so broad-mandate orgs (where BIPOC really is the umbrella)
    #       still surface for manual review.
    #
    #   BIPOC + TWO OR MORE served groups -> Multiple via Step 3's ordinary
    #       distinct-L1 rule; BIPOC contributes nothing and isn't consulted.
    # -----------------------------------------------------------------------
    if bipoc_present:
        bipoc_groups = sorted(set(s["level1"] for s in served))
        if len(bipoc_groups) != 1:
            # No bare "BIPOC signal detected" primary flag: BIPOC-alone ->
            # Multiple is unambiguous. Only annotate when a specific group
            # also appears, so a reviewer can confirm the umbrella call.
            flag = ("Note (low priority): BIPOC keyword alongside specific group(s) ("
                    + ", ".join(bipoc_groups) + ") - verify manually") if served else ""
            return build_output(MULTIPLE_ETHNIC, "", "", flag, context_flags)
        # Exactly one served group: fall through to the ordinary single-L1
        # resolution below so the L2/L3 depth is chosen the same way as for
        # any other single-group row. The note rides along in context_flags,
        # which build_output appends to whichever branch ends up firing.
        context_flags = context_flags + [
            "Note (low priority): BIPOC keyword alongside specific group(s) ("
            + ", ".join(bipoc_groups) + ") - classified as that group; verify manually"
        ]

    # -----------------------------------------------------------------------
    # Step 2 — No served candidates
    # Try org fallback first; if only weak (org_name/provider/example/
    # aspirational/negated) candidates remain, keep General but name them in
    # a transparency note instead of silently dropping them. Otherwise fall
    # through to plain General Population.
    # -----------------------------------------------------------------------
    if not served:
        if org:
            org_l1 = set(s["level1"] for s in org)
            if len(org_l1) >= 2:
                return build_output(
                    MULTIPLE_ETHNIC, "", "",
                    "Classified from the organization's name via a curated lookup list "
                    "(multiple groups) - the request text itself contains no ethnic signal; "
                    "confirm this still reflects who is served",
                    context_flags,
                )
            best = org[0]
            return build_output(
                best["level1"], best["level2"], best["level3"],
                "Classified from the organization's name via a curated lookup list - "
                "the request text itself contains no ethnic signal; confirm this still "
                "reflects who is served",
                context_flags,
            )
        if weak:
            groups = sorted({
                s["level1"] + (f" ({s['level2'] or s['level3']})" if (s["level2"] or s["level3"]) else "")
                for s in weak
            })
            roles = sorted({s.get("role", "served") for s in weak})
            note = (
                "Note (low priority): " + ", ".join(groups)
                + " mentioned in " + "/".join(roles)
                + " context only - not classified as served population; verify"
            )
            return build_output(GENERAL_POP, "", "", note, context_flags)
        return build_output(GENERAL_POP, "", "", "", context_flags)

    primary = served

    # -----------------------------------------------------------------------
    # Step 2 — Black + Indigenous / Black + African co-occurrence checks
    #
    # Black is L2 under "Other Ethnic and Cultural Origins", not its own L1.
    # These checks must run BEFORE Step 3 so they emit the correct flag text
    # rather than the generic "multiple distinct groups detected".
    # -----------------------------------------------------------------------
    is_black = any(
        "black" in s["level2"].lower()
        for s in primary if s["level1"] == OTHER_ETHNIC
    )
    is_indigenous = any(s["level1"] == "North American Indigenous Origins" for s in primary)
    is_african = any(s["level1"] == "African Origins" for s in primary)
    is_caribbean = any(s["level1"] == "Caribbean Origins" for s in primary)

    if is_black and is_indigenous and not bipoc_present:
        return build_output(
            MULTIPLE_ETHNIC, "", "",
            "BIPOC signal detected (Black and Indigenous co-present — verify served population)",
            context_flags,
        )

    if is_black and is_african or is_black and is_caribbean: # Handle black & caribbean as well.
        return build_output(MULTIPLE_ETHNIC, "", "", "", context_flags)

    # -----------------------------------------------------------------------
    # Step 3 — Multiple distinct Level 1 groups
    # Any two candidates from different L1 branches → Multiple.
    # Deduplication already collapsed same-outcome duplicates, so two
    # surviving entries with different L1 are genuinely different groups.
    # -----------------------------------------------------------------------
    distinct_l1 = set(s["level1"] for s in primary)
    if len(distinct_l1) >= 2:
        # The generic "multiple distinct groups detected" string is dropped as
        # pure noise — the Multiple classification itself already says as much.
        # No primary flag; context flags (if any) still appended.
        return build_output(MULTIPLE_ETHNIC, "", "", "", context_flags)

    indigenous_topic_keep_only = (
        next(iter(distinct_l1)) == INDIGENOUS_L1
        and all(s.get("role", "served") == "topic_keep" for s in primary)
    )
    verify_flags = context_flags + [FLAG_INDIGENOUS_TOPIC_VERIFY] if indigenous_topic_keep_only else context_flags

    # -----------------------------------------------------------------------
    # Step 4 — Deepest shared level within a single L1
    #
    # Rule: find the deepest taxonomy level at which ALL surviving candidates
    # hold the identical value.
    #
    # Umbrella drop: L1-only entries (no L2, no L3 — e.g. bare "African")
    # are dropped first when at least one specific candidate also exists,
    # so they don't constrain the outcome.
    #
    # Resolution order (over the surviving candidate set):
    #   1. All agree on the same non-empty L3 → return that L3 (with its L2)
    #   2. All agree on the same L2            → return that L2
    #   3. Otherwise                           → return the shared L1
    #
    # If only umbrella candidates remain (all L1-only), return the L1.
    # -----------------------------------------------------------------------
    shared_l1 = primary[0]["level1"]

    specific = [s for s in primary if s["level2"] or s["level3"]]

    # Step 4a — North American Indigenous umbrella + specific sub-group(s).
    # Scoped to Indigenous only. When a broad umbrella signal (L1-only:
    # indigenous / aboriginal / treaty 6 / indigenous canadian) co-occurs with
    # TWO OR MORE distinct specific sub-groups (Métis, First Nations, Inuit,
    # Cree, ...), classify at the general L1 and flag for review — genuinely
    # ambiguous which sub-group(s) are served. But when exactly ONE distinct
    # sub-group co-occurs with the umbrella, don't roll up: fall through to
    # the normal pool resolution below, which narrows to that one sub-group.
    if shared_l1 == INDIGENOUS_L1 and specific:
        umbrella_present = any(not (s["level2"] or s["level3"]) for s in primary)
        distinct_subs = {s["level2"] or s["level3"] for s in specific}
        if umbrella_present and len(distinct_subs) >= 2:
            subs = sorted(distinct_subs)
            flag = INDIGENOUS_UMBRELLA_FLAG + " (" + ", ".join(subs) + ")"
            return build_output(shared_l1, "", "", flag, verify_flags)

    pool = specific if specific else primary

    # Single candidate in the pool — return its full path with source flag.
    if len(pool) == 1:
        best = pool[0]
        return build_output(
            shared_l1, best["level2"], best["level3"],
            source_flag(best["source"], best["level1"]),
            verify_flags,
        )

    # Multiple candidates — consensus resolution.
    l3_vals = set(s["level3"] for s in pool)
    if len(l3_vals) == 1 and next(iter(l3_vals)):
        winner = pool[0]
        return build_output(shared_l1, winner["level2"], winner["level3"], "", verify_flags)

    l2_vals = set(s["level2"] for s in pool)
    if len(l2_vals) == 1:
        return build_output(shared_l1, next(iter(l2_vals)), "", "", verify_flags)

    return build_output(shared_l1, "", "", "", verify_flags)
