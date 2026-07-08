"""
import_review_audit.py
----------------------
One-time migration: convert a hand-audited review report into the structured
gold format that audit_score.py scores.

The auditor added a single freeform column 'Correct Sex & Gender' to the
'Audit Detail' tab of review_report(Gender and Sex).xlsx. This script parses
those notes into audit_score.py's structured columns, joining to the engine
baseline (which carries the stable ID) on Funding Request Name.

Writes:  Data Sheets/audit_gold_prefilled.xlsx   (never overwrites audit_gold.xlsx)
Run:
    python import_review_audit.py
    python import_review_audit.py --review "Data Sheets/review_report(Gender and Sex).xlsx"
"""

import sys
import re
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # Engine 1 and 2
import bootstrap

import pandas as pd

import ethnic_taggerv3 as et
import audit_score as asc            # reuse loaders, classifiers, column constants
from gender_constants import (
    GENDER_GENERAL_POP, GENDER_MULTIPLE, GENDER_WOMEN_GIRLS, GENDER_MEN_BOYS,
    GENDER_TWO_SPIRIT, GENDER_OTHER, SEXUAL_2SLGBTQIA, SEXUAL_GENERAL_POP,
)

# --- config ---------------------------------------------------------------
DEFAULT_REVIEW     = bootstrap.PROJECT_ROOT / "Taxonomy" / "review_report(Gender and Sex).xlsx"
AUDIT_DETAIL_SHEET = "Audit Detail"
NOTE_COL           = "Correct Sex & Gender"
OUT_FILE           = bootstrap.PROJECT_ROOT / "Data Sheets" / "audit_gold_prefilled.xlsx"

# Review-report label columns (the labels the auditor actually saw / approved)
RR_NAME   = "Funding Request Name"
RR_GENDER = "Gender Id"
RR_SEXUAL = "Sexual Id"


