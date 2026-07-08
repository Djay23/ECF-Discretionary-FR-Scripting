import re
import sys
import time
import pandas as pd
from openpyxl import load_workbook
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # Engine 1 and 2
import bootstrap

from ethnic_taggerv3 import (
    normalize_text,
    get_body_and_name_texts,
    matches_any,
    is_negated,
    is_example_mention,
    _echoes_org_name,
)
from constants import ASPIRATIONAL_PHRASES

from gender_constants import (
    # Gender identity labels
    GENDER_WOMEN_GIRLS, GENDER_MEN_BOYS, GENDER_TWO_SPIRIT,
    GENDER_OTHER, GENDER_MULTIPLE, GENDER_GENERAL_POP,
    # Gender output columns
    OUTPUT_GENDER, OUTPUT_GENDER_FLAG,
    # Gender term data
    IDENTITY_KEY_TO_LABEL, IDENTITY_KEY_SHORT_LABEL,
    GENDER_TERM_PATTERNS,
    BARE_QUEER_PATTERN, BARE_TRANS_PATTERN, GENDER_QUEER_CONTEXT,
    UMBRELLA_ACRONYM_PATTERN,
    # Gender flags
    FLAG_ASPIRATIONAL, FLAG_TWO_SPIRIT_INDIG, FLAG_NEGATION, FLAG_UMBRELLA_ACRONYM,
    FLAG_ORG_NAME, FLAG_AMBIGUOUS_TERM,
    # Org-name and ambiguous-term data
    ORG_NAME_CONTEXT_PATTERNS, AMBIGUOUS_CODED_TERMS,
    # Sexual identity labels
    SEXUAL_2SLGBTQIA, SEXUAL_GENERAL_POP,
    # Sexual output columns
    OUTPUT_SEXUAL, OUTPUT_SEXUAL_FLAG,
    # Sexual term data
    SEXUAL_GENDER_DIVERSE_PATTERNS, SEXUAL_ORIENTATION_PATTERNS,
    # Sexual flags
    SFLAG_NEGATION, SFLAG_GENDER_TERM, SFLAG_ASPIRATIONAL,
)

"""
Gender_SexID.py
---------------
Gender Identity + Sexual Identity classifiers — standalone script.

Reads:   "Data Sheets/FR testing.xlsx"  →  sheet "Discretionary Funding Requests"
Writes:  four columns back into the same workbook (openpyxl header-lookup):
           Gender Id - FR9       Gender Classification Flag
           Sexual Id - FR10      Sexual Classification Flag

Architecture:
    All data (labels, patterns, flag strings) lives in gender_constants.py.
    Generic text helpers (normalize_text, is_negated, etc.) are imported
    from ethnic_taggerv3.py — not copied.

Public API (imported by generate_review_report.py):
    classify_gender(row)  → (label: str, flag: str)
    classify_sexual(row)  → (label: str, flag: str)
    GENDER_GENERAL_POP, GENDER_MULTIPLE
    SEXUAL_2SLGBTQIA, SEXUAL_GENERAL_POP

Pipeline — Gender:
    1. get_body_and_name_texts() → normalize → extract_gender_candidates() on
       the body; a name-only signal degrades to General + FLAG_ORG_NAME
    2. resolve_gender() : 0 keys → General Pop, 1 → that group, 2+ → Multiple

Pipeline — Sexual:
    1. same body/name split → extract_sexual_candidates()
    2. resolve_sexual() : any guarded body signal → 2SLGBTQIA+, else General Pop
       (name-only signal → General Pop + FLAG_ORG_NAME)

To Run:
    python Gender_SexID.py
"""

DATA_SHEET = "Discretionary Funding Requests"

# ===========================================================================
# ORG-NAME CONTEXT DETECTOR
# ===========================================================================

def is_org_name_context(text):
    """
    Return True when any ORG_NAME_CONTEXT_PATTERNS fires on normalized text,
    indicating a gender/sexual term appears inside an organizational construct.
    Classification is kept; caller appends FLAG_ORG_NAME as an annotation.
    """
    return matches_any(ORG_NAME_CONTEXT_PATTERNS, text)

# ===========================================================================
# GENDER IDENTITY — extraction + resolver
# ===========================================================================

