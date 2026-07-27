"""
dataset_config.py
Single source of truth for which funding-request dataset the engine runs on.
Change ACTIVE_DATASET to switch, or set the ECF_DATASET environment variable
for a one-off run without editing this file.
"""

import os

ACTIVE_DATASET = "2025"

DATASETS = {
    "2025": {
        "raw_file": "Data Sheets/FR testing.xlsx",
        "output_file": "Data Sheets/FR testing.xlsx",
        "gold_file": "Taxonomy/AUDITED_FR_GOLD.xlsx",
        "data_sheet": "Discretionary Funding Requests",
        "taxonomy_file": "Taxonomy/Taxonomy - Definitions.xlsx",
        "taxonomy_sheet": "Ethnic and Cultural Origins",
    },
    "2023_24": {
        "raw_file": "Data Sheets/FR_Engine - 2023-2024.xlsx",
        "output_file": "Data Sheets/FR_Engine - 2023-2024 (engine output).xlsx",
        "gold_file": None,
        "data_sheet": "Discretionary Funding Requests",
        "taxonomy_file": "Taxonomy/Taxonomy - Definitions.xlsx",
        "taxonomy_sheet": "Ethnic and Cultural Origins",
    },
}


def active_config():
    """Return (name, config_dict) for the active dataset. Reads the env var at
    call time so an override always takes effect. Sheet names and relative
    paths only -- no filesystem checks here, so importing this module is safe
    and side-effect-free."""
    name = os.environ.get("ECF_DATASET", ACTIVE_DATASET)
    if name not in DATASETS:
        valid = ", ".join(DATASETS)
        raise SystemExit(
            f"Unknown dataset '{name}'. Valid options: {valid}. "
            f"Set ACTIVE_DATASET in dataset_config.py or the ECF_DATASET env var."
        )
    return name, DATASETS[name]
