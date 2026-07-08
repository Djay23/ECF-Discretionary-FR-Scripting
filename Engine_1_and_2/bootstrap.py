import sys
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parent   # "Engine 1 and 2"
PROJECT_ROOT = ENGINE_ROOT.parent                 # repo root (holds Taxonomy/, Data Sheets/)

for sub in ("Pipeline", "Constants", "Semantic_Engine", "Auditing"):
    p = str(ENGINE_ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)
