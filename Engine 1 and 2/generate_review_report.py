import sys
import random
import pandas as pd

import ethnic_taggerv3 as et
from pathlib import Path

"""
generate_review_report.py
---------------------------
ClaudeAI Diagnostic tool -- NOT part of the normal classification run, and never
writes back to your funding requests file. Builds a single Excel
workbook with several tabs, meant for manual review of what Engine 1
is actually doing on your real data, before any more classification
rules get added.

This exists because the right next step isn't more rules -- it's
finding out whether the existing rules are already correct. The two
numbers worth knowing before anything else:
    - How many of the "General Population" rows are actually correct?
    - How many of the "Ambiguous equity term" rows are correct?
Guessing at either from outside the data is how rules end up being
added for problems that don't actually exist, or missed for ones that
do.

Tabs produced:
    1. General Population Sample - a random sample (up to 100 rows) of
       everything Engine 1 left as General Population. Random, not
       "first N", so the sample isn't biased by row order in the sheet.
    2. Ambiguous Equity Rows - ALL rows flagged with the "no paired
       ethnic signal" buzzword-only outcome. Every one of these, not a
       sample, since this is the smaller and more suspicious group.
    3. Multiple Rows - ALL rows classified as Multiple Ethnic and
       Cultural Origins, so you can judge whether the flags on them are
       actually actionable or just restating a decision already made.
    4. Flag Frequency - every distinct flag value that appears anywhere
       in the dataset, with a count, sorted most-common first.
    5. Classification Frequency - every distinct (Ethnic 1, Ethnic 2,
       Ethnic 3) combination Engine 1 produced, with a count, so you
       can see what's actually being triggered most often.

To Run:
    python generate_review_report.py "<path to Taxonomy - Definitions.xlsx>" "<path to funding requests workbook>"

Output:
    review_report.xlsx, written to the current directory.
"""

SAMPLE_SIZE = 100
RANDOM_SEED = 42  # fixed so the same sample comes up
OUTPUT_FILE = "review_report.xlsx"


def main():
    if len(sys.argv) < 3:
        print('Usage: python generate_review_report.py "C:\\Users\\oadode\\OneDrive - Edmonton Community Foundation\\Desktop\\Discretionary FR Scripting\\ECF-Discretionary-FR-Scripting\\Taxonomy - Definitions.xlsx" "C:\\Users\\oadode\\OneDrive - Edmonton Community Foundation\\Desktop\\Discretionary FR Scripting\\ECF-Discretionary-FR-Scripting\\FR testing.xlsx"')
        sys.exit(1)

    SCRIPT_DIR = Path(__file__).resolve().parent

    taxonomy_filepath = SCRIPT_DIR.parent / "Data Sheets" / "Taxonomy - Definitions.xlsx"
    funding_filepath = SCRIPT_DIR.parent / "Data Sheets" / "FR testing.xlsx"

    tax_df = pd.read_excel(taxonomy_filepath, sheet_name=et.TAXONOMY_SHEET, dtype=str)
    data_df = pd.read_excel(funding_filepath, sheet_name=et.DATA_SHEET, dtype=str)

    taxonomy_entries = et.build_taxonomy(tax_df)

    rows = []
    for idx, row in data_df.iterrows():
        e1, e2, e3, flag = et.classify_row(row, taxonomy_entries)
        rows.append({
            "Funding Request Name": row.get("Funding Request Name", f"row {idx}"),
            "Final_Project_Description": row.get("Final_Project_Description", ""),
            "Final_Summary_Description": row.get("Final_Summary_Description", ""),
            "Purpose": row.get("Purpose", ""),
            "Ethnic 1": e1,
            "Ethnic 2": e2,
            "Ethnic 3": e3,
            "Classification Flag": flag,
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
        results_df.groupby(["Ethnic 1", "Ethnic 2", "Ethnic 3"])
        .size()
        .reset_index(name="Count")
        .sort_values("Count", ascending=False)
    )

    with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
        general_sample.to_excel(writer, sheet_name="General Pop Sample", index=False)
        ambiguous_df.to_excel(writer, sheet_name="Ambiguous Equity Rows", index=False)
        multiple_df.to_excel(writer, sheet_name="Multiple Rows", index=False)
        flag_counts.to_excel(writer, sheet_name="Flag Frequency", index=False)
        class_counts.to_excel(writer, sheet_name="Classification Frequency", index=False)

    print(f"\nWritten to: {OUTPUT_FILE}")
    print("This file is a separate review workbook -- your original funding")
    print("requests file was not opened for writing and was not modified.")


if __name__ == "__main__":
    main()