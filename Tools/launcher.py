"""
launcher.py
-----------
The menu behind RUN.bat. Everything here is written for someone who does not
read code: no tracebacks ever reach the screen, every failure says what to do
next, and the one destructive action asks before it writes.

Not meant to be run directly -- double-click RUN.bat instead. (It works if you
do run it directly, as long as the dependencies are installed.)
"""

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENGINE = PROJECT_ROOT / "Engine_1_and_2"
AUDIT = ENGINE / "Auditing"

DATASETS = {
    "1": ("2025", "2025"),
    "2": ("2023_24", "2023-2024"),
}

# Files that the user commonly leaves open in Excel, which blocks writing.
LOCKABLE = [
    PROJECT_ROOT / "Data Sheets" / "FR testing.xlsx",
    PROJECT_ROOT / "Data Sheets" / "Classification Review.xlsx",
    PROJECT_ROOT / "Post Review" / "Discretionary FR - 2025 (GOLD) Final review.xlsx",
    PROJECT_ROOT / "Post Review" / "Discretionary FR - 2023-2024 (GOLD) Final review.xlsx",
]

BAR = "=" * 62


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def pause():
    input("\nPress Enter to return to the menu...")


def is_locked(path):
    """True if the file exists but is held open by Excel."""
    if not path.exists():
        return False
    try:
        with open(path, "rb"):
            return False
    except PermissionError:
        return True
    except OSError:
        return False


def warn_if_locked(paths):
    """Return True if it's safe to continue."""
    locked = [p for p in paths if is_locked(p)]
    if not locked:
        return True
    print("\n  These files are open in Excel and cannot be updated:\n")
    for p in locked:
        print(f"     - {p.name}")
    print("\n  Close them in Excel, then try again.")
    return False


def run(script, args=(), dataset=None, quiet=False):
    """Run one project script. Returns its exit code, or None if it could not
    start. Output streams straight to the window so the user sees progress."""
    env = dict(os.environ)
    if dataset:
        env["ECF_DATASET"] = dataset
    env["PYTHONIOENCODING"] = "utf-8"
    cmd = [sys.executable, str(script), *args]
    try:
        proc = subprocess.run(cmd, cwd=str(PROJECT_ROOT), env=env)
    except OSError as e:
        print(f"\n  Could not start the script: {e}")
        return None
    if proc.returncode != 0 and not quiet:
        print(f"\n  {BAR}")
        print("  That step did not finish successfully.")
        print("  Read the message above -- it usually says exactly what to fix")
        print("  (most often: a file is open in Excel, or a file was renamed).")
        print(f"  {BAR}")
    return proc.returncode


def do_classify(dataset, label):
    clear()
    print(f"{BAR}\n  RUN CLASSIFICATION  --  {label}\n{BAR}")
    print("\n  This reads the funding-request workbook and fills in the ethnic,")
    print("  gender and sexual-identity columns. It can take a few minutes.\n")
    if input("  Type Y to start, or press Enter to cancel: ").strip().lower() != "y":
        return
    if not warn_if_locked(LOCKABLE):
        return pause()
    print()
    if run(ENGINE / "run_all.py", dataset=dataset) == 0:
        print("\n  Done. The workbook has been updated.")
    pause()


def do_review_report():
    clear()
    print(f"{BAR}\n  BUILD REVIEW WORKBOOK\n{BAR}")
    print("\n  Creates 'Data Sheets/Classification Review.xlsx' -- the file you")
    print("  type your corrections into. It covers every dataset at once and")
    print("  does not change any gold file.\n")
    if not warn_if_locked([PROJECT_ROOT / "Data Sheets" / "Classification Review.xlsx"]):
        return pause()
    print()
    if run(AUDIT / "generate_review_report.py") == 0:
        print("\n  Done. Open 'Data Sheets/Classification Review.xlsx' to review.")
    pause()


