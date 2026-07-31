import os
import re

import pandas as pd

from ethnic_taggerv3 import (
    get_body_and_name_texts,
    extract_context_signals,
    build_context_notes,
    is_bipoc_real_target,
    matches_any,
    detect_ethnocultural_org_name,
    is_non_prefixed,
    normalize_text,
    apply_identity_phrase_rewrites,
    parse_raw_org_name,
    body_names_a_population,
    _body_without_org_name,
    GENERAL_POP,
    MULTIPLE_ETHNIC,
)

from constants import (
    LANGUAGE_ACCOMMODATION_PATTERNS, FRENCH_ETHNIC_KEEP_PATTERNS,
    SILENT_NAME_RELIGION_PATTERN, SILENT_NAME_LANGUAGE_PATTERN,
    IDENTITY_EXPANSION_DISCLAIMER_PATTERNS,
)

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
# ML AUGMENTATION LAYER — evidence-role NLI arbiter. Off by default so the
# deterministic rule engine stays the shipping path; set USE_ML_ROLE_ARBITER=1
# to A/B test the learned role frames against the regex-only path
# (audit_score.py reads the same env var — no code change needed to compare).
# ---------------------------------------------------------------------------

USE_ML_ROLE_ARBITER = os.environ.get("USE_ML_ROLE_ARBITER") == "1"

# Two-tier "ambiguity moat" over the NLI arbiter's margin (raw entailment
# logits, not probabilities — a margin, not an absolute confidence, is
# what's comparable across premises):
#   margin <  ML_ROLE_NOTE_MARGIN                -> silent, no-op
#   ML_ROLE_NOTE_MARGIN <= margin < ML_ROLE_OVERRIDE_MARGIN -> low-priority note
#   margin >= ML_ROLE_OVERRIDE_MARGIN             -> high-confidence note
# The arbiter NEVER changes `role` or the classification at any tier — see
# docstring below. These two constants are provisional; calibrate against
# the live 448-row margin distribution before trusting them (see
# Engine_1_and_2/Auditing/calibrate_ml_role_margins.py).
ML_ROLE_NOTE_MARGIN = 0.5
ML_ROLE_OVERRIDE_MARGIN = 1.5

# Column the workbook uses to mark a row as already stakeholder-reviewed
# (non-blank = a human already corrected/confirmed this row's classification).
# classify_row() skips the ML role arbiter entirely for such rows so it can
# never attach a second-guessing note to a human-confirmed decision,
# regardless of margin.
STAKEHOLDER_REVIEWED_COL = "Classification Accuracy (Corrected in Different Areas)"


