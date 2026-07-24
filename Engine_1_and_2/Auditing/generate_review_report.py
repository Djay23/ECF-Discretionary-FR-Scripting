import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # Engine 1 and 2
import bootstrap

import ethnic_taggerv3 as et
from classify_pipeline import classify_row as pipeline_classify_row
import Gender_SexID as gs
import audit_evidence as ae

"""
generate_review_report.py
--------------------------
Builds ONE self-contained review workbook for the active dataset. Read-only:
it never writes back to the funding-requests file or the gold file.

Three sheets:
  1. "Discretionary Funding Requests" — every row, side by side: what the ENGINE
     decided vs the hand-AUDITED (gold) value on each axis, an agree? column,
     the engine's flags, and a "why + evidence" column explaining each flag and
     pointing to the term/field/snippet it came from.
  2. "Classification Frequency" — per axis (Ethnic/Gender/Sexual): how often each
     classification occurred (engine vs audited counts), how many of those rows
     were flagged, plus an engine-vs-audited agreement summary.
  3. "Flag Frequency" — each distinct flag type and its count (by axis), plus
     total flag instances and flagged-row totals.

If the active dataset has no gold file, the audited columns/accuracy are left
blank and the report is engine-only.

To Run:
   $env:PYTHONIOENCODING="utf-8"; python Engine_1_and_2/Auditing/generate_review_report.py
"""

# Audited (hand-corrected / gold) classification columns in the workbook.
AUDIT_ETHNIC_COLS = ["Ethnic 1 - FR6", "Ethnic 2 - FR7", "Ethnic 3 - FR8"]
AUDIT_GENDER_COL  = "Gender Id - FR9"
AUDIT_SEXUAL_COL  = "Sexual Id - FR10"


def _read_excel_safe(path, **kwargs):
    """pd.read_excel that survives an Excel/OneDrive exclusive lock by reading a
    temp copy (a plain copy uses a share mode Excel allows)."""
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


def _cell(value):
    """Stripped string for a cell; blank/NaN -> ''."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def _join_levels(*values):
    """Join non-empty level values into one display string ('L1 | L2 | L3')."""
    return " | ".join(v for v in (_cell(v) for v in values) if v)


def _canon(text):
    """Case/space-insensitive key for comparing engine vs audited labels."""
    return " ".join(str(text).split()).lower()


def split_flags_joinaware(cell):
    """Split a flag cell into distinct flags. The engine joins flags with '; '
    but some flags contain an internal '; ' whose continuation starts lowercase,
    so re-attach any lowercase-leading segment to the flag it belongs to."""
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


def build_evidence_cell(row, taxonomy_entries, eth_flag, gen_flag, sex_flag):
    """Reviewer-facing "why + evidence" text for the axes that carry a flag: the
    flag text explains WHY, the re-scanned evidence shows WHICH term matched, in
    WHICH field, and the surrounding snippet. Returns '' when nothing is flagged."""
    axes = (
        ("ETHNIC", eth_flag, lambda r: ae.ethnic_evidence(r, taxonomy_entries)),
        ("GENDER", gen_flag, ae.gender_evidence),
        ("SEXUAL", sex_flag, ae.sexual_evidence),
    )
    blocks = []
    for label, flag, evidence_fn in axes:
        if not _cell(flag):
            continue
        evidence = evidence_fn(row).strip() or "(no matching term re-scanned in the text)"
        blocks.append(f"{label} - why: {_cell(flag)}  |  evidence: {evidence}")
    return "\n".join(blocks)


def _freq_table(records, axis, engine_key, audit_key, flag_key):
    """Per-axis frequency: for each classification value (union of engine +
    audited), how many rows the ENGINE gave it, how many the AUDIT gave it, and
    how many audited-that-class rows carried a flag. Sorted by audited count."""
    from collections import Counter
    engine_ct, audit_ct, flagged_ct = Counter(), Counter(), Counter()
    for rec in records:
        e, a = rec[engine_key], rec[audit_key]
        if e:
            engine_ct[e] += 1
        if a:
            audit_ct[a] += 1
            if _cell(rec[flag_key]):
                flagged_ct[a] += 1
    values = sorted(set(engine_ct) | set(audit_ct),
                    key=lambda v: (-audit_ct[v], -engine_ct[v], v))
    return [
        {"Axis": axis, "Classification": v,
         "Engine Count": engine_ct[v], "Audited Count": audit_ct[v],
         "Flagged (audited rows)": flagged_ct[v]}
        for v in values
    ]


def main():
    ds = bootstrap.dataset()
    print(f"[dataset] active: {ds.name}")

    # Prefer the gold workbook (it holds source text AND the audited columns);
    # fall back to the raw file (engine-only, no audit) when no gold exists.
    have_gold = getattr(ds, "gold_file", None) is not None and Path(ds.gold_file).exists()
    source = ds.gold_file if have_gold else ds.raw_file
    print(f"[source] {'gold' if have_gold else 'raw (no gold — engine-only)'}: {Path(source).name}")

    tax_df = _read_excel_safe(ds.taxonomy_file, sheet_name=et.TAXONOMY_SHEET, dtype=str)
    data_df = _read_excel_safe(source, sheet_name=ds.data_sheet, dtype=str)
    taxonomy_entries = et.build_taxonomy(tax_df)

    records = []
    for _, row in data_df.iterrows():
        # --- engine (live) ---
        e1, e2, e3, eth_flag = pipeline_classify_row(row, taxonomy_entries)
        g_label, gen_flag = gs.classify_gender(row)
        s_label, sex_flag = gs.classify_sexual(row)
        eth_engine = _join_levels(e1, e2, e3)
        gen_engine = _cell(g_label)
        sex_engine = _cell(s_label)

        # --- audited (from gold columns; blank if not present) ---
        eth_audit = _join_levels(*[row.get(c, "") for c in AUDIT_ETHNIC_COLS]) if have_gold else ""
        gen_audit = _cell(row.get(AUDIT_GENDER_COL, "")) if have_gold else ""
        sex_audit = _cell(row.get(AUDIT_SEXUAL_COL, "")) if have_gold else ""

        def agree(engine, audit):
            if not have_gold or not audit:
                return ""
            return "YES" if _canon(engine) == _canon(audit) else "NO"

        records.append({
            "Funding Request Name": _cell(row.get("Funding Request Name", "")),
            "SF_18_ID_Funding_Request__c": _cell(row.get("SF_18_ID_Funding_Request__c", "")),
            "Final_Project_Description": _cell(row.get("Final_Project_Description", "")),
            "Final_Summary_Description": _cell(row.get("Final_Summary_Description", "")),
            "Purpose": _cell(row.get("Purpose", "")),
            "Ethnic (engine)": eth_engine,
            "Ethnic (audited)": eth_audit,
            "Ethnic agree?": agree(eth_engine, eth_audit),
            "Gender (engine)": gen_engine,
            "Gender (audited)": gen_audit,
            "Gender agree?": agree(gen_engine, gen_audit),
            "Sexual (engine)": sex_engine,
            "Sexual (audited)": sex_audit,
            "Sexual agree?": agree(sex_engine, sex_audit),
            "Classification Flag": _cell(eth_flag),
            "Gender Classification Flag": _cell(gen_flag),
            "Sexual Classification Flag": _cell(sex_flag),
            "Flag Explanation (why + evidence)": build_evidence_cell(
                row, taxonomy_entries, eth_flag, gen_flag, sex_flag),
        })

    print(f"{len(records)} rows classified.")

    # --- Sheet 1: the full data sheet ---
    detail_df = pd.DataFrame(records)

    # --- Sheet 2: classification frequency (per axis) + agreement summary ---
    freq_rows = (
        _freq_table(records, "Ethnic", "Ethnic (engine)", "Ethnic (audited)", "Classification Flag")
        + _freq_table(records, "Gender", "Gender (engine)", "Gender (audited)", "Gender Classification Flag")
        + _freq_table(records, "Sexual", "Sexual (engine)", "Sexual (audited)", "Sexual Classification Flag")
    )
    freq_df = pd.DataFrame(freq_rows)

    def _accuracy(axis, col):
        judged = [r for r in records if r[col]]
        agreed = sum(1 for r in judged if r[col] == "YES")
        pct = f"{agreed / len(judged) * 100:.1f}%" if judged else "n/a"
        return {"Axis": axis, "Engine == Audited": agreed,
                "Rows compared": len(judged), "Accuracy": pct}

    accuracy_df = pd.DataFrame([
        _accuracy("Ethnic", "Ethnic agree?"),
        _accuracy("Gender", "Gender agree?"),
        _accuracy("Sexual", "Sexual agree?"),
    ]) if have_gold else pd.DataFrame([{"note": "no gold file — engine-only report"}])

    # --- Sheet 3: flag frequency (per axis) + totals ---
    from collections import Counter
    flag_ct = Counter()
    axis_flag_ct = Counter()
    flagged_row_ct = Counter()
    any_flag_rows = 0
    for r in records:
        row_flagged = False
        for axis, col in (("Ethnic", "Classification Flag"),
                          ("Gender", "Gender Classification Flag"),
                          ("Sexual", "Sexual Classification Flag")):
            cell = r[col]
            if _cell(cell):
                row_flagged = True
                flagged_row_ct[axis] += 1
                for f in split_flags_joinaware(cell):
                    flag_ct[(axis, f)] += 1
                    axis_flag_ct[axis] += 1
        if row_flagged:
            any_flag_rows += 1
    flag_freq_df = pd.DataFrame(
        [{"Axis": axis, "Flag": f, "Count": n}
         for (axis, f), n in flag_ct.most_common()]
    )
    totals_df = pd.DataFrame([
        {"Metric": "Rows with >=1 flag", "Value": any_flag_rows},
        {"Metric": "Total flag instances", "Value": sum(flag_ct.values())},
        {"Metric": "Ethnic flag instances", "Value": axis_flag_ct["Ethnic"]},
        {"Metric": "Gender flag instances", "Value": axis_flag_ct["Gender"]},
        {"Metric": "Sexual flag instances", "Value": axis_flag_ct["Sexual"]},
    ])

    report_name = ("Classification Review.xlsx" if ds.name == "2025"
                   else f"Classification Review_{ds.name}.xlsx")
    out_path = bootstrap.PROJECT_ROOT / "Data Sheets" / report_name

    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        detail_df.to_excel(writer, sheet_name="Discretionary Funding Requests", index=False)

        # Classification Frequency: accuracy summary block, then the per-axis table.
        accuracy_df.to_excel(writer, sheet_name="Classification Frequency",
                             index=False, startrow=0)
        freq_df.to_excel(writer, sheet_name="Classification Frequency",
                        index=False, startrow=len(accuracy_df) + 2)

        # Flag Frequency: totals block, then the per-flag table.
        totals_df.to_excel(writer, sheet_name="Flag Frequency", index=False, startrow=0)
        flag_freq_df.to_excel(writer, sheet_name="Flag Frequency",
                             index=False, startrow=len(totals_df) + 2)

    print(f"\nWritten to: {out_path}")
    print("Sheets: 'Discretionary Funding Requests', 'Classification Frequency', 'Flag Frequency'.")
    print("Read-only report — your funding-requests file and gold file were not modified.")


if __name__ == "__main__":
    main()
