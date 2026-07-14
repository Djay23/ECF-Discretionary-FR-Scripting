import sys
import random
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # Engine 1 and 2
import bootstrap 

import ethnic_taggerv3 as et
from classify_pipeline import classify_row as pipeline_classify_row
import Gender_SexID as gs
import audit_evidence as ae
from pathlib import Path
 
"""
generate_review_report.py
---------------------------
ClaudeAI Diagnostic tool -- NOT part of the normal classification run, and never
writes back to your funding requests file. Builds a single Excel
workbook with several tabs, meant for manual review of what Engine 1
is actually doing on your real data, before any more classification
rules get added.

Tabs produced:
  Ethnic (5):
    1.  General Pop Sample       - random sample (up to 100) of General Population rows
    2.  Ambiguous Equity Rows    - all rows with "no paired ethnic signal" flag
    3.  Multiple Rows            - all Multiple Ethnic and Cultural Origins rows
    4.  Flag Frequency           - distinct ethnic flags, most-common first
    5.  Classification Frequency - distinct (Ethnic1, Ethnic2, Ethnic3) combos, most-common first
  Gender (4):
    6.  Gender Gen Pop Sample    - random sample of Gender General Population rows (recall check)
    7.  Gender Multiple Rows     - all Multiple gender identities rows
    8.  Gender Flag Frequency    - distinct gender flags, most-common first
    9.  Gender Class Frequency   - distinct Gender Id values, most-common first
  Sexual Identity (4):
    10. 2SLGBTQIA Rows           - all 2SLGBTQIA+ rows (precision check)
    11. Sexual Gen Pop Sample    - random sample of Sexual General Population rows (recall check)
    12. Sexual Flag Frequency    - distinct sexual flags, most-common first
    13. Sexual Class Frequency   - distinct Sexual Id values, most-common first

To Run:
   $env:PYTHONIOENCODING="utf-8"; $env:HF_HUB_OFFLINE="1"; python Engine_1_and_2/Auditing/generate_review_report.py

Output:
    Data Sheets/review_report(ML implement).xlsx  (separate workbook — FR testing.xlsx is never modified)
"""

SAMPLE_SIZE = 100
RANDOM_SEED = 42  # fixed so the same sample comes up

GENDER_SAMPLE_COLS = ["Funding Request Name", "Final_Project_Description",
                      "Final_Summary_Description", "Purpose", "Gender Id", "Gender Flag"]
SEXUAL_SAMPLE_COLS = ["Funding Request Name", "Final_Project_Description",
                      "Final_Summary_Description", "Purpose", "Sexual Id", "Sexual Flag"]

