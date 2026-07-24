import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # Engine 1 and 2
import bootstrap

sys.path.insert(0, str(bootstrap.PROJECT_ROOT / "Engine_1_and_2" / "Pipeline"))
sys.path.insert(0, str(bootstrap.PROJECT_ROOT / "Engine_1_and_2" / "Semantic_Engine"))

import pandas as pd
import ethnic_taggerv3 as et

"""
regression_ml_arbiter.py
-------------------------
One-off validation script (not part of the shipping pipeline). Runs
classify_row() over all 448 rows in Taxonomy/AUDITED_FR_GOLD.xlsx twice --
once with USE_ML_ROLE_ARBITER off, once on -- and confirms:
  1. Ethnic 1/2/3 labels are byte-identical in both runs (the arbiter must
     never change a classification, per the flag-only design).
  2. Lists every row whose FLAG TEXT changed, so the new notes can be
     manually spot-checked for sanity.

Run:
    .venv/Scripts/python.exe Engine_1_and_2/Auditing/regression_ml_arbiter.py
"""


def _read_excel_safe(path, **kwargs):
    import shutil, tempfile
    try:
        return pd.read_excel(path, **kwargs)
    except PermissionError:
        tmp = Path(tempfile.gettempdir()) / f"_locked_{Path(path).name}"
        shutil.copy2(path, tmp)
        try:
            return pd.read_excel(tmp, **kwargs)
        finally:
            try:
                tmp.unlink()
            except OSError:
                pass


def main():
    ds = bootstrap.dataset()
    print(f"[dataset] active: {ds.name}  ->  reads {ds.raw_file.name}, writes {ds.output_file.name}")

    # A fresh year has no reviewed rows, so scoring against the raw file
    # (every row unreviewed) is correct when no gold file exists yet.
    funding_fp = ds.gold_file if ds.gold_file is not None else ds.raw_file
    tax_df = _read_excel_safe(ds.taxonomy_file, sheet_name=et.TAXONOMY_SHEET, dtype=str)
    data_df = _read_excel_safe(funding_fp, sheet_name=et.DATA_SHEET, dtype=str)
    taxonomy_entries = et.build_taxonomy(tax_df)

    # Run 1: arbiter OFF
    os.environ.pop("USE_ML_ROLE_ARBITER", None)
    import classify_pipeline
    classify_pipeline.USE_ML_ROLE_ARBITER = False
    off_results = {}
    for _, row in data_df.iterrows():
        sid = row.get("SF_18_ID_Funding_Request__c", "")
        if pd.isna(sid) or not str(sid).strip():
            continue
        e1, e2, e3, flag = classify_pipeline.classify_row(row, taxonomy_entries)
        off_results[str(sid).strip()] = (e1, e2, e3, flag)

    # Run 2: arbiter ON
    classify_pipeline.USE_ML_ROLE_ARBITER = True
    label_diffs = []
    flag_diffs = []
    for _, row in data_df.iterrows():
        sid = row.get("SF_18_ID_Funding_Request__c", "")
        if pd.isna(sid) or not str(sid).strip():
            continue
        sid = str(sid).strip()
        e1, e2, e3, flag = classify_pipeline.classify_row(row, taxonomy_entries)
        off_e1, off_e2, off_e3, off_flag = off_results[sid]
        if (e1, e2, e3) != (off_e1, off_e2, off_e3):
            label_diffs.append((sid, row.get("Funding Request Name", ""), (off_e1, off_e2, off_e3), (e1, e2, e3)))
        if flag != off_flag:
            flag_diffs.append((sid, row.get("Funding Request Name", ""), off_flag, flag))

    print(f"Rows compared: {len(off_results)}")
    print(f"\nLABEL diffs (Ethnic 1/2/3 changed) -- MUST be zero: {len(label_diffs)}")
    for sid, name, before, after in label_diffs:
        print(f"  [{sid}] {name}")
        print(f"    before: {before}")
        print(f"    after:  {after}")

    print(f"\nFLAG TEXT diffs (new arbiter notes attached): {len(flag_diffs)}")
    for sid, name, before, after in flag_diffs:
        print(f"  [{sid}] {name}")
        print(f"    before: {before}")
        print(f"    after:  {after}")

    if not label_diffs:
        print("\nPASS: zero label changes -- arbiter is flag-only as designed.")
    else:
        print("\nFAIL: label changes detected -- arbiter is NOT flag-only. Investigate before shipping.")


if __name__ == "__main__":
    main()
