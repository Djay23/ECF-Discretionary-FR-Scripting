"""
import_review_audit.py
---------------------
Migrates hand-audit annotations from the 'Correct Sex & Gender' freeform
column in review_report(Gender and Sex).xlsx into the structured columns that
audit_score.py expects, producing Data Sheets/audit_gold_prefilled.xlsx.

Workflow:
  1. Re-run classifiers on all rows that have a stable ID, producing the
     same gold template that audit_score.py --init would create (in-memory
     only — audit_gold.xlsx is never touched).
  2. Load the Audit Detail tab of the review report and extract the 57 rows
     that carry a 'Correct Sex & Gender' annotation.
  3. Left-join annotated rows onto the gold template by Funding Request Name.
     Unmatched rows (no stable ID) and ambiguous joins (duplicate name) are
     printed, not silently dropped.
  4. Parse each freeform note into structured columns (heuristic):
       Leading YES   -> engine label is correct; note -> Notes
       Leading NO    -> attempt to map phrase to canonical label constant
       Unsure/blank  -> leave blank (needs manual finalization)
  5. Write Data Sheets/audit_gold_prefilled.xlsx.
     Never modifies FR testing.xlsx or an existing audit_gold.xlsx.

Caveat: the single 'Correct Sex & Gender' column conflates gender, sexual,
and flag-adequacy in free text, so parsing is lossy (~93% auto-fill in the
current dataset; rows marked 'needs-review' or 'uncertain' need a manual
pass).  Review the Parse Status column, finalize as needed, rename to
audit_gold.xlsx, then run:  python audit_score.py

To Run:
    python import_review_audit.py
"""

import sys
import re
from collections import defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bootstrap

import ethnic_taggerv3 as et
from classify_pipeline import classify_row as pipeline_classify_row
import Gender_SexID as gs

from gender_constants import GENDER_GENERAL_POP, GENDER_MULTIPLE
from Gender_SexID import SEXUAL_2SLGBTQIA

# ---------------------------------------------------------------------------
# Column name constants (kept in sync with audit_score.py)
# ---------------------------------------------------------------------------
STABLE_ID_COL   = "SF_18_ID_Funding_Request__c"
ENG_ETHNIC1     = "Ethnic 1 (engine)"
ENG_ETHNIC2     = "Ethnic 2 (engine)"
ENG_ETHNIC3     = "Ethnic 3 (engine)"
ENG_GENDER      = "Gender Id (engine)"
ENG_SEXUAL      = "Sexual Id (engine)"
ENG_ETHNIC_FLAG = "Classification Flag (engine)"
ENG_GENDER_FLAG = "Gender Flag (engine)"
ENG_SEXUAL_FLAG = "Sexual Flag (engine)"
CORRECT_ETHNIC1 = "Correct Ethnic 1"
CORRECT_GENDER  = "Correct Gender Id"
CORRECT_SEXUAL  = "Correct Sexual Id"
ETHNIC_FLAG_OK  = "Ethnic Flag OK?"
GENDER_FLAG_OK  = "Gender Flag OK?"
SEXUAL_FLAG_OK  = "Sexual Flag OK?"
NOTES_COL       = "Notes"
PARSE_STATUS_COL = "Parse Status"

ANNOTATION_COL     = "Correct Sex & Gender"
AUDIT_DETAIL_SHEET = "Audit Detail"

REVIEW_REPORT = bootstrap.PROJECT_ROOT / "Data Sheets" / "review_report(Gender and Sex).xlsx"
GOLD_FILE     = bootstrap.PROJECT_ROOT / "Data Sheets" / "audit_gold.xlsx"
PREFILL_FILE  = bootstrap.PROJECT_ROOT / "Data Sheets" / "audit_gold_prefilled.xlsx"


# ---------------------------------------------------------------------------
# Classifier runner (mirrors audit_score._run_classifiers)
# ---------------------------------------------------------------------------

def _run_classifiers(data_df, taxonomy_entries):
    rows = []
    skipped = 0
    for _, row in data_df.iterrows():
        sid = row.get(STABLE_ID_COL, "")
        if pd.isna(sid) or not str(sid).strip():
            skipped += 1
            continue
        e1, e2, e3, eflag = pipeline_classify_row(row, taxonomy_entries)
        g_label, g_flag   = gs.classify_gender(row)
        s_label, s_flag   = gs.classify_sexual(row)
        rows.append({
            STABLE_ID_COL:          str(sid).strip(),
            "Funding Request Name": str(row.get("Funding Request Name", "") or ""),
            ENG_ETHNIC1:            e1,
            ENG_ETHNIC2:            e2,
            ENG_ETHNIC3:            e3,
            ENG_GENDER:             g_label,
            ENG_SEXUAL:             s_label,
            ENG_ETHNIC_FLAG:        eflag,
            ENG_GENDER_FLAG:        g_flag,
            ENG_SEXUAL_FLAG:        s_flag,
        })
    return pd.DataFrame(rows), skipped