def extract_gender_candidates(text, name_text=""):
    """
    Scan normalized text for gender-identity terms.

    Returns
    -------
    keys: set[str]  — accepted identity keys
    org_echo_keys: set[str]  — subset of keys whose match merely echoes the
        org's own name inside the body (Plan.md Fix 1 Phase 2 — e.g. "Black
        Canadian Women in Action is undertaking..." repeating the org name
        in the description) rather than describing a served population.
    flags_out: set[str]  — annotation flag strings triggered by this text
    any_negated : bool — True if any negation encountered (→ FLAG_NEGATION)
    """
    keys = set()
    keys_with_served_occurrence = set()
    flags_out = set()
    any_negated = False

    # Standard (unambiguous) patterns.
    # Scan ALL occurrences (not just the first) so that when a term appears
    # more than once -- e.g. an org restates its own name ("Edmonton Women's
    # Shelter provides...") AND separately describes who it serves ("...for
    # women fleeing violence") -- a later served occurrence rescues the key
    # even if an earlier occurrence was an org-name echo.
    for pattern, identity_key, extra_flag_key in GENDER_TERM_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            term = m.group(0)
            if is_negated(term, text):
                any_negated = True
                continue
            if is_example_mention(term, text):
                continue
            keys.add(identity_key)
            if not (name_text and _echoes_org_name(text, m.start(), m.end(), name_text)):
                keys_with_served_occurrence.add(identity_key)

    org_echo_keys = keys - keys_with_served_occurrence

    # Bare "queer" — ambiguity check
    # \bqueer\b fires on "queer youth" AND on "gender queer community".
    # Suppress the ambiguity flag when "queer" is part of "gender queer".
    for m in re.finditer(BARE_QUEER_PATTERN, text, re.IGNORECASE):
        term = m.group(0)
        if is_negated(term, text) or is_example_mention(term, text):
            any_negated = True
            continue
        prefix = text[max(0, m.start() - 8) : m.start()].rstrip()
        if prefix.lower().endswith("gender") or prefix.lower().endswith("gender-"):
            continue  # already captured by the "gender queer" standard pattern
        keys.add("genderqueer")

    # Bare "trans" — false-positive risk
    # \btrans\b cannot match inside "transgender" (no \b between 's' and 'g').
    for m in re.finditer(BARE_TRANS_PATTERN, text, re.IGNORECASE):
        term = m.group(0)
        if is_negated(term, text) or is_example_mention(term, text):
            any_negated = True
            continue
        keys.add("transgender")

    # 2SLGBTQIA+ umbrella acronym — implies gender-diverse identity on the gender axis.
    # "2S" prefix additionally adds two_spirit (Two-Spirit is explicitly named in the acronym).
    # resolve_gender short-circuits lgbtq_umbrella → GENDER_MULTIPLE regardless of key count.
    for m in re.finditer(UMBRELLA_ACRONYM_PATTERN, text, re.IGNORECASE):
        term = m.group(0)
        if is_negated(term, text) or is_example_mention(term, text):
            any_negated = True
            continue
        keys.add("lgbtq_umbrella")
        if term.lower().startswith("2s"):
            keys.add("two_spirit")
        flags_out.add(FLAG_UMBRELLA_ACRONYM)

    # Ambiguous coded terms (femme/masc/butch/stud) — flag only, no key added.
    # These terms are gender-coded AND orientation-adjacent; reviewer checks both axes.
    for pattern in AMBIGUOUS_CODED_TERMS:
        m = re.search(pattern, text, re.IGNORECASE)
        if not m:
            continue
        term = m.group(0)
        if is_negated(term, text) or is_example_mention(term, text):
            continue
        flags_out.add(FLAG_AMBIGUOUS_TERM)

    return keys, org_echo_keys, flags_out, any_negated

