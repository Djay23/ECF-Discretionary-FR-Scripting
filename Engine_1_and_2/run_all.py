"""
run_all.py
----------
Single entry point for a full classification pass over
    Data Sheets/FR testing.xlsx  (sheet "Discretionary Funding Requests")

Runs, in order, against the same workbook:
    1. ethnic_taggerv3.main()  -> Ethnic 1/2/3 - FR6/7/8, Classification Flag,
                                  Semantic Suggestion (REVIEW)
    2. Gender_SexID.main()     -> Gender Id - FR9, Gender Classification Flag,
                                  Sexual Id - FR10, Sexual Classification Flag

Both engines are independent scripts that load and save the workbook by
header-name lookup, so running them sequentially is safe: the gender/sex pass
reopens the file the ethnic pass just saved and appends its own columns.

Historically only ethnic_taggerv3.py was documented/run, which left the four
gender/sex columns blank. Use this script (or run both engines) for a complete
output.

To Run:
    python Engine_1_and_2/run_all.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # Engine_1_and_2
import bootstrap  # (sets up sys.path for Pipeline/Constants/etc.)

import ethnic_taggerv3 as et
import Gender_SexID as gs

def main():
    print("=" * 70)
    print("STEP 1/2 — Ethnic classification (ethnic_taggerv3)")
    print("=" * 70)
    et.main()

    print("\n" + "=" * 70)
    print("STEP 2/2 — Gender + Sexual classification (Gender_SexID)")
    print("=" * 70)
    gs.main()

    print("\nAll engines complete. Ethnic, gender, and sexual columns written to "
          "Data Sheets/FR testing.xlsx.")

if __name__ == "__main__":
    main()
