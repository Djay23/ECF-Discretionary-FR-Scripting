"""
dataset_config.py
Which funding-request datasets exist, and where their files are.

Datasets are DISCOVERED, not listed here: every workbook in "Data Sheets/"
is one, and its gold + Final Review partners are matched by the year in the
filename. See paths.py for the convention. Adding next year's data means
dropping the workbook in the folder -- no code edit.

Pick which dataset to work on with the ECF_DATASET environment variable, or
set ACTIVE_DATASET below. Leaving ACTIVE_DATASET as None uses the first
dataset found (alphabetically, so the oldest year).
"""

import os

import paths

ACTIVE_DATASET = None


def _build():
    """{name: cfg} in the shape the rest of the project expects. Paths are
    ABSOLUTE, not relative to PROJECT_ROOT: the workspace (Data Sheets/
    Taxonomy/Final Review) can live outside the repo entirely -- a Desktop
    folder, or a Docker bind mount -- so there may be no relative path to
    express. Every consumer joins these as `bootstrap.PROJECT_ROOT / cfg[...]`,
    and pathlib's "/" returns an absolute right-hand side unchanged, so
    consumers keep working with no change on either side of the split."""
    out = {}
    for name, d in paths.discover().items():
        out[name] = {
            "raw_file": str(d.source).replace("\\", "/"),
            # The engines write their columns back into the same workbook.
            "output_file": str(d.source).replace("\\", "/"),
            "gold_file": (str(d.gold).replace("\\", "/")
                          if d.gold else None),
            "final_review_file": (str(d.final_review).replace("\\", "/")
                                  if d.final_review else None),
            "data_sheet": paths.DATA_SHEET,
            "taxonomy_file": (str(d.taxonomy).replace("\\", "/")
                              if d.taxonomy else None),
            "taxonomy_sheet": paths.TAXONOMY_SHEET,
        }
    return out


DATASETS = _build()


def active_config():
    """Return (name, config_dict) for the active dataset. Reads the env var at
    call time so an override always takes effect."""
    if not DATASETS:
        raise SystemExit(
            f"No datasets found.\n"
            f"Put at least one funding-request workbook (.xlsx) in:\n"
            f"    {paths.DATA_DIR}\n"
            f"Name it with its year, e.g. 'FR 2026.xlsx'.")

    name = os.environ.get("ECF_DATASET") or ACTIVE_DATASET or next(iter(DATASETS))
    if name not in DATASETS:
        valid = ", ".join(DATASETS)
        raise SystemExit(
            f"Unknown dataset '{name}'. Found: {valid}.\n"
            f"Datasets are named after the year in the workbook filename, in "
            f"'{paths.DATA_DIR.name}'. Set ECF_DATASET to one of the names above.")
    return name, DATASETS[name]