def clean(v):
    """NaN/None -> '' ; otherwise stripped string."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    s = str(v)
    return "" if s.lower() == "nan" else s.strip()


def norm(v):
    """lowercase + collapse whitespace, for keyword checks."""
    return re.sub(r"\s+", " ", clean(v)).strip().lower()


def map_gender_label(text):
    """Free-text target phrase -> canonical gender label, or None if unclear."""
    t = norm(text)
    if "general" in t:                                              return GENDER_GENERAL_POP
    if "multiple" in t:                                             return GENDER_MULTIPLE
    if "two" in t and "spirit" in t:                                return GENDER_TWO_SPIRIT
    if any(k in t for k in ("women", "girl", "female", "mother")): return GENDER_WOMEN_GIRLS
    if any(k in t for k in ("men", "boy", "male", "father")):      return GENDER_MEN_BOYS
    if "other" in t:                                                return GENDER_OTHER
    return None


def map_sexual_label(text):
    """Free-text target phrase -> canonical sexual label, or None if unclear."""
    t = norm(text)
    if "general" in t:                                             return SEXUAL_GENERAL_POP
    if any(k in t for k in ("2slgbtqia", "2slgbtq", "lgbtq")):    return SEXUAL_2SLGBTQIA
    return None


def parse_note(note, rr_gender, rr_sexual):
    """
    Parse one freeform 'Correct Sex & Gender' cell into structured cells.
    rr_gender / rr_sexual = labels the auditor saw in the review report (used for YES).
    Returns dict with keys: correct_gender, correct_sexual,
                            gender_flag_ok, sexual_flag_ok, notes.
    Conservative: when axis/label is unclear, leave Correct blank and dump note
    into Notes for human finalization. Never invent a correct answer.
    """
    out = {"correct_gender": "", "correct_sexual": "",
           "gender_flag_ok": "", "sexual_flag_ok": "", "notes": ""}
    raw = clean(note)
    t = norm(raw)
    if not t:
        return out

    verdict = t.split()[0].strip(" -:")            # yes / no / i / unsure ...
    hedged  = t.startswith("i guess") or verdict in ("i", "unsure", "maybe")

    if hedged:
        out["notes"] = raw
        return out

    if verdict in ("yes", "y", "correct"):
        # engine (as the auditor saw it) was right on both axes
        out["correct_gender"] = clean(rr_gender)
        out["correct_sexual"] = clean(rr_sexual)
        if "flag" in t:                            # e.g. "YES - Should flag Femme"
            out["notes"] = raw
        return out

    if verdict in ("no", "n", "incorrect"):
        out["notes"] = raw                         # always keep the note for review
        flaggy = "flag" in t                       # "Flag <org>" -> words are a name, not a label
        gl = None if flaggy else map_gender_label(raw)
        sl = None if flaggy else map_sexual_label(raw)

        explicit_gender = "gender" in t
        explicit_sexual = any(k in t for k in ("sexual", "lgbtq", "2slgbtq", "orientation"))

        g_specific = norm(rr_gender) not in ("", norm(GENDER_GENERAL_POP))
        s_specific = norm(rr_sexual) not in ("", norm(SEXUAL_GENERAL_POP))

        # attribute the correction to the named axis, or (if none named) to the
        # single axis the engine actually populated with a specific label.
        target_gender = explicit_gender or (not explicit_sexual and g_specific and not s_specific)
        target_sexual = explicit_sexual or (not explicit_gender and s_specific and not g_specific)

        wants_general = "general" in t
        if target_gender:
            out["correct_gender"] = gl or (GENDER_GENERAL_POP if (wants_general or flaggy) else "")
        if target_sexual:
            out["correct_sexual"] = sl or (SEXUAL_GENERAL_POP if (wants_general or flaggy) else "")
        return out

    out["notes"] = raw                             # unknown verdict -> safe
    return out


def main():
    ap = argparse.ArgumentParser(description="Migrate review-report audit -> gold prefill")
    ap.add_argument("--review",   default=str(DEFAULT_REVIEW), help="Annotated review report path")
    ap.add_argument("--sheet",    default=AUDIT_DETAIL_SHEET)
    ap.add_argument("--note-col", default=NOTE_COL)
    args = ap.parse_args()

    # 1. Engine baseline (stable IDs + current engine output) — reuse audit_score
    print("Running classifiers for engine baseline...")
    tax_df, data_df  = asc.load_inputs()
    taxonomy_entries = et.build_taxonomy(tax_df)
    engine_df, skipped = asc._run_classifiers(data_df, taxonomy_entries)
    if skipped:
        print(f"  Skipped {skipped} rows missing '{asc.STABLE_ID_COL}'.")

    # 2. Load annotated 'Audit Detail' tab; keep only rows with a non-empty note
    print(f"Loading annotations: {args.review} [{args.sheet}]")
    rr = pd.read_excel(args.review, sheet_name=args.sheet, dtype=str)
    if args.note_col not in rr.columns:
        print(f"ERROR: column '{args.note_col}' not found in sheet '{args.sheet}'.")
        sys.exit(1)
    rr = rr[rr[args.note_col].apply(lambda v: clean(v) != "")]
    print(f"  {len(rr)} annotated rows.")

    # 3. Build the gold template exactly like audit_score.cmd_init
    gold = engine_df[[
        asc.STABLE_ID_COL, "Funding Request Name",
        asc.ENG_ETHNIC1, asc.ENG_ETHNIC2, asc.ENG_ETHNIC3,
        asc.ENG_GENDER, asc.ENG_SEXUAL,
        asc.ENG_ETHNIC_FLAG, asc.ENG_GENDER_FLAG, asc.ENG_SEXUAL_FLAG,
    ]].copy()
    for col in [asc.CORRECT_ETHNIC1, asc.CORRECT_GENDER, asc.CORRECT_SEXUAL,
                asc.ETHNIC_FLAG_OK, asc.GENDER_FLAG_OK, asc.SEXUAL_FLAG_OK, asc.NOTES_COL]:
        gold[col] = ""

    gold_names = gold["Funding Request Name"].apply(norm)
    name_counts = gold_names.value_counts()
    dup_names = set(name_counts[name_counts > 1].index)

    matched = unmatched = dup_skipped = 0
    filled_g = filled_s = 0
    for _, arow in rr.iterrows():
        name = norm(arow.get(RR_NAME, ""))
        if not name:
            unmatched += 1
            continue
        if name in dup_names:
            dup_skipped += 1
            print(f"  DUPLICATE NAME (skipped, no stable id to disambiguate): {arow.get(RR_NAME)!r}")
            continue
        sel = gold_names == name
        if not sel.any():
            unmatched += 1
            print(f"  UNMATCHED: {arow.get(RR_NAME)!r}")
            continue

        parsed = parse_note(arow.get(args.note_col, ""),
                            arow.get(RR_GENDER, ""), arow.get(RR_SEXUAL, ""))
        idx = gold[sel].index[0]
        if parsed["correct_gender"]:
            gold.at[idx, asc.CORRECT_GENDER] = parsed["correct_gender"]; filled_g += 1
        if parsed["correct_sexual"]:
            gold.at[idx, asc.CORRECT_SEXUAL] = parsed["correct_sexual"]; filled_s += 1
        if parsed["gender_flag_ok"]:
            gold.at[idx, asc.GENDER_FLAG_OK] = parsed["gender_flag_ok"]
        if parsed["sexual_flag_ok"]:
            gold.at[idx, asc.SEXUAL_FLAG_OK] = parsed["sexual_flag_ok"]
        if parsed["notes"]:
            gold.at[idx, asc.NOTES_COL] = parsed["notes"]
        matched += 1

    # 4. Write the prefilled gold (distinct name — never clobber audit_gold.xlsx)
    gold.to_excel(OUT_FILE, index=False)

    # Post-write: certain pandas/openpyxl version combinations inject a
    # synthetic "Column1, Column2, ..." row above the real headers.
    # Detect and remove it so row 1 always contains the real column names.
    from openpyxl import load_workbook as _load_wb
    _wb = _load_wb(OUT_FILE)
    _ws = _wb.active
    _first = [str(_c.value or "") for _c in _ws[1]]
    if all((_v.startswith("Column") and _v[6:].isdigit()) for _v in _first if _v):
        _ws.delete_rows(1)
        _wb.save(OUT_FILE)

    # 5. Summary + caveats
    print(f"\nWritten {len(gold)} rows -> {OUT_FILE}")
    print(f"  annotated: {len(rr)} | matched: {matched} | unmatched: {unmatched} | dup-name skipped: {dup_skipped}")
    print(f"  auto-filled Correct Gender Id: {filled_g} | Correct Sexual Id: {filled_s}")
    print(f"  left blank for manual finalization: gender {matched - filled_g}, sexual {matched - filled_s}")
    print("\nCAVEATS:")
    print("  Pre-fill is heuristic (~80%); review blank/ambiguous rows before renaming to audit_gold.xlsx.")
    print("  Recall reflects only the General-Population rows you sampled, not the whole dataset.")
    print("\nNext: finalize blanks, rename to 'audit_gold.xlsx', then run: python audit_score.py")


if __name__ == "__main__":
    main()