def apply_ml_role_arbiter(candidates):
    """
    Phase B: for each candidate the regex role frames (infer_role) tagged
    "served", ask the vendored NLI cross-encoder for a second opinion on
    that exact span/context. This is a learned generalization over the
    regex phrase lists (ROLE_TOPIC_AFTER_PATTERNS, ASPIRATIONAL_PHRASES,
    etc.), which only catch wording someone anticipated — a paraphrase
    (e.g. "Indigenous ways of knowing" vs. the enumerated "Indigenous
    perspectives") silently defaults to "served" today.

    ADVISORY ONLY: this function never mutates `role` or any classification
    output. Its only effect is attaching `ml_role_note` (a verify-only
    annotation, same status as any other context flag) when the arbiter
    disagrees with "served" by enough margin — nothing here can change
    Ethnic 1/2/3, the resolver branch taken, or any other candidate field
    that feeds the classification decision. This mirrors the resolver's
    own invariant that context flags never influence which branch fires
    (see resolver.py module docstring).

    Never promotes a regex weak role to "served" — the regex frames are
    already tuned/regression-tested for the strong case; the arbiter's
    job here is only to flag likely regex false negatives, not add new
    classification signal. Candidates without a captured span/context
    (e.g. org_lookup) pass through untouched.
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
        if best == "served":
            refined.append(c)
            continue
        margin = scores[best] - scores["served"]
        if margin < ML_ROLE_NOTE_MARGIN:
            refined.append(c)
            continue
        c = dict(c)
        detail = f'(served={scores["served"]:.2f}, {best}={scores[best]:.2f})'
        # "negated" reads awkwardly as "reads as negated, not served" -- give
        # it its own clause instead of reusing the generic "reads as <role>"
        # phrasing the other weak roles share.
        if best == "negated":
            verdict = f'"{c["span"]}" may be explicitly excluded, not served'
        else:
            verdict = f'"{c["span"]}" reads as {best}, not served'
        if margin < ML_ROLE_OVERRIDE_MARGIN:
            c["ml_role_note"] = (
                f'Note (low priority): ML role arbiter suggests {verdict} {detail} - verify'
            )
        else:
            c["ml_role_note"] = (
                f'ML role arbiter: {verdict} (high confidence) {detail} - verify'
            )
        refined.append(c)
    return refined


# ---------------------------------------------------------------------------
# French language accommodation filter
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
# Generalizable silent-body name rule
# ---------------------------------------------------------------------------

# Removed 2026-07-28: this ETHNIC name-inference flag fired 37x with 0 errors
# across both gold sheets -- pure reviewer fatigue. Emptied so the returns below
# produce no flag; the classification from the org name is unchanged. The GENDER
# axis keeps its own SILENT_NAME_FLAG_TEXT (30 fires, 5 real catches -- the
# org-name Women/Girls safety net), so this removal is ethnic-only.
SILENT_NAME_FLAG = ""

# Emitted when a row's ONLY served evidence is the organization naming itself
# (an org-name echo, or a copula self-description like "X is the only Indigenous
# Artist-Run Centre") -- see ethnic_taggerv3.SELF_ID_ROLE.
#
# Why this exists: self-identification used to be DEMOTED, which left the body
# with no served signal, which routed the row through classify_from_raw_name --
# and that rule always attached SILENT_NAME_FLAG. Once self-identification
# became a served signal, those rows started classifying through the ordinary
# taxonomy branch instead, where source_flag() returns "" -- so they silently
# lost their flag. The label was right and the flag was gone, which is the
# worst combination: a confident classification with nothing telling a reviewer
# it was INFERRED from the org's name rather than stated. This restores the
# "any name-derived classification is flagged" guarantee.
SELF_ID_FLAG = (
    "Classified from the organization's own self-description - the text never states "
    "who is served; verify served population"
)

def classify_from_raw_name(raw_name, taxonomy_entries):
    """
    Only called when the body carries no signal at all (the existing
    "not body_candidates and not bipoc_present" guard in classify_row) --
    i.e. a truly silent body, NOT merely a body with a weak/org_name-echo
    mention (a body that DOES mention an identity term, even as a
    self-reference or historical aside, is handled by the normal resolver
    weak-candidate path instead; see infer_role's org-name-echo demotion).

    Classifies from identity terms in the RAW (pre-normalize, pre-identity-
    rewrite) funding-request account name, generalizing a per-org last
    resort to any unseen org.

    Returns (l1, l2, l3, flag) — ALWAYS flagged when non-None — or None if
    nothing in the name is recognized.

    Order of decision:
      1. Religion/language-only exclusions ("Islamic Missionary
         Association", "French Canadian Association") -> General + a
         targeted note. These never guess an ethnicity from an inherently
         ambiguous religious/linguistic marker, even if a bare "french"
         keyword would otherwise match a real taxonomy L3 entry.
      2. BIPOC / two-or-more distinct L1 groups -> Multiple.
      3. Any single recognized identity/country/pattern term -> that group.
      4. Nothing recognized -> None (caller falls back to existing
         name-only-signal / plain General handling).
    """
    org = parse_raw_org_name(raw_name)
    if not org:
        return None
    org_norm = apply_identity_phrase_rewrites(normalize_text(org))
    if not org_norm:
        return None

    if matches_any([SILENT_NAME_RELIGION_PATTERN], org_norm):
        # Religion -> General (never guess ethnicity from a religious marker).
        # No flag: across both gold sheets this fired 21x with 0 errors -- the
        # call was always correct, so the flag was pure reviewer fatigue.
        return (GENERAL_POP, "", "", "")
    if matches_any([SILENT_NAME_LANGUAGE_PATTERN], org_norm):
        return (GENERAL_POP, "", "",
                "Francophone/language organization name only - not an ethnic signal; verify served population")

    name_candidates = (
        extract_taxonomy_candidates(org_norm, taxonomy_entries)
        + extract_compound_candidates(org_norm)
        + extract_pattern_candidates(org_norm)
        + extract_country_candidates(org_norm)
        + extract_broad_identity_candidates(org_norm)
    )
    bipoc_hit = is_bipoc_real_target(org_norm)

    if not name_candidates and not bipoc_hit:
        return None

    distinct_l1 = set(c["level1"] for c in name_candidates)
    if bipoc_hit or len(distinct_l1) >= 2:
        return (MULTIPLE_ETHNIC, "", "", SILENT_NAME_FLAG)

    best = max(name_candidates, key=lambda c: c["depth"])
    return (best["level1"], best["level2"], best["level3"], SILENT_NAME_FLAG)


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

    Noise removal: "Ambiguous equity term with no paired ethnic signal",
    "Equity/diversity buzzword present alongside a real signal", and
    "Possible consulted-party mention (expert/advisor role)" no longer fire
    — check_grassroots_case() and EXPERT_ROLE_PHRASES stay defined and
    available for other callers; this function just stops emitting their
    note text.

    Context-only gating: Emphasis and 'Hindu' are CONTEXTUAL — verify-manually
    notes, not classification-relevant like negation/BIPOC — so only fire when
    the row actually resolved to something other than General. When
    resolved_label is None (caller not yet gating), they fire unconditionally,
    preserving prior behaviour for any other caller.
    """
    notes = []

    if re.search(r"\bcultural association\b", combined, re.IGNORECASE):
        notes.append("'Cultural Association' detected - verify named group manually")

    # Org candidates are last-resort; exclude them when computing whether a
    # real ethnic signal is present for the negation check below.
    primary_states = [s for s in states if s["source"] != "org_lookup"]

    is_general = resolved_label is not None and resolved_label == GENERAL_POP

    if primary_states and not is_general and re.search(r"\b(especially|particularly)\b", combined, re.IGNORECASE):
        notes.append(
            "\"Especially\"/\"particularly\" appears near the matched group - it may be "
            "one example within a broader population; confirm the classification isn't "
            "narrower (or broader) than intended"
        )

    if not is_general and re.search(r"\bhindu\b", combined, re.IGNORECASE):
        notes.append("'Hindu' detected — may imply South Asian/Indian origin; verify as religion vs. ethnicity")

    # Non-{group} negation: check if any matched candidate's ethnic keyword appears
    # immediately after "non-" in the text. Annotation only — does not suppress candidates.
    # Uses is_non_prefixed (the per-keyword path) rather than NEGATION_PHRASES (whole-text scan),
    # so "non-profit" cannot trigger it — only an actually matched ethnic term can.
    if primary_states and has_non_prefixed_negation(primary_states, combined):
        notes.append(
            "Matched term appears near a negation word (e.g. \"not\", \"excluding\") - "
            "confirm the population is served, not excluded"
        )

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
    # A signal must be corroborated in the body to classify.
    # The name is only consulted for a curated known-org lookup and to
    # decide whether a name-only signal should be flagged.
    # ------------------------------------------------------------------
    # extract_org_candidates is deliberately NOT part of this bundle: the
    # known-org map is a name-only last resort.
    # Consulting it on body text would let an org's self-reference in its
    # own description inject a definitive (non-role-tagged) org_lookup
    # candidate; name_org below is the only place it's consulted.
    def _extract(txt, name_for_role=""):
        return (
            extract_taxonomy_candidates(txt, taxonomy_entries, name_for_role)
            + extract_compound_candidates(txt, name_for_role)
            + extract_pattern_candidates(txt, name_for_role)
            + extract_country_candidates(txt, name_for_role)
            + extract_broad_identity_candidates(txt, name_for_role)
        )

    # name_text is passed through so a candidate whose body match merely
    # echoes the org's own name (e.g. an org restating its own name in its
    # description) is tagged role="org_name" (weak) instead of "served".
    body_candidates = _extract(body_text, name_text)
    # NaN-safe blank check: a pandas row's blank AN cell is a float NaN
    # (truthy in Python), not "" -- `row.get(col, "") or ""` was WRONG here
    # (its default only applies when the key is absent, never when the
    # value is NaN), so every real pandas row was treated as reviewed and
    # the arbiter never actually ran against live data. pd.isna() mirrors
    # the same guard normalize_text()/audit_evidence.py already use.
    an_val = row.get(STAKEHOLDER_REVIEWED_COL, "")
    stakeholder_reviewed = not pd.isna(an_val) and bool(str(an_val).strip())
    if not stakeholder_reviewed:
        body_candidates = apply_ml_role_arbiter(body_candidates)  # Phase B, off by default
    bipoc_present    = is_bipoc_real_target(body_text)   # BIPOC must be in the body
    name_org         = extract_org_candidates(name_text)  # curated known-org from the name
    name_signal      = bool(_extract(name_text)) or is_bipoc_real_target(name_text)

    # A body mention only corroborates when its role is "served". An org-name
    # echo (or provider/example/aspirational mention) is weak, NOT
    # corroboration: a body whose only ethnic mention is the org's own name
    # restated in an administrative sentence is administratively silent,
    # exactly like a body with no mention at all.
    served_body = [c for c in body_candidates if c.get("role", "served") == "served"]

    # True when EVERY served mention is the org naming itself -- i.e. the row
    # classifies only because we inferred the served population from the
    # organization's identity, never because the text said so. A single
    # ordinary served mention ("programming for Black youth") anywhere in the
    # body clears this, because then the claim is stated rather than inferred.
    self_id_only = bool(served_body) and all(c.get("self_id") for c in served_body)

    # Name-only / silent-body guard: no served signal in the body.
    if not served_body and not bipoc_present:
        if name_org:  # known org (e.g. Niginan) classifies -- tiny curated map first
            candidates = name_org
        else:
            # Generalizable silent-body name rule: a body with no served signal -- whether
            # truly empty OR carrying only a weak org-name echo of the org's
            # own identity -- classifies from the raw account-name identity
            # terms instead of defaulting flat to General.

            disclaimed = matches_any(IDENTITY_EXPANSION_DISCLAIMER_PATTERNS, body_text)
            name_rule = None
            if not disclaimed and not body_names_a_population(
                    _body_without_org_name(body_text, row.get("Funding Request Name", ""))):
                name_rule = classify_from_raw_name(row.get("Funding Request Name", ""), taxonomy_entries)
            if name_rule is not None:
                return name_rule
            if body_candidates:
                # Weak-only body (org-echo / provider / etc.) that the name
                # rule did not resolve: fall through so the resolver emits its
                # "mentioned in <role> context only" transparency note (General).
                candidates = body_candidates
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
    # Step 4b — French language accommodation filter
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
    # Hindu are gated to non-General rows — see extra_annotation_notes.
    # ------------------------------------------------------------------
    # ml_role_note already carries its own priority-appropriate prefix
    # (see apply_ml_role_arbiter's two-tier note text) — do not re-wrap it.
    ml_notes = [c["ml_role_note"] for c in states if c.get("ml_role_note")]
    notes = pre_notes + ml_notes + extra_annotation_notes(combined, states, bipoc_present, resolved_label=e1)

    # Self-identification provenance (see SELF_ID_FLAG). Gated to non-General
    # results: on a General row there is no inferred group for a reviewer to
    # check, so the note would be pure noise.
    if self_id_only and e1 != GENERAL_POP:
        notes.append(SELF_ID_FLAG)

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
    # De-duplicate before joining. Negation is detected TWICE by design, by two
    # deliberately different checks that emit byte-identical text:
    #   * build_context_notes()        -- whole-text negation-phrase scan,
    #                                     already embedded in `flag` by resolve()
    #   * has_non_prefixed_negation()  -- per-keyword "non-<ethnicity>" check,
    #                                     arriving here via extra_annotation_notes()
    # A row that trips both (a general negation phrase AND a "non-<group>"
    # construction) would otherwise print the same sentence twice. It is
    # data-dependent (only fires when both checks match), not a fixed case.
    #
    # Compared by whole-string containment rather than by splitting on ";" --
    # some notes legitimately contain a semicolon (the "especially"/"particularly"
    # note does), so splitting would fragment them and defeat the comparison.
    deduped, seen = [], []
    for n in notes:
        if n and n not in flag and n not in seen:
            seen.append(n)
            deduped.append(n)
    if deduped:
        note_text = "; ".join(deduped)
        flag = f"{flag}; {note_text}" if flag else note_text

    return (e1, e2, e3, flag)


# ---------------------------------------------------------------------------
# ADDITIVE LAYER 3 — Multi-identity marker collector (string-safe).
#
# Purely additive and read-only: does NOT touch classify_row, the resolver,
# or any existing label/flag. It re-runs the SAME body extraction classify_row
# performs and returns the distinct SERVED ethnic-group tags, so a row the
# resolver collapses to the single string "Multiple Ethnic and Cultural
# Origins" can still expose WHICH specific groups were matched. The caller
# (generate_review_report.py) comma-joins these into the new, non-breaking
# `multi_identity_markers` column for intersectional visibility. Existing
# outputs and downstream consumers are unaffected.
# ---------------------------------------------------------------------------

def identity_markers(row, taxonomy_entries):
    """Distinct served ethnic-group tags detected in the BODY (deepest label
    per group), mirroring classify_row's served-candidate set. Never
    classifies; feeds the additive `multi_identity_markers` column only."""
    body_text, name_text = get_body_and_name_texts(row)
    if not body_text.strip():
        return []
    candidates = (
        extract_taxonomy_candidates(body_text, taxonomy_entries, name_text)
        + extract_compound_candidates(body_text, name_text)
        + extract_pattern_candidates(body_text, name_text)
        + extract_country_candidates(body_text, name_text)
        + extract_broad_identity_candidates(body_text, name_text)
    )
    # Same "served role corroborates, weak roles do not" gate classify_row uses.
    served = [c for c in candidates if c.get("role", "served") == "served"]
    markers = []
    seen = set()
    for c in served:
        label = c["level3"] or c["level2"] or c["level1"]
        if label and label not in seen:
            seen.add(label)
            markers.append(label)
    if is_bipoc_real_target(body_text) and "BIPOC" not in seen:
        markers.append("BIPOC")
    return markers
