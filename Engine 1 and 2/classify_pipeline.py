import re

from ethnic_taggerv3 import (
    get_column_texts,
    extract_context_signals,
    build_context_notes,
    is_bipoc_real_target,
    check_grassroots_case,
    matches_any,
    detect_ethnocultural_org_name,
    EXPERT_ROLE_PHRASES,
    GENERAL_POP,
)

from constants import LANGUAGE_ACCOMMODATION_PATTERNS, FRENCH_ETHNIC_KEEP_PATTERNS

from extractors import (
    extract_taxonomy_candidates,
    extract_compound_candidates,
    extract_pattern_candidates,
    extract_country_candidates,
    extract_broad_identity_candidates,
    extract_org_candidates,
)

from resolver import resolve

"""
classify_pipeline.py
--------------------
Classification orchestration layer — wires the 3-layer pipeline:

    Layer 1  : extractors.py       (signal extraction)
    Layer 2  : ethnic_taggerv3.py  (context annotation)
    Layer 3  : resolver.py         (state machine decision)

This module contains NO classification logic. All ethnic origin decisions
live in resolver.py. This function is pure orchestration.
"""

# ---------------------------------------------------------------------------
# P2-1 — French language accommodation filter
# ---------------------------------------------------------------------------

def filter_french_language_accommodation(candidates, combined):
    """
    If text signals language accommodation (french-speaking, in French and English,
    official-language minority, francophone) and does NOT match an ethnic keep-pattern
    (French Canadian Association, Francophone Cultural Society, etc.), drop any
    French/European ethnic candidates and return an annotation note.

    Prevents spurious Multiple when "in French and English" + Indigenous appears.
    """
    if not matches_any(LANGUAGE_ACCOMMODATION_PATTERNS, combined):
        return candidates, None
    if matches_any(FRENCH_ETHNIC_KEEP_PATTERNS, combined):
        return candidates, None
    filtered = [
        c for c in candidates
        if not (
            c["level1"] == "European Origins"
            and "french" in (c["level2"] + c["level3"]).lower()
        )
    ]
    note = "French reference treated as language accommodation — verify ethnic identity"
    if len(filtered) == len(candidates):
        return candidates, note
    return filtered, note


# ---------------------------------------------------------------------------
# Annotation helpers — no classification logic, annotation text only
# ---------------------------------------------------------------------------

def extra_annotation_notes(combined, states, bipoc_present):
    """
    Builds review-flag annotation notes for signals that require human
    judgement but do not change the classification outcome.

    Excludes: historical / expansion / aspirational / example (debug only).
    Excludes: Case 13 ethnocultural org title — called separately in
              classify_row() because it requires the raw row and taxonomy.
    """
    notes = []

    if re.search(r"\bcultural association\b", combined, re.IGNORECASE):
        notes.append("'Cultural Association' detected - verify named group manually")

    # Org candidates are last-resort; exclude them when computing whether a
    # real ethnic signal is present for the grassroots / equity-word check.
    primary_states = [s for s in states if s["source"] != "org_lookup"]
    has_ethnic_signal = bool(primary_states) or bipoc_present

    grassroots_state = check_grassroots_case(combined, has_ethnic_signal)
    if grassroots_state == "no_signal":
        notes.append("Ambiguous equity term with no paired ethnic signal")
    if grassroots_state == "has_signal":
        notes.append("Equity/diversity buzzword present alongside a real signal - verify manually")

    if primary_states and matches_any(EXPERT_ROLE_PHRASES, combined):
        notes.append("Possible consulted-party mention (expert/advisor role) rather than served population - verify manually")

    if primary_states and re.search(r"\b(especially|particularly)\b", combined, re.IGNORECASE):
        notes.append("Emphasis phrase ('especially'/'particularly') detected — verify specificity of population served")

    if re.search(r"\bhindu\b", combined, re.IGNORECASE):
        notes.append("'Hindu' detected — may imply South Asian/Indian origin; verify as religion vs. ethnicity")

    return notes

# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def classify_row(row, taxonomy_entries):
    """
    Orchestrate the 3-layer ethnic origin classification pipeline.
    No if/else for ethnicity decisions — all decisions live in resolver.py.
    """

    # ------------------------------------------------------------------
    # Step 1 — Normalize text
    # get_column_texts handles: column selection, normalize_text(),
    # apply_identity_phrase_rewrites() (e.g. "African Canadian" → "black")
    # ------------------------------------------------------------------
    col_texts = get_column_texts(row)
    combined  = " ".join(t for t in col_texts if t.strip())

    if not combined.strip():
        return (GENERAL_POP, "", "", "Empty input")

    # ------------------------------------------------------------------
    # Step 2 — Extract signals
    # All extractor functions are dumb sensors: no filtering,
    # no negation guards, no context logic. Each returns every match.
    # ------------------------------------------------------------------
    candidates = (
        extract_taxonomy_candidates(combined, taxonomy_entries)
        + extract_compound_candidates(combined)
        + extract_pattern_candidates(combined)
        + extract_country_candidates(combined)
        + extract_broad_identity_candidates(combined)
        + extract_org_candidates(combined)
    )

    # ------------------------------------------------------------------
    # Step 3 — Extract context flags
    # Production notes: negation only. Historical / expansion /
    # aspirational / example are debug metadata only.
    # ------------------------------------------------------------------
    context = build_context_notes(extract_context_signals(combined))

    # ------------------------------------------------------------------
    # Step 4 — Compute BIPOC presence
    # ------------------------------------------------------------------
    bipoc_present = is_bipoc_real_target(combined)

    # ------------------------------------------------------------------
    # Step 4b — French language accommodation filter (P2-1)
    # Drop French/European candidates when text is about language access,
    # not ethnic identity. Annotation note collected into pre_notes so it
    # is appended alongside the resolver flag in Step 8.
    # ------------------------------------------------------------------
    pre_notes = []
    candidates, french_note = filter_french_language_accommodation(candidates, combined)
    if french_note:
        pre_notes.append(french_note)

    # ------------------------------------------------------------------
    # Step 5 — Build states
    # Candidates from extractors are already in resolver-ready format:
    # { level1, level2, level3, depth, source }
    # ------------------------------------------------------------------
    states = candidates

    # ------------------------------------------------------------------
    # Step 6 — Resolve
    # Resolver embeds context flag strings into the output flag.
    # Context NEVER influences which classification branch fires.
    # ------------------------------------------------------------------
    e1, e2, e3, flag = resolve(states, context, bipoc_present)

    # ------------------------------------------------------------------
    # Step 7 — Build extra annotation notes
    # Equity-word, expert-role, cultural association checks.
    # ------------------------------------------------------------------
    notes = pre_notes + extra_annotation_notes(combined, states, bipoc_present)

    # ------------------------------------------------------------------
    # Step 7b — Case 13: potential ethnocultural org name in title
    #
    # Guard inside detect_ethnocultural_org_name() skips this entirely
    # when candidates exist or BIPOC is present — it is strictly a
    # last-resort safety net for fully unclassified rows.
    # ------------------------------------------------------------------
    funding_name = row.get("Funding Request Name", "") or ""
    org_note = detect_ethnocultural_org_name(
        funding_name, candidates, bipoc_present, taxonomy_entries
    )
    if org_note:
        notes.append(org_note)

    # ------------------------------------------------------------------
    # Step 8 — Attach extra notes to final flag
    # Context notes already embedded by resolver (step 6).
    # Only extra notes appended here — no double-append.
    # ------------------------------------------------------------------
    if notes:
        note_text = "; ".join(notes)
        flag = f"{flag}; {note_text}" if flag else note_text

    return (e1, e2, e3, flag)
