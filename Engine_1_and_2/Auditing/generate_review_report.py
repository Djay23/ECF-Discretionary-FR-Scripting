import sys
import random
from collections import Counter
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # Engine 1 and 2
import bootstrap 

import ethnic_taggerv3 as et
from classify_pipeline import classify_row as pipeline_classify_row, identity_markers
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
  Flags-by-group (3) — which classification group each flag fell under:
    14. Ethnic Flags by Group    - (Ethnic 1 group x flag) counts, most-common first
    15. Gender Flags by Group    - (Gender Id x flag) counts, most-common first
    16. Sexual Flags by Group    - (Sexual Id x flag) counts, most-common first

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


# ---------------------------------------------------------------------------
# ADDITIVE LAYER 4 — Deterministic validation moat (no numeric scores).
#
# Purely additive triage: it reads the labels/flags/evidence the engine ALREADY
# produced for a row and sorts it into one of three review tiers. It fabricates
# no confidence score and changes no classification — it only decides whether a
# row needs a human look, using real code signals:
#
#   * System Blindspot : every axis resolved to General AND no evidence term was
#                        matched anywhere -> unrecognized terminology, worth a look.
#   * Targeted Audit   : a "Multiple" multi-group fallback fired, OR a name-vs-body
#                        field conflict was flagged by the engine.
#   * Auto-Pass        : a clean, unconflicted single-identity (or clearly-signalled)
#                        row -- no review needed.
# ---------------------------------------------------------------------------
def audit_tier(e1, g_label, s_label, flag, g_flag, s_flag, eth_ev, gen_ev, sex_ev):
    is_multiple = (e1 == et.MULTIPLE_ETHNIC) or (g_label == gs.GENDER_MULTIPLE)
    all_general = (
        e1 == et.GENERAL_POP
        and g_label == gs.GENDER_GENERAL_POP
        and s_label == gs.SEXUAL_GENERAL_POP
    )
    no_evidence = not (eth_ev.strip() or gen_ev.strip() or sex_ev.strip())
    all_flags = " ".join(f for f in (flag, g_flag, s_flag) if f).lower()
    # A direct syntax conflict between distinct free-text fields: the engine
    # flagged that the signal lives only in the org/name (body did not
    # corroborate) or that distinct groups co-occur across the text.
    field_conflict = any(marker in all_flags for marker in (
        "signal appears only in the organization",
        "classified from organization name",
        "org-name self-reference",
        "co-present",
        "distinct groups",
    ))
    if all_general and no_evidence:
        return "System Blindspot"
    if is_multiple or field_conflict:
        return "Targeted Audit"
    return "Auto-Pass"


def split_flags_joinaware(cell):
    """Split a flag cell into distinct flags. The engine joins flags with '; '
    but some individual flags contain an internal '; ' (e.g. "...broader
    population; confirm the classification isn't narrower..."). Every catalogued
    flag starts uppercase or with 'Note (low priority):', while those internal
    continuations start lowercase — so re-attach any lowercase-leading segment to
    the flag it belongs to (mirrors the stakeholder dashboard's split_flags)."""
    parts = []
    for p in str(cell).split(";"):
        p = p.strip()
        if not p:
            continue
        if parts and p[:1].islower():
            parts[-1] = parts[-1] + "; " + p
        else:
            parts.append(p)
    return parts


def flags_by_group(df, group_col, flag_col):
    """Long-format tally answering "which group did each flag fall under":
    (group, flag) -> count, most-common first. One flagged row contributes one
    count per distinct flag it carries. Rows with no flag are ignored."""
    counter = Counter()
    for _, r in df.iterrows():
        grp = str(r[group_col]).strip() or "(blank)"
        for f in split_flags_joinaware(r[flag_col]):
            counter[(grp, f)] += 1
    return pd.DataFrame(
        [(g, f, n) for (g, f), n in counter.most_common()],
        columns=[group_col, flag_col, "Count"],
    )