def do_apply():
    """The only destructive action: always previews, always asks first."""
    clear()
    print(f"{BAR}\n  APPLY MY REVIEW CORRECTIONS\n{BAR}")
    print("\n  Step 1 of 2: previewing what would change. Nothing is written yet.\n")
    code = run(AUDIT / "apply_review_corrections.py", quiet=True)
    if code != 0:
        print("\n  Nothing was written. Fix the problem shown above and try again.")
        return pause()

    print(f"\n{BAR}")
    print("  Step 2 of 2: write these changes into the Post Review files?")
    print("  (The list above shows every cell that would change.)")
    print(BAR)
    if input("\n  Type YES to write them, or press Enter to cancel: ").strip() != "YES":
        print("\n  Cancelled. Nothing was written.")
        return pause()
    if not warn_if_locked(LOCKABLE):
        return pause()
    print()
    if run(AUDIT / "apply_review_corrections.py", ["--apply"]) == 0:
        print("\n  Done. Your corrections are in the Post Review files.")
    pause()


def do_dashboard(dataset, label):
    clear()
    print(f"{BAR}\n  BUILD STAKEHOLDER DASHBOARD  --  {label}\n{BAR}\n")
    if run(AUDIT / "generate_stakeholder_dashboard.py", dataset=dataset) == 0:
        print("\n  Done. Open the .html file in 'Data Sheets' to view it.")
    pause()


def do_healthcheck():
    clear()
    print(f"{BAR}\n  CHECK EVERYTHING IS SET UP\n{BAR}\n")
    ok = True

    print("  Required programs:")
    for mod in ("pandas", "numpy", "openpyxl"):
        try:
            __import__(mod)
            print(f"     OK       {mod}")
        except ImportError:
            print(f"     MISSING  {mod}")
            ok = False

    print("\n  Required files:")
    needed = [
        PROJECT_ROOT / "Taxonomy" / "Taxonomy - Definitions.xlsx",
        PROJECT_ROOT / "Data Sheets" / "FR testing.xlsx",
        PROJECT_ROOT / "Data Sheets" / "FR_Engine - 2023-2024.xlsx",
    ] + LOCKABLE[2:]
    for p in needed:
        if p.exists():
            print(f"     OK       {p.name}")
        else:
            print(f"     MISSING  {p.name}")
            print(f"                (expected in '{p.parent.name}')")
            ok = False

    print("\n  Files currently open in Excel:")
    locked = [p for p in LOCKABLE if is_locked(p)]
    if locked:
        for p in locked:
            print(f"     LOCKED   {p.name}  -- close it before running anything")
    else:
        print("     none -- good")

    print(f"\n{BAR}")
    print("  Everything looks correct." if ok else
          "  Something is missing. Show the lines marked MISSING to whoever\n"
          "  maintains this tool.")
    print(BAR)
    pause()


def menu():
    choice_ds = "1"
    while True:
        dataset, label = DATASETS[choice_ds]
        clear()
        print(f"""
{BAR}
  ECF DISCRETIONARY FR  --  CLASSIFICATION TOOL
{BAR}

  Working on dataset:  {label}

  1.  Run classification (fills in the FR columns)
  2.  Build review workbook (the file you correct)
  3.  Apply my review corrections
  4.  Build stakeholder dashboard

  D.  Switch dataset (currently {label})
  C.  Check everything is set up
  0.  Exit
""")
        c = input("  Choose an option: ").strip().lower()

        if c == "1":
            do_classify(dataset, label)
        elif c == "2":
            do_review_report()
        elif c == "3":
            do_apply()
        elif c == "4":
            do_dashboard(dataset, label)
        elif c == "d":
            choice_ds = "2" if choice_ds == "1" else "1"
        elif c == "c":
            do_healthcheck()
        elif c == "0":
            print("\n  Goodbye.\n")
            return 0


def main():
    try:
        return menu()
    except KeyboardInterrupt:
        print("\n\n  Stopped.\n")
        return 1
    except Exception as e:                      # never show a traceback
        print(f"\n{BAR}")
        print("  Something went wrong that this tool did not expect.")
        print(f"  Details: {type(e).__name__}: {e}")
        print("  Send this message to whoever maintains the tool.")
        print(BAR)
        input("\nPress Enter to close...")
        return 1


if __name__ == "__main__":
    sys.exit(main())
