import os
import re

from ethnic_taggerv3 import (
    get_body_and_name_texts,
    extract_context_signals,
    build_context_notes,
    is_bipoc_real_target,
    matches_any,
    detect_ethnocultural_org_name,
    is_non_prefixed,
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
# ML AUGMENTATION LAYER — Phase B: evidence-role NLI arbiter (Plan.md
# "ML AUGMENTATION LAYER" section). Off by default so the deterministic
# rule engine stays the shipping path; set USE_ML_ROLE_ARBITER=1 to A/B
# test the learned role frames against the regex-only path (audit_score.py
# picks up the env var the same way — no code change needed to compare).
# ---------------------------------------------------------------------------

USE_ML_ROLE_ARBITER = os.environ.get("USE_ML_ROLE_ARBITER") == "1"

# Only override a regex "served" call when the NLI arbiter's next-best
# weak role beats "served" by this margin (raw entailment logits, not
# probabilities — a margin, not an absolute confidence, is what's
# comparable across premises). Conservative by construction: silence
# (no override) is the safe failure mode on these sensitive axes.
ML_ROLE_OVERRIDE_MARGIN = 1.5


def apply_ml_role_arbiter(candidates):
    """
    Phase B: for each candidate the regex role frames (infer_role) tagged
    "served", ask the vendored NLI cross-encoder for a second opinion on
    that exact span/context. If the arbiter is confidently more specific
    (e.g. "org_name"/"provider"/"example") than "served", demote the
    candidate's role and record why — this is the learned generalization
    of Phase 2 tiering the plan calls for (Alberta Ballet's "Black
    classical ballet company", Digestive Health's "Indigenous
    Nutritionist", incidental body mentions the regex frames don't cover).

    Never promotes a regex weak role to "served" — the regex frames are
    already tuned/regression-tested for the strong case; the arbiter's
    job here is only to catch regex false positives, not add new signal.
    Candidates without a captured span/context (e.g. org_lookup) pass
    through untouched.
    """
    if not USE_ML_ROLE_ARBITER:
        return candidates
    from ml_arbiter import nli_role

    refined = []
    for c in candidates:
        if c.get("role") != "served" or not c.get("span") or not c.get("context"):
            refined.append(c)
            continue
        scores = nli_role(c["span"], c["context"])
        best = scores["best_role"]
        if best in ("served", "negated"):
            refined.append(c)
            continue
        if scores[best] - scores["served"] < ML_ROLE_OVERRIDE_MARGIN:
            refined.append(c)
            continue
        c = dict(c)
        c["role"] = best
        c["ml_role_note"] = (
            f'ML role arbiter: "{c["span"]}" reclassified served -> {best} '
            f'(served={scores["served"]:.2f}, {best}={scores[best]:.2f})'
        )
        refined.append(c)
    return refined


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

def extra_annotation_notes(combined, states, bipoc_present, resolved_label=None):
    """
    Builds review-flag annotation notes for signals that require human
    judgement but do not change the classification outcome.

    Excludes: historical / expansion / aspirational / example (debug only).
    Excludes: Case 13 ethnocultural org title — called separately in
              classify_row() because it requires the raw row and taxonomy.

    Fix 4 (noise removal): "Ambiguous equity term with no paired ethnic
    signal", "Equity/diversity buzzword present alongside a real signal",
    and "Possible consulted-party mention (expert/advisor role)" no longer
    fire — check_grassroots_case() and EXPERT_ROLE_PHRASES stay defined and
    available for other callers; this function just stops emitting their
    note text.

    Fix 6 (context-only gating): Emphasis and 'Hindu' are CONTEXTUAL —
    verify-manually notes, not classification-relevant like negation/BIPOC
    — so only fire when the row actually resolved to something other than
    General. When resolved_label is None (caller not yet gating), they fire
    unconditionally, preserving prior behaviour for any other caller.
    """
    notes = []

    if re.search(r"\bcultural association\b", combined, re.IGNORECASE):
        notes.append("'Cultural Association' detected - verify named group manually")

    # Org candidates are last-resort; exclude them when computing whether a
    # real ethnic signal is present for the negation check below.
    primary_states = [s for s in states if s["source"] != "org_lookup"]

    is_general = resolved_label is not None and resolved_label == GENERAL_POP

    if primary_states and not is_general and re.search(r"\b(especially|particularly)\b", combined, re.IGNORECASE):
        notes.append("Emphasis phrase ('especially'/'particularly') detected — verify specificity of population served")

    if not is_general and re.search(r"\bhindu\b", combined, re.IGNORECASE):
        notes.append("'Hindu' detected — may imply South Asian/Indian origin; verify as religion vs. ethnicity")

    # Non-{group} negation: check if any matched candidate's ethnic keyword appears
    # immediately after "non-" in the text. Annotation only — does not suppress candidates.
    # Uses is_non_prefixed (the per-keyword path) rather than NEGATION_PHRASES (whole-text scan),
    # so "non-profit" cannot trigger it — only an actually matched ethnic term can.
    if primary_states and has_non_prefixed_negation(primary_states, combined):
        notes.append("Negation detected - verify exclusion vs inclusion intent")

    return notes

def has_non_prefixed_negation(states, combined):
    """
    Return True if any primary candidate's ethnic term appears after 'non-' in text.
    Extracts a searchable keyword from each candidate's most specific level name
    (L3 first, then the last content word of L2/L1 after stripping 'Origins').
    """
    for s in states:
        for level in [s["level3"], s["level2"], s["level1"]]:
            if not level:
                continue
            # Strip comma-qualified suffixes ("Black, not otherwise specified" → "Black")
            word = re.sub(r'\s*,.*$', '', level).strip()
            # Strip "Origins" and leading direction words to reach the ethnic noun
            word = re.sub(r'\borigins?\b', '', word, flags=re.IGNORECASE).strip()
            parts = [p for p in word.split() if len(p) > 2]
            if not parts:
                continue
            # Use the last meaningful word: "North American Indigenous" → "Indigenous"
            keyword = parts[-1]
            if is_non_prefixed(keyword, combined):
                return True
    return False

# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def classify_row(row, taxonomy_entries):
    """
    Orchestrate the 3-layer ethnic origin classification pipeline.
    No if/else for ethnicity decisions — all decisions live in resolver.py.
    """

    # ------------------------------------------------------------------
    # Step 1 — Normalize text, split into body vs. name
    # get_body_and_name_texts handles: column selection, normalize_text(),
    # apply_identity_phrase_rewrites() (e.g. "African Canadian" → "black"),
    # keeping the served-population body separate from the org/request name.
    # ------------------------------------------------------------------
    body_text, name_text = get_body_and_name_texts(row)
    combined = (body_text + " " + name_text).strip()

    if not combined:
        return (GENERAL_POP, "", "", "Empty input")

    # ------------------------------------------------------------------
    # Step 2 — Extract signals (body vs. name)
    # All extractor functions are dumb sensors: no filtering,
    # no negation guards, no context logic. Each returns every match.
    #
    # A signal must be corroborated in the body to classify (Plan.md D1).
    # The name is only consulted for a curated known-org lookup and to
    # decide whether a name-only signal should be flagged.
    # ------------------------------------------------------------------
    def _extract(txt, name_for_role=""):
        return (
            extract_taxonomy_candidates(txt, taxonomy_entries, name_for_role)
            + extract_compound_candidates(txt, name_for_role)
            + extract_pattern_candidates(txt, name_for_role)
            + extract_country_candidates(txt, name_for_role)
            + extract_broad_identity_candidates(txt, name_for_role)
            + extract_org_candidates(txt)
        )

    # name_text is passed through so a candidate whose body match merely
    # echoes the org's own name (e.g. "Black Canadian Women in Action is
    # undertaking...") is tagged role="org_name" (weak) instead of "served".
    body_candidates = _extract(body_text, name_text)
    body_candidates = apply_ml_role_arbiter(body_candidates)  # Phase B, off by default
    bipoc_present    = is_bipoc_real_target(body_text)   # BIPOC must be in the body
    name_org         = extract_org_candidates(name_text)  # curated known-org from the name
    name_signal      = bool(_extract(name_text)) or is_bipoc_real_target(name_text)

    # Name-only guard: nothing in the body, but the name carries a signal.
    if not body_candidates and not bipoc_present:
        if name_org:  # known org (e.g. Niginan) classifies
            candidates = name_org
        elif name_signal:
            return (GENERAL_POP, "", "",
                    "Signal appears only in the organization/funding-request name - "
                    "classified General; verify served population")
        else:
            candidates = []
    else:
        candidates = body_candidates

    # ------------------------------------------------------------------
    # Step 3 — Extract context flags
    # Production notes: negation only. Historical / expansion /
    # aspirational / example are debug metadata only.
    # ------------------------------------------------------------------

    # Negation is surfaced ONLY when an ethnic term was actually detected (anchor),
    # using the pruned ETHNIC_ANNOTATION_NEGATION_PHRASES list.
    ethnic_term_present = bool(candidates) or bipoc_present
    context = build_context_notes(extract_context_signals(combined), ethnic_term_present)

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
    # Cultural-association, emphasis, Hindu, and negation checks. Emphasis/
    # Hindu are gated to non-General rows (Fix 6) — see extra_annotation_notes.
    # ------------------------------------------------------------------
    ml_notes = [f"Note (low priority): {c['ml_role_note']}" for c in states if c.get("ml_role_note")]
    notes = pre_notes + ml_notes + extra_annotation_notes(combined, states, bipoc_present, resolved_label=e1)

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