def main():

    taxonomy_filepath = bootstrap.PROJECT_ROOT / "Taxonomy" / "Taxonomy - Definitions.xlsx"
    funding_filepath = bootstrap.PROJECT_ROOT / "Data Sheets" / "FR testing.xlsx"
    OUTPUT_FILE = bootstrap.PROJECT_ROOT / "Data Sheets" / "review_report(ML implement).xlsx"

    tax_df = pd.read_excel(taxonomy_filepath, sheet_name=et.TAXONOMY_SHEET, dtype=str)
    data_df = pd.read_excel(funding_filepath, sheet_name=et.DATA_SHEET, dtype=str)

    taxonomy_entries = et.build_taxonomy(tax_df)

    CROSS_DOMAIN_NOTE = "Ethnic/cultural signal co-present - verify intersectional target population"

    rows = []
    for idx, row in data_df.iterrows():
        e1, e2, e3, flag = pipeline_classify_row(row, taxonomy_entries)
        g_label, g_flag  = gs.classify_gender(row)
        s_label, s_flag  = gs.classify_sexual(row)

        # Cross-domain co-signal: gender/sexual classification alongside ethnic signal
        has_gender_or_sexual = (g_label != gs.GENDER_GENERAL_POP or
                                s_label != gs.SEXUAL_GENERAL_POP)
        has_ethnic = (e1 != et.GENERAL_POP)
        if has_gender_or_sexual and has_ethnic:
            g_flag = "; ".join(p for p in [g_flag, CROSS_DOMAIN_NOTE] if p)
            s_flag = "; ".join(p for p in [s_flag, CROSS_DOMAIN_NOTE] if p)

        rows.append({
            "Funding Request Name": row.get("Funding Request Name", f"row {idx}"),
            "SF_18_ID_Funding_Request__c": row.get("SF_18_ID_Funding_Request__c", ""),
            "Final_Project_Description": row.get("Final_Project_Description", ""),
            "Final_Summary_Description": row.get("Final_Summary_Description", ""),
            "Purpose": row.get("Purpose", ""),
            "Ethnic 1": e1,
            "Ethnic 2": e2,
            "Ethnic 3": e3,
            "Classification Flag": flag,
            "Gender Id": g_label,
            "Gender Flag": g_flag,
            "Sexual Id": s_label,
            "Sexual Flag": s_flag,
            "Ethnic Evidence": ae.ethnic_evidence(row, taxonomy_entries),
            "Gender Evidence": ae.gender_evidence(row),
            "Sexual Evidence": ae.sexual_evidence(row),
        })

    results_df = pd.DataFrame(rows)
    print(f"{len(results_df)} total rows classified.")

    # --- Tab 1: General Population sample (random, not first-N) ---
    general_df = results_df[results_df["Ethnic 1"] == et.GENERAL_POP]
    print(f"General Population rows: {len(general_df)}")
    sample_n = min(SAMPLE_SIZE, len(general_df))
    general_sample = general_df.sample(n=sample_n, random_state=RANDOM_SEED) if sample_n > 0 else general_df

    # --- Tab 2: every "no paired ethnic signal" row, not a sample ---
    ambiguous_df = results_df[results_df["Classification Flag"].str.contains(
        "no paired ethnic signal", case=False, na=False)]
    print(f"Ambiguous equity term (no signal) rows: {len(ambiguous_df)}")

    # --- Tab 3: every Multiple row ---
    multiple_df = results_df[results_df["Ethnic 1"] == et.MULTIPLE_ETHNIC]
    print(f"Multiple Ethnic and Cultural Origins rows: {len(multiple_df)}")

    # --- Tab 4: flag frequency, most common first ---
    flag_counts = (
        results_df[results_df["Classification Flag"] != ""]["Classification Flag"]
        .value_counts()
        .reset_index()
    )
    flag_counts.columns = ["Classification Flag", "Count"]

    # --- Tab 5: classification (E1/E2/E3) frequency, most common first ---
    class_counts = (
        results_df.assign(flagged=results_df["Classification Flag"] != "")
        .groupby(["Ethnic 1", "Ethnic 2", "Ethnic 3"])
        .agg(Count=("flagged", "size"), Flagged_Count=("flagged", "sum"))
        .reset_index()
        .sort_values("Count", ascending=False)
    )
    class_counts.rename(columns={"Flagged_Count": "Flagged Count"}, inplace=True)

    # --- Gender tabs ---
    gender_gen_pop_df = results_df[results_df["Gender Id"] == gs.GENDER_GENERAL_POP]
    g_sample_n = min(SAMPLE_SIZE, len(gender_gen_pop_df))
    gender_gen_pop_sample = (
        gender_gen_pop_df.sample(n=g_sample_n, random_state=RANDOM_SEED)
        if g_sample_n > 0 else gender_gen_pop_df
    )[GENDER_SAMPLE_COLS]
    gender_multiple_df = results_df[results_df["Gender Id"] == gs.GENDER_MULTIPLE]
    gender_flag_counts = (
        results_df[results_df["Gender Flag"] != ""]["Gender Flag"]
        .value_counts().reset_index()
    )
    gender_flag_counts.columns = ["Gender Flag", "Count"]
    gender_class_counts = (
        results_df["Gender Id"].value_counts().reset_index()
    )
    gender_class_counts.columns = ["Gender Id", "Count"]

    # --- Sexual identity tabs ---
    sexual_2slgbtqia_df = results_df[results_df["Sexual Id"] == gs.SEXUAL_2SLGBTQIA]
    sexual_gen_pop_df   = results_df[results_df["Sexual Id"] == gs.SEXUAL_GENERAL_POP]
    s_sample_n = min(SAMPLE_SIZE, len(sexual_gen_pop_df))
    sexual_gen_pop_sample = (
        sexual_gen_pop_df.sample(n=s_sample_n, random_state=RANDOM_SEED)
        if s_sample_n > 0 else sexual_gen_pop_df
    )[SEXUAL_SAMPLE_COLS]
    sexual_flag_counts = (
        results_df[results_df["Sexual Flag"] != ""]["Sexual Flag"]
        .value_counts().reset_index()
    )
    sexual_flag_counts.columns = ["Sexual Flag", "Count"]
    sexual_class_counts = (
        results_df["Sexual Id"].value_counts().reset_index()
    )
    sexual_class_counts.columns = ["Sexual Id", "Count"]

    # --- Audit Detail tab — every row, all labels/flags/evidence ---
    # SF_18_ID_Funding_Request__c is included so future hand-audits can join
    # back to audit_gold.xlsx by stable ID instead of Funding Request Name.
    AUDIT_DETAIL_COLS = [
        "Funding Request Name",
        "SF_18_ID_Funding_Request__c",
        "Final_Project_Description", "Final_Summary_Description", "Purpose",
        "Ethnic 1", "Ethnic 2", "Ethnic 3",
        "Gender Id", "Sexual Id",
        "Classification Flag", "Gender Flag", "Sexual Flag",
        "Ethnic Evidence", "Gender Evidence", "Sexual Evidence",
    ]
    audit_detail_df = results_df[AUDIT_DETAIL_COLS]

    with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
        # Primary audit surface
        audit_detail_df.to_excel(writer, sheet_name="Audit Detail", index=False)
        # Ethnic tabs
        general_sample.to_excel(writer, sheet_name="General Pop Sample", index=False)
        ambiguous_df.to_excel(writer, sheet_name="Ambiguous Equity Rows", index=False)
        multiple_df.to_excel(writer, sheet_name="Multiple Rows", index=False)
        flag_counts.to_excel(writer, sheet_name="Flag Frequency", index=False)
        class_counts.to_excel(writer, sheet_name="Classification Frequency", index=False)
        # Gender tabs
        gender_gen_pop_sample.to_excel(writer, sheet_name="Gender Gen Pop Sample", index=False)
        gender_multiple_df.to_excel(writer, sheet_name="Gender Multiple Rows", index=False)
        gender_flag_counts.to_excel(writer, sheet_name="Gender Flag Frequency", index=False)
        gender_class_counts.to_excel(writer, sheet_name="Gender Class Frequency", index=False)
        # Sexual identity tabs
        sexual_2slgbtqia_df.to_excel(writer, sheet_name="2SLGBTQIA Rows", index=False)
        sexual_gen_pop_sample.to_excel(writer, sheet_name="Sexual Gen Pop Sample", index=False)
        sexual_flag_counts.to_excel(writer, sheet_name="Sexual Flag Frequency", index=False)
        sexual_class_counts.to_excel(writer, sheet_name="Sexual Class Frequency", index=False)

    print(f"\nWritten to: {OUTPUT_FILE}")
    print("This file is a separate review workbook -- your original funding\nrequests file was not opened for writing and was not modified.")

if __name__ == "__main__":
    main()