import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

ENGINE_ROOT = Path(__file__).resolve().parent   # "Engine 1 and 2"
PROJECT_ROOT = ENGINE_ROOT.parent                 # repo root (holds Taxonomy/, Data Sheets/)

for sub in ("Pipeline", "Constants", "Semantic_Engine", "Auditing"):
    p = str(ENGINE_ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))
from dataset_config import active_config


@dataclass(frozen=True)
class Dataset:
    name: str
    raw_file: Path
    output_file: Path
    gold_file: Optional[Path]
    # The audited copy that apply_review_corrections.py writes into: engine
    # output PLUS the reviewer's applied edits. This, not gold_file, is the
    # finished picture of a dataset.
    final_review_file: Optional[Path]
    data_sheet: str
    taxonomy_file: Path
    taxonomy_sheet: str


def dataset():
    """Resolve the active dataset to absolute paths and validate the inputs.
    Call this at the start of an entry point's main()."""
    name, cfg = active_config()
    gold = cfg["gold_file"]
    ds = Dataset(
        name=name,
        raw_file=PROJECT_ROOT / cfg["raw_file"],
        output_file=PROJECT_ROOT / cfg["output_file"],
        gold_file=(PROJECT_ROOT / gold) if gold else None,
        final_review_file=((PROJECT_ROOT / cfg["final_review_file"])
                           if cfg.get("final_review_file") else None),
        data_sheet=cfg["data_sheet"],
        taxonomy_file=PROJECT_ROOT / cfg["taxonomy_file"],
        taxonomy_sheet=cfg["taxonomy_sheet"],
    )
    if not ds.raw_file.exists():
        raise SystemExit(f"Dataset '{name}': raw file not found at {ds.raw_file}")
    if not ds.taxonomy_file.exists():
        raise SystemExit(f"Dataset '{name}': taxonomy file not found at {ds.taxonomy_file}")
    return ds

# Windows consoles default to cp1252, which can't encode the unicode arrows
# ("→") and em-dashes in the engines' summary printouts — that raised
# UnicodeEncodeError mid-run (after the workbook had already saved). Reconfigure
# stdout/stderr to UTF-8 once here so every entry point that imports bootstrap
# prints safely without needing PYTHONIOENCODING set. No-op where UTF-8 is
# already active; guarded for streams that don't support reconfigure.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