def _read_excel_safe(path, **kwargs):
    """pd.read_excel that survives an Excel/OneDrive exclusive open-handle lock:
    on PermissionError, read a temp copy (a plain copy uses a share mode Excel
    allows) so an open workbook doesn't block the run."""
    try:
        return pd.read_excel(path, **kwargs)
    except PermissionError:
        import shutil, tempfile
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

    taxonomy_filepath = bootstrap.PROJECT_ROOT / "Taxonomy" / "Taxonomy - Definitions.xlsx"
    funding_filepath = bootstrap.PROJECT_ROOT / "Data Sheets" / "FR testing.xlsx"
    OUTPUT_FILE = bootstrap.PROJECT_ROOT / "Data Sheets" / "review_report(ML implement).xlsx"

    tax_df = _read_excel_safe(taxonomy_filepath, sheet_name=et.TAXONOMY_SHEET, dtype=str)
    data_df = _read_excel_safe(funding_filepath, sheet_name=et.DATA_SHEET, dtype=str)

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

        eth_ev = ae.ethnic_evidence(row, taxonomy_entries)
        gen_ev = ae.gender_evidence(row)
        sex_ev = ae.sexual_evidence(row)

        # --- Additive Layer 3: intersectional marker string (string-safe) ---
        # All distinct matched identity tags across axes, comma-joined. Existing
        # label columns are untouched; this is extra visibility only.
        markers = identity_markers(row, taxonomy_entries)
        if g_label != gs.GENDER_GENERAL_POP:
            markers.append(g_label)
        if s_label != gs.SEXUAL_GENERAL_POP:
            markers.append(s_label)
        multi_identity_markers = ", ".join(markers)

        # --- Additive Layer 4: deterministic triage tier ---
        tier = audit_tier(e1, g_label, s_label, flag, g_flag, s_flag,
                          eth_ev, gen_ev, sex_ev)

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
            "multi_identity_markers": multi_identity_markers,
            "audit_tier": tier,
            "Ethnic Evidence": eth_ev,
            "Gender Evidence": gen_ev,
            "Sexual Evidence": sex_ev,
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

    # --- Flags-by-group (Q5): which classification group each flag fell under ---
    ethnic_flags_by_group = flags_by_group(results_df, "Ethnic 1",  "Classification Flag")
    gender_flags_by_group = flags_by_group(results_df, "Gender Id", "Gender Flag")
    sexual_flags_by_group = flags_by_group(results_df, "Sexual Id", "Sexual Flag")
    print(f"Flags-by-group rows: ethnic={len(ethnic_flags_by_group)}, "
          f"gender={len(gender_flags_by_group)}, sexual={len(sexual_flags_by_group)}")

    # --- Audit Detail tab — every row, all labels/flags/evidence ---
    # SF_18_ID_Funding_Request__c is included so future hand-audits can join
    # back to audit_gold.xlsx by stable ID instead of Funding Request Name.
    AUDIT_DETAIL_COLS = [
        "Funding Request Name",
        "SF_18_ID_Funding_Request__c",
        "Final_Project_Description", "Final_Summary_Description", "Purpose",
        "Ethnic 1", "Ethnic 2", "Ethnic 3",
        "Gender Id", "Sexual Id",
        "multi_identity_markers", "audit_tier",
        "Classification Flag", "Gender Flag", "Sexual Flag",
        "Ethnic Evidence", "Gender Evidence", "Sexual Evidence",
    ]
    audit_detail_df = results_df[AUDIT_DETAIL_COLS]

    # --- Additive Layer 4: Manual Audit Queue — every non-Auto-Pass row ---
    # Deterministic triage output. Auto-Pass rows are omitted; Targeted Audit
    # and System Blindspot rows are surfaced together for human review, tier
    # column first so a reviewer can sort/triage.
    manual_audit_df = results_df[results_df["audit_tier"] != "Auto-Pass"][AUDIT_DETAIL_COLS]
    tier_counts = results_df["audit_tier"].value_counts().to_dict()
    print(f"Audit tiers: {tier_counts}")
    print(f"Manual audit queue (Targeted Audit + System Blindspot): {len(manual_audit_df)} rows")

    with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
        # Primary audit surface
        audit_detail_df.to_excel(writer, sheet_name="Audit Detail", index=False)
        # Deterministic validation moat (additive Layer 4)
        manual_audit_df.to_excel(writer, sheet_name="Manual Audit Queue", index=False)
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
        # Flags-by-group tabs (which group each flag fell under)
        ethnic_flags_by_group.to_excel(writer, sheet_name="Ethnic Flags by Group", index=False)
        gender_flags_by_group.to_excel(writer, sheet_name="Gender Flags by Group", index=False)
        sexual_flags_by_group.to_excel(writer, sheet_name="Sexual Flags by Group", index=False)

    print(f"\nWritten to: {OUTPUT_FILE}")
    print("This file is a separate review workbook -- your original funding\nrequests file was not opened for writing and was not modified.")

if __name__ == "__main__":
    main()