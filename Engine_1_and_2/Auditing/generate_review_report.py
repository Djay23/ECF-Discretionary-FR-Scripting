import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # Engine 1 and 2
import bootstrap

import ethnic_taggerv3 as et
import audit_evidence as ae
from dataset_config import DATASETS

"""
generate_review_report.py
--------------------------
Builds ONE review workbook that MIRRORS the gold sheets. Read-only: never
writes back to any gold or funding-requests file.

One sheet per dataset (e.g. "2023-24", "2025"), each a copy of that dataset's
gold sheet -- the SAME columns the gold carries (classification, flags,
sector/ECD/AH, source text, the accuracy column, ...) -- with only three
columns dropped (Account Name, Status, Amount) and ONE column added:

    "Flag Explanation (why + evidence)"  -- for each flagged axis, the flag
    text (WHY) from the gold sheet's own flag column, plus the re-scanned
    evidence (WHICH term matched, in WHICH field, + snippet) from
    audit_evidence.py.

Nothing is hardcoded to a fixed column set: whatever columns are in a gold
sheet flow through (minus the three dropped), so editing the gold and re-running
this script updates the report. Classification values are taken straight from
the gold sheet; only the evidence column is computed.

Frequency/accuracy summaries deliberately live in the stakeholder dashboard
(generate_stakeholder_dashboard.py), not here.

To Run:
    python Engine_1_and_2/Auditing/generate_review_report.py
"""

# Columns dropped from the gold mirror. Everything else passes through.
OMIT_COLS = {"Account Name", "Status", "Amount"}

EVIDENCE_COL = "Flag Explanation (why + evidence)"

# Gold flag columns -> axis label + evidence function. The "why" is read from
# the gold sheet's own flag column so the report tracks the gold, not a re-run.
FLAG_AXES = [
    ("ETHNIC", "Classification Flag",        "ethnic"),
    ("GENDER", "Gender Classification Flag", "gender"),
    ("SEXUAL", "Sexual Classification Flag", "sexual"),
]


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


def build_evidence_cell(row, taxonomy_entries):
    """"why + evidence" text for the axes that carry a flag in the GOLD row: the
    gold's own flag column explains WHY, audit_evidence re-scans the text for
    WHICH term matched, in WHICH field, + snippet. '' when nothing is flagged."""
    evidence_fn = {
        "ethnic": lambda r: ae.ethnic_evidence(r, taxonomy_entries),
        "gender": ae.gender_evidence,
        "sexual": ae.sexual_evidence,
    }
    blocks = []
    for label, flag_col, axis in FLAG_AXES:
        flag = _cell(row.get(flag_col, ""))
        if not flag:
            continue
        evidence = evidence_fn[axis](row).strip() or "(no matching term re-scanned in the text)"
        blocks.append(f"{label} - why: {flag}  |  evidence: {evidence}")
    return "\n".join(blocks)


def build_sheet(name, cfg):
    """Return (sheet_name, DataFrame) mirroring one gold sheet: all its columns
    minus OMIT_COLS, plus the evidence column. None if the gold is missing."""
    gold_rel = cfg.get("gold_file")
    gold_path = (bootstrap.PROJECT_ROOT / gold_rel) if gold_rel else None
    if not gold_path or not gold_path.exists():
        print(f"[{name}] no gold file ({gold_rel}) -- skipped.")
        return None

    tax_df = _read_excel_safe(bootstrap.PROJECT_ROOT / cfg["taxonomy_file"],
                              sheet_name=cfg["taxonomy_sheet"], dtype=str)
    taxonomy_entries = et.build_taxonomy(tax_df)

    df = _read_excel_safe(gold_path, sheet_name=cfg["data_sheet"], dtype=str).fillna("")
    df[EVIDENCE_COL] = [build_evidence_cell(r, taxonomy_entries) for _, r in df.iterrows()]

    keep = [c for c in df.columns if c not in OMIT_COLS]
    sheet_name = name.replace("_", "-")[:31]  # Excel sheet-name limit / no '/'
    return sheet_name, df[keep]


def main():
    # 2023_24 before 2025 (sorted) so the older dataset reads left-to-right first.
    sheets = []
    for name in sorted(DATASETS):
        result = build_sheet(name, DATASETS[name])
        if result:
            sheets.append(result)

    if not sheets:
        print("No gold sheets available -- nothing written.")
        return 1

    out_path = bootstrap.PROJECT_ROOT / "Data Sheets" / "Classification Review.xlsx"
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        for sheet_name, df in sheets:
            df.to_excel(writer, sheet_name=sheet_name, index=False)
            print(f"  sheet '{sheet_name}': {len(df)} rows, {len(df.columns)} columns")

    print(f"\nWritten to: {out_path}")
    print("Read-only mirror of the gold sheets (+ evidence column). No gold file modified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