def resolve_gender(keys, flags_set, any_negated, aspirational):
    """
    0 keys          → General Population (No specific gender served)
    lgbtq_umbrella  → Multiple gender identities (always — acronym spans identities)
    1 other key     → that key's output group label
    2+ other keys   → Multiple gender identities  (flag lists which identities)
    Annotation flags are appended; they never change the branch.

    Fix 6: Aspirational is a contextual flag (verify-manually), not
    classification-relevant like negation/BIPOC/two-spirit — it only fires
    once the row has actually resolved to a specific group, not General.
    """
    flag_parts = sorted(flags_set)

    if any_negated:
        flag_parts.append(FLAG_NEGATION)
    if "two_spirit" in keys:
        flag_parts.append(FLAG_TWO_SPIRIT_INDIG)

    if not keys:
        return GENDER_GENERAL_POP, "; ".join(flag_parts)

    if aspirational:
        flag_parts.append(FLAG_ASPIRATIONAL)

    # LGBTQ family acronym → always Multiple regardless of other keys present.
    # The acronym inherently spans multiple gender identities; name the source in the flag.
    if "lgbtq_umbrella" in keys:
        other_short = sorted(IDENTITY_KEY_SHORT_LABEL[k] for k in keys if k != "lgbtq_umbrella")
        if other_short:
            label_list = ["2SLGBTQIA+ umbrella"] + other_short
        else:
            label_list = ["2SLGBTQIA+ umbrella acronym"]
        flag_parts.insert(0, f"Multiple: {', '.join(label_list)}")
        return GENDER_MULTIPLE, "; ".join(flag_parts)

    # 'gender-diverse' is a distinct concept (Plan.md Fix 2a), not a single
    # identity — it always routes to Multiple, same short-circuit shape as
    # the 2SLGBTQIA+ umbrella acronym above.
    if "gender_diverse" in keys:
        other_short = sorted(
            IDENTITY_KEY_SHORT_LABEL[k] for k in keys if k != "gender_diverse"
        )
        label_list = ["gender-diverse"] + other_short
        flag_parts.insert(0, f"Multiple: {', '.join(label_list)}")
        return GENDER_MULTIPLE, "; ".join(flag_parts)

    if len(keys) == 1:
        return IDENTITY_KEY_TO_LABEL[next(iter(keys))], "; ".join(flag_parts)

    short_names = sorted(IDENTITY_KEY_SHORT_LABEL[k] for k in keys)
    flag_parts.insert(0, f"Multiple: {', '.join(short_names)}")
    return GENDER_MULTIPLE, "; ".join(flag_parts)


def classify_gender(row):
    """Public entry point — gender identity classification for a single row.

    A signal must be corroborated in the body to classify (Plan.md D1); a
    name-only signal degrades to General Population + FLAG_ORG_NAME. A body
    mention that only echoes the org's own name (Plan.md Fix 1 Phase 2, e.g.
    "Black Canadian Women in Action is undertaking...") is not corroboration
    either — it degrades to General + a transparency note.
    """
    body_text, name_text = get_body_and_name_texts(row)
    if not (body_text + name_text).strip():
        return GENDER_GENERAL_POP, ""
    body = normalize_text(body_text)
    name = normalize_text(name_text)
    keys, org_echo_keys, flags_set, any_negated = extract_gender_candidates(body, name_text=name)
    served_keys = keys - org_echo_keys
    # Body is truly silent of served signal (no served keys, no
    # ambiguous-term/negation annotation) — only then does a name-only or
    # org-echo-only signal matter.
    if not served_keys and not flags_set and not any_negated:
        if org_echo_keys:
            groups = sorted(IDENTITY_KEY_SHORT_LABEL[k] for k in org_echo_keys)
            note = (
                "Note (low priority): " + ", ".join(groups)
                + " mentioned via org-name self-reference in body - not classified; verify"
            )
            return GENDER_GENERAL_POP, note
        name_keys, _, _, _ = extract_gender_candidates(name)
        if name_keys:
            return GENDER_GENERAL_POP, FLAG_ORG_NAME
        return GENDER_GENERAL_POP, ""
    if served_keys and is_org_name_context(body):
        flags_set.add(FLAG_ORG_NAME)
    aspirational = matches_any(ASPIRATIONAL_PHRASES, body)
    return resolve_gender(served_keys, flags_set, any_negated, aspirational)

# ===========================================================================
# SEXUAL IDENTITY — extraction + resolver
# ===========================================================================

