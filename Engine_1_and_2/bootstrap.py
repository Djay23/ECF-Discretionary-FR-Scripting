import sys
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parent   # "Engine 1 and 2"
PROJECT_ROOT = ENGINE_ROOT.parent                 # repo root (holds Taxonomy/, Data Sheets/)

for sub in ("Pipeline", "Constants", "Semantic_Engine", "Auditing"):
    p = str(ENGINE_ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

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
