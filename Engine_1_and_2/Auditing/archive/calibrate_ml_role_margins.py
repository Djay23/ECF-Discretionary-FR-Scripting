import sys
import shutil
import tempfile
import os
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # Engine 1 and 2
import bootstrap

sys.path.insert(0, str(bootstrap.PROJECT_ROOT / "Engine_1_and_2" / "Pipeline"))
sys.path.insert(0, str(bootstrap.PROJECT_ROOT / "Engine_1_and_2" / "Semantic_Engine"))

import pandas as pd

import ethnic_taggerv3 as et
from extractors import (
    extract_taxonomy_candidates,
    extract_compound_candidates,
    extract_pattern_candidates,
    extract_country_candidates,
    extract_broad_identity_candidates,
)
from classify_pipeline import STAKEHOLDER_REVIEWED_COL
from ml_arbiter import nli_role

"""
calibrate_ml_role_margins.py
-----------------------------
One-off analysis script (not part of the shipping pipeline). Runs the real
vendored NLI cross-encoder over every candidate the regex frames currently
default to "served" across the live 448 rows in Taxonomy/AUDITED_FR_GOLD.xlsx
(the current gold record -- see memory: gold-standard-location), and
histograms the margin between the arbiter's best weak-role guess and
"served". Used to pick real ML_ROLE_NOTE_MARGIN / ML_ROLE_OVERRIDE_MARGIN
boundaries in classify_pipeline.py instead of assuming the inherited 0.5/1.5
values are right for the expanded (topic/aspirational/allyship) hypothesis set.

Skips rows already marked stakeholder-reviewed (column AN non-blank) --
same exclusion classify_row() applies in production, so the calibration
sample matches what the arbiter will actually see live.

Run:
    .venv/Scripts/python.exe Engine_1_and_2/Auditing/calibrate_ml_role_margins.py
"""

def _extract(txt, name_for_role, taxonomy_entries):
    return (
        extract_taxonomy_candidates(txt, taxonomy_entries, name_for_role)
        + extract_compound_candidates(txt, name_for_role)
        + extract_pattern_candidates(txt, name_for_role)
        + extract_country_candidates(txt, name_for_role)
        + extract_broad_identity_candidates(txt, name_for_role)
    )


def _read_excel_safe(path, **kwargs):
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

    margins = []
    best_role_counts = Counter()
    skipped_reviewed = 0
    scored = 0

    for _, row in data_df.iterrows():
        an_val = row.get(STAKEHOLDER_REVIEWED_COL, "")
        # NaN-safe: a blank cell from pd.read_excel is a float NaN, not ""
        # -- `x or ""` is wrong here since NaN is truthy in Python.
        if not pd.isna(an_val) and str(an_val).strip():
            skipped_reviewed += 1
            continue

        body_text, name_text = et.get_body_and_name_texts(row)
        if not body_text.strip():
            continue
        candidates = _extract(body_text, name_text, taxonomy_entries)

        for c in candidates:
            if c.get("role") != "served" or not c.get("span") or not c.get("context"):
                continue
            scores = nli_role(c["span"], c["context"])
            best = scores["best_role"]
            if best in ("served", "negated"):
                continue
            margin = scores[best] - scores["served"]
            margins.append(margin)
            best_role_counts[best] += 1
            scored += 1

    print(f"Rows skipped (already stakeholder-reviewed): {skipped_reviewed}")
    print(f"Candidates scored (regex role == 'served', best weak role != served/negated): {scored}")
    print(f"\nBest-role distribution among scored candidates:")
    for role, n in best_role_counts.most_common():
        print(f"  {role:14} {n}")

    if not margins:
        print("\nNo candidates to histogram.")
        return

    margins.sort()
    buckets = [(-999, 0.0), (0.0, 0.5), (0.5, 1.0), (1.0, 1.5), (1.5, 2.0), (2.0, 999)]
    print(f"\nMargin histogram ({len(margins)} candidates):")
    for lo, hi in buckets:
        count = sum(1 for m in margins if lo <= m < hi)
        label = f"[{lo}, {hi})" if hi != 999 else f"[{lo}, inf)"
        print(f"  {label:14} {count}")

    def pct(p):
        idx = min(len(margins) - 1, int(len(margins) * p))
        return margins[idx]

    print(f"\nPercentiles: p25={pct(0.25):.2f}  p50={pct(0.50):.2f}  "
          f"p75={pct(0.75):.2f}  p90={pct(0.90):.2f}  p95={pct(0.95):.2f}")
    print("\nUse this distribution to sanity-check ML_ROLE_NOTE_MARGIN=0.5 / "
          "ML_ROLE_OVERRIDE_MARGIN=1.5 in classify_pipeline.py before trusting them.")


if __name__ == "__main__":
    main()