def extract_sexual_candidates(text):
    """
    Presence-only scan — any single guarded signal is enough.

    Returns
    -------
    found: bool — at least one signal survived guards
    found_gender_diverse: bool — at least one gender-diverse term survived guards
        (SFLAG_GENDER_TERM fires whenever this is True, even alongside orientation terms)
    any_negated : bool — at least one negation encountered
    example_suppressed : bool — at least one term was dropped ONLY because it
        appeared in an example/illustrative context ("...groups such as
        2SLGBTQIA+..."), Plan.md Fix 7 — the caller surfaces this as a
        transparency note instead of silently dropping it with no trace.
    """
    found_gender_diverse = False
    found_orientation = False
    any_negated = False
    example_suppressed = False

    for pattern in SEXUAL_GENDER_DIVERSE_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if not m:
            continue
        term = m.group(0)
        if is_negated(term, text):
            any_negated = True
            continue
        if is_example_mention(term, text):
            example_suppressed = True
            continue
        found_gender_diverse = True

    for pattern in SEXUAL_ORIENTATION_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if not m:
            continue
        term = m.group(0)
        if is_negated(term, text):
            any_negated = True
            continue
        if is_example_mention(term, text):
            example_suppressed = True
            continue
        found_orientation = True

    found = found_gender_diverse or found_orientation
    return found, found_gender_diverse, any_negated, example_suppressed

def resolve_sexual(found, found_gender_diverse, any_negated, aspirational, example_suppressed=False):
    """
    found → 2SLGBTQIA+; else → General Population.
    SFLAG_GENDER_TERM fires whenever a gender-diverse term contributed (not only
    when it was the exclusive signal), so every inference from a gender term is
    surfaced for reviewer verification.
    Flags are annotations only — they never change the branch.

    Fix 6: Aspirational is a contextual flag — it only fires once the row
    has actually resolved to 2SLGBTQIA+, not General.
    Fix 7: when the only signal was example-suppressed, keep General but
    name what was dropped instead of silently discarding it with no trace.
    """
    flag_parts = []

    if found:
        if found_gender_diverse:
            flag_parts.append(SFLAG_GENDER_TERM)
        if any_negated:
            flag_parts.append(SFLAG_NEGATION)
        if aspirational:
            flag_parts.append(SFLAG_ASPIRATIONAL)
        return SEXUAL_2SLGBTQIA, "; ".join(flag_parts)

    if example_suppressed:
        flag_parts.append(
            "Note (low priority): 2SLGBTQIA+ mentioned in example/illustrative "
            "context - not classified; verify"
        )
    if any_negated:
        flag_parts.append(SFLAG_NEGATION)
    return SEXUAL_GENERAL_POP, "; ".join(flag_parts)

def classify_sexual(row):
    """Public entry point — sexual identity classification for a single row.

    A signal must be corroborated in the body to classify (Plan.md D1); a
    name-only signal degrades to General Population + FLAG_ORG_NAME.
    """
    body_text, name_text = get_body_and_name_texts(row)
    if not (body_text + name_text).strip():
        return SEXUAL_GENERAL_POP, ""
    body = normalize_text(body_text)
    name = normalize_text(name_text)
    found, found_gender_diverse, any_negated, example_suppressed = extract_sexual_candidates(body)
    # Body is truly silent (no signal, no negation, no example-suppressed
    # mention) — only then does a name-only signal matter.
    if not found and not any_negated and not example_suppressed:
        name_found, *_ = extract_sexual_candidates(name)
        if name_found:
            return SEXUAL_GENERAL_POP, FLAG_ORG_NAME
        return SEXUAL_GENERAL_POP, ""
    aspirational = matches_any(ASPIRATIONAL_PHRASES, body)
    label, flag = resolve_sexual(found, found_gender_diverse, any_negated, aspirational, example_suppressed)
    if found and is_org_name_context(body):
        flag = "; ".join(p for p in [FLAG_ORG_NAME, flag] if p)
    return label, flag

# ===========================================================================
# main() — writes both classifiers to FR testing.xlsx in one workbook pass
# ===========================================================================