# ---------------------------------------------------------------------------
# Annotation parser
# ---------------------------------------------------------------------------

def _parse_annotation(note_raw, eng_gender, eng_sexual):
    """
    Parse one freeform annotation into structured audit columns.

    Returns a dict with keys:
        correct_gender, correct_sexual,
        gender_flag_ok, sexual_flag_ok,
        notes, parse_status

    parse_status values:
        'yes'           — engine was correct; correction columns = engine labels
        'no-parsed'     — engine was wrong; correct label extracted from note
        'needs-review'  — engine was wrong; correct label could not be parsed
        'uncertain'     — reviewer was unsure; left blank for manual finalization
        'blank'         — no annotation present
    """
    if pd.isna(note_raw) or not str(note_raw).strip():
        return dict(
            correct_gender="", correct_sexual="",
            gender_flag_ok="", sexual_flag_ok="",
            notes="", parse_status="blank",
        )

    note = str(note_raw).strip()
    nl   = note.lower()

    # ------------------------------------------------------------------
    # YES branch — engine classification was correct
    # ------------------------------------------------------------------
    if nl.startswith("yes"):
        # "flag" in note -> the reviewer noted a missing or incomplete flag
        flag_concern = "flag" in nl
        return dict(
            correct_gender=eng_gender,
            correct_sexual=eng_sexual,
            gender_flag_ok="No" if flag_concern else "Yes",
            sexual_flag_ok="Yes",
            notes=note,
            parse_status="yes",
        )

    # ------------------------------------------------------------------
    # NO branch — engine classification was wrong
    # ------------------------------------------------------------------
    if nl.startswith("no"):
        correct_gender = ""
        correct_sexual = ""
        parse_status   = "needs-review"

        if "general" in nl:
            correct_gender = GENDER_GENERAL_POP
            parse_status   = "no-parsed"
        elif "multiple" in nl:
            correct_gender = GENDER_MULTIPLE
            parse_status   = "no-parsed"
            # "gender-diverse" or explicit "2slgbtqia" in note also implies sexual axis
            if "2slgbtqia" in nl or "gender-diverse" in nl:
                correct_sexual = SEXUAL_2SLGBTQIA

        return dict(
            correct_gender=correct_gender,
            correct_sexual=correct_sexual,
            gender_flag_ok="No",
            sexual_flag_ok="No",
            notes=note,
            parse_status=parse_status,
        )

    # ------------------------------------------------------------------
    # Uncertain — reviewer was unsure; leave blank for human finalization
    # ------------------------------------------------------------------
    return dict(
        correct_gender="", correct_sexual="",
        gender_flag_ok="", sexual_flag_ok="",
        notes=note, parse_status="uncertain",
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if not REVIEW_REPORT.exists():
        print(f"ERROR: {REVIEW_REPORT} not found.")
        sys.exit(1)

    if GOLD_FILE.exists():
        print(f"NOTE: {GOLD_FILE} already exists — this script writes to")
        print(f"      audit_gold_prefilled.xlsx only and never modifies it.")

    # ------------------------------------------------------------------
    # Step 1 — build gold template in-memory (no file written)
    # ------------------------------------------------------------------
    print("Loading taxonomy and funding requests...")
    taxonomy_fp = bootstrap.PROJECT_ROOT / "Taxonomy" / "Taxonomy - Definitions.xlsx"
    funding_fp  = bootstrap.PROJECT_ROOT / "Data Sheets" / "FR testing.xlsx"
    tax_df  = pd.read_excel(taxonomy_fp, sheet_name=et.TAXONOMY_SHEET, dtype=str)
    data_df = pd.read_excel(funding_fp,  sheet_name=et.DATA_SHEET,     dtype=str)
    taxonomy_entries = et.build_taxonomy(tax_df)

    print("Running classifiers...")
    engine_df, skipped = _run_classifiers(data_df, taxonomy_entries)
    if skipped:
        print(f"  Skipped {skipped} rows missing '{STABLE_ID_COL}'.")

    gold_df = engine_df.copy()
    for col in [CORRECT_ETHNIC1, CORRECT_GENDER, CORRECT_SEXUAL,
                ETHNIC_FLAG_OK, GENDER_FLAG_OK, SEXUAL_FLAG_OK,
                NOTES_COL, PARSE_STATUS_COL]:
        gold_df[col] = ""

    # Build name -> list-of-gold-indices lookup (handles any future duplicates)
    gold_name_idx = defaultdict(list)
    for idx, row in gold_df.iterrows():
        name = str(row["Funding Request Name"] or "").strip()
        gold_name_idx[name].append(idx)

    # ------------------------------------------------------------------
    # Step 2 — load annotated rows from the review report
    # ------------------------------------------------------------------
    print(f"Loading annotations from: {REVIEW_REPORT}")
    review_df = pd.read_excel(REVIEW_REPORT, sheet_name=AUDIT_DETAIL_SHEET, dtype=str)
    annotated = review_df[
        review_df[ANNOTATION_COL].notna() &
        (review_df[ANNOTATION_COL].str.strip() != "")
    ][["Funding Request Name", ANNOTATION_COL]].copy()
    print(f"  {len(annotated)} annotated rows found.")

    # ------------------------------------------------------------------
    # Step 3 — join and parse
    # ------------------------------------------------------------------
    n_matched      = 0
    n_no_stable_id = 0
    n_ambiguous    = 0

    for _, ann_row in annotated.iterrows():
        name = str(ann_row["Funding Request Name"] or "").strip()
        note = ann_row[ANNOTATION_COL]

        gold_indices = gold_name_idx.get(name, [])

        if not gold_indices:
            n_no_stable_id += 1
            print(f"  UNMATCHED (no stable ID in gold): {name!r}")
            continue

        if len(gold_indices) > 1:
            n_ambiguous += 1
            print(f"  AMBIGUOUS ({len(gold_indices)} gold rows share this name): {name!r}")

        for gi in gold_indices:
            eng_gender = gold_df.at[gi, ENG_GENDER]
            eng_sexual = gold_df.at[gi, ENG_SEXUAL]
            parsed = _parse_annotation(note, eng_gender, eng_sexual)

            gold_df.at[gi, CORRECT_GENDER]   = parsed["correct_gender"]
            gold_df.at[gi, CORRECT_SEXUAL]   = parsed["correct_sexual"]
            gold_df.at[gi, GENDER_FLAG_OK]   = parsed["gender_flag_ok"]
            gold_df.at[gi, SEXUAL_FLAG_OK]   = parsed["sexual_flag_ok"]
            gold_df.at[gi, NOTES_COL]        = parsed["notes"]
            gold_df.at[gi, PARSE_STATUS_COL] = parsed["parse_status"]
            n_matched += 1

    # ------------------------------------------------------------------
    # Step 4 — write output
    # ------------------------------------------------------------------
    output_cols = [
        STABLE_ID_COL, "Funding Request Name",
        ENG_ETHNIC1, ENG_ETHNIC2, ENG_ETHNIC3,
        ENG_GENDER, ENG_SEXUAL,
        ENG_ETHNIC_FLAG, ENG_GENDER_FLAG, ENG_SEXUAL_FLAG,
        CORRECT_ETHNIC1, CORRECT_GENDER, CORRECT_SEXUAL,
        ETHNIC_FLAG_OK, GENDER_FLAG_OK, SEXUAL_FLAG_OK,
        NOTES_COL, PARSE_STATUS_COL,
    ]
    gold_df[output_cols].to_excel(PREFILL_FILE, index=False)

    # Post-write: certain pandas/openpyxl version combinations inject a
    # synthetic "Column1, Column2, ..." row above the real headers.
    # Detect and remove it so row 1 always contains the real column names.
    from openpyxl import load_workbook as _load_wb
    _wb = _load_wb(PREFILL_FILE)
    _ws = _wb.active
    _first = [str(_c.value or "") for _c in _ws[1]]
    if all((_v.startswith("Column") and _v[6:].isdigit()) for _v in _first if _v):
        _ws.delete_rows(1)
        _wb.save(PREFILL_FILE)

    # ------------------------------------------------------------------
    # Step 5 — summary
    # ------------------------------------------------------------------
    status_counts = gold_df[PARSE_STATUS_COL].value_counts()
    annotated_statuses = gold_df[gold_df[PARSE_STATUS_COL] != ""]
    n_needs_review = (gold_df[PARSE_STATUS_COL] == "needs-review").sum()
    n_uncertain    = (gold_df[PARSE_STATUS_COL] == "uncertain").sum()
    n_manual       = n_needs_review + n_uncertain

    print(f"\nResults:")
    print(f"  Gold template rows   : {len(gold_df)}")
    print(f"  Annotations matched  : {n_matched}")
    if n_no_stable_id:
        print(f"  Unmatched (no ID)    : {n_no_stable_id}")
    if n_ambiguous:
        print(f"  Ambiguous joins      : {n_ambiguous}")
    print(f"\nParse status breakdown:")
    for status in ["yes", "no-parsed", "needs-review", "uncertain", "blank"]:
        count = (gold_df[PARSE_STATUS_COL] == status).sum()
        if count:
            print(f"  {status:<20}: {count}")
    print(f"\nCaveat: {n_matched - n_manual}/{n_matched} annotations pre-filled automatically (~"
          f"{round((n_matched - n_manual) / max(n_matched, 1) * 100)}%).")
    if n_manual:
        print(f"  {n_manual} row(s) marked 'needs-review' or 'uncertain' require manual")
        print(f"  finalization before scoring.")
    print(f"\nNote: 'Correct Ethnic 1' is left blank throughout - the hand-audit")
    print(f"  focused on gender/sexual; fill it separately if needed.")
    print(f"\nWritten -> {PREFILL_FILE}")
    print("Review, finalize, rename to audit_gold.xlsx, then run: python audit_score.py")


if __name__ == "__main__":
    main()
