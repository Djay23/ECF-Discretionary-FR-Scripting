import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # Engine 1 and 2
import bootstrap
import safe_save

import ethnic_taggerv3 as et
import audit_evidence as ae
from classify_pipeline import classify_row
from Gender_SexID import classify_gender, classify_sexual
from dataset_config import DATASETS

"""
generate_review_report.py
--------------------------
Builds ONE review workbook that MIRRORS the gold sheets. Read-only: never
writes back to any gold or funding-requests file.

One sheet per dataset (e.g. "2023-24", "2025"), each the FLAGGED rows of that
dataset's gold sheet -- the SAME columns the gold carries (classification, flags,
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

# The three flag columns are re-computed LIVE from the current engine (not read
# from the gold snapshot), so flags removed from the engine never resurface. The
# classification columns still come straight from the gold (your corrections).


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


def build_evidence_cell(row, taxonomy_entries, eth_flag, gen_flag, sex_flag):
    """"why + evidence" per flagged axis, using the CURRENT engine's live flag as
    WHY (so removed flags never appear) and audit_evidence for WHERE (which term
    matched, in which field, + snippet). '' when nothing is flagged."""
    axes = (
        ("ETHNIC", eth_flag, lambda r: ae.ethnic_evidence(r, taxonomy_entries)),
        ("GENDER", gen_flag, ae.gender_evidence),
        ("SEXUAL", sex_flag, ae.sexual_evidence),
    )
    blocks = []
    for label, flag, evidence_fn in axes:
        flag = _cell(flag)
        if not flag:
            continue
        evidence = evidence_fn(row).strip() or "(no matching term re-scanned in the text)"
        blocks.append(f"{label} - why: {flag}  |  evidence: {evidence}")
    return "\n".join(blocks)


def _review_basis(name, cfg):
    """The workbook whose rows become this dataset's review sheet.

    The gold copy when the dataset has one: it carries the decisions and the
    "Formerly X" verdicts from earlier audit rounds, which a reviewer wants to
    see. A dataset being classified for the first time has no gold -- and does
    not need one, because the classified workbook holds exactly the same
    columns apart from the verdict column. Reading it here is what lets a new
    year be reviewed at all; previously the dataset was skipped and the review
    workbook came out empty.
    """
    gold_rel = cfg.get("gold_file")
    gold_path = (bootstrap.PROJECT_ROOT / gold_rel) if gold_rel else None
    if gold_path and gold_path.exists():
        return gold_path, "gold"
    raw = bootstrap.PROJECT_ROOT / cfg["raw_file"]
    if raw.exists():
        return raw, "classified workbook"
    return None, None


def build_sheet(name, cfg):
    """Return (sheet_name, DataFrame) mirroring one dataset's workbook: all its
    columns minus OMIT_COLS, plus the evidence column. None if nothing to read."""
    gold_path, which = _review_basis(name, cfg)
    if gold_path is None:
        print(f"[{name}] no gold copy and no classified workbook -- skipped.")
        return None
    print(f"[{name}] building from {which}: {gold_path.name}")

    tax_df = _read_excel_safe(bootstrap.PROJECT_ROOT / cfg["taxonomy_file"],
                              sheet_name=cfg["taxonomy_sheet"], dtype=str)
    taxonomy_entries = et.build_taxonomy(tax_df)

    df = _read_excel_safe(gold_path, sheet_name=cfg["data_sheet"], dtype=str).fillna("")

    # Live flags + evidence from the current engine. Classification columns stay
    # as the gold has them; only the three flag columns are overwritten.
    eth_f, gen_f, sex_f, evidence = [], [], [], []
    for _, r in df.iterrows():
        ef = classify_row(r, taxonomy_entries)[3]
        gf = classify_gender(r)[1]
        sf = classify_sexual(r)[1]
        eth_f.append(ef); gen_f.append(gf); sex_f.append(sf)
        evidence.append(build_evidence_cell(r, taxonomy_entries, ef, gf, sf))
    df["Classification Flag"] = eth_f
    df["Gender Classification Flag"] = gen_f
    df["Sexual Classification Flag"] = sex_f
    df[EVIDENCE_COL] = evidence

    # Review sheet = flagged rows only (any axis flag from the current engine).
    df = df[[bool(_cell(e) or _cell(g) or _cell(s))
             for e, g, s in zip(eth_f, gen_f, sex_f)]]

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

    import paths
    out_path = paths.REVIEW_FILE
    def _write(target):
        with pd.ExcelWriter(target, engine="openpyxl") as writer:
            for sheet_name, df in sheets:
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                print(f"  sheet '{sheet_name}': {len(df)} rows, {len(df.columns)} columns")

    # Built in full beside the target, then swapped in, so an interrupted run
    # cannot leave a half-written review workbook in its place.
    safe_save.save_via(out_path, _write)

    print(f"\nWritten to: {out_path}")
    print("Read-only mirror of the gold sheets (+ evidence column). No gold file modified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