def main():
    start_time = time.time()

    funding_filepath = bootstrap.PROJECT_ROOT / "Data Sheets" / "FR testing.xlsx"

    print(f"Loading funding requests from: {funding_filepath}")
    if not funding_filepath.exists():
        print(f"Error: data workbook not found at '{funding_filepath}'.")
        print(f"Place the file at: {bootstrap.PROJECT_ROOT / 'Data Sheets' / 'FR testing.xlsx'} "
              f"(sheet '{DATA_SHEET}').")
        sys.exit(1)
    try:
        data_df = pd.read_excel(funding_filepath, sheet_name=DATA_SHEET, dtype=str)
    except Exception as e:
        print(f"Error loading data sheet '{DATA_SHEET}' from '{funding_filepath}': {e}")
        sys.exit(1)

    print(f"Data rows: {len(data_df)}")

    for col in [OUTPUT_GENDER, OUTPUT_GENDER_FLAG, OUTPUT_SEXUAL, OUTPUT_SEXUAL_FLAG]:
        if col not in data_df.columns:
            data_df[col] = ""

    stats = {
        "-Gender → Women & Girls": 0, "-Gender → Men & Boys": 0, "-Gender → Two Spirit": 0,
        "-Gender → Other": 0, "-Gender → Multiple": 0, "-Gender → General": 0,
        "-Sexual → 2SLGBTQIA": 0, "-Sexual → General": 0,
        "-Flagged → Gender": 0, "-Flagged → Sexual": 0,
    }

    for idx, row in data_df.iterrows():
        g_label, g_flag = classify_gender(row)
        s_label, s_flag = classify_sexual(row)

        data_df.at[idx, OUTPUT_GENDER]      = g_label
        data_df.at[idx, OUTPUT_GENDER_FLAG] = g_flag
        data_df.at[idx, OUTPUT_SEXUAL]      = s_label
        data_df.at[idx, OUTPUT_SEXUAL_FLAG] = s_flag

        if   g_label == GENDER_WOMEN_GIRLS: stats["-Gender → Women & Girls"] += 1
        elif g_label == GENDER_MEN_BOYS:    stats["-Gender → Men & Boys"]    += 1
        elif g_label == GENDER_TWO_SPIRIT:  stats["-Gender → Two Spirit"]  += 1
        elif g_label == GENDER_OTHER:       stats["-Gender → Other"]       += 1
        elif g_label == GENDER_MULTIPLE:    stats["-Gender → Multiple"]    += 1
        else:                               stats["-Gender → General"]     += 1

        if s_label == SEXUAL_2SLGBTQIA:     stats["-Sexual → 2SLGBTQIA"]  += 1
        else:                               stats["-Sexual → General"]     += 1

        if g_flag: stats["-Flagged → Gender"]  += 1
        if s_flag: stats["-Flagged → Sexual"]  += 1

    # Write-back via openpyxl header-lookup (never assumes column positions)
    wb = load_workbook(funding_filepath)
    ws = wb[DATA_SHEET]
    headers = {cell.value: cell.column for cell in ws[1]}

    for col_name in [OUTPUT_GENDER, OUTPUT_GENDER_FLAG, OUTPUT_SEXUAL, OUTPUT_SEXUAL_FLAG]:
        if col_name not in headers:
            new_col = ws.max_column + 1
            ws.cell(row=1, column=new_col, value=col_name)
            headers[col_name] = new_col

    for i, (idx, _row) in enumerate(data_df.iterrows(), start=2):
        ws.cell(row=i, column=headers[OUTPUT_GENDER],      value=data_df.at[idx, OUTPUT_GENDER])
        ws.cell(row=i, column=headers[OUTPUT_GENDER_FLAG], value=data_df.at[idx, OUTPUT_GENDER_FLAG])
        ws.cell(row=i, column=headers[OUTPUT_SEXUAL],      value=data_df.at[idx, OUTPUT_SEXUAL])
        ws.cell(row=i, column=headers[OUTPUT_SEXUAL_FLAG], value=data_df.at[idx, OUTPUT_SEXUAL_FLAG])

    wb.save(funding_filepath)

    print("\nResults:")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print(f"\nOutput written to: {funding_filepath}")
    elapsed = time.time() - start_time
    print(f"Gender + Sexual classification completed in {elapsed:.1f} seconds.")

if __name__ == "__main__":
    main()
