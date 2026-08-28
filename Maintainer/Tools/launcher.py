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
import runpy
import shutil
import subprocess
import sys
from pathlib import Path

# Frozen into a .exe (PyInstaller), the bundled project files are unpacked into
# a throwaway temp dir at sys._MEIPASS, not sitting next to the .exe itself --
# that's the only thing that changes here.
#
# Unfrozen, this file can be run from two different homes -- Maintainer/Tools/
# in the checked-out repo, or wherever a maintainer copies just this script --
# so don't assume a fixed number of parent hops (that broke when this file
# moved from Tools/ to Maintainer/Tools/, one level deeper). Instead walk up
# until a folder containing "Engine_1_and_2" is found; that's always the
# actual project root.
if getattr(sys, "frozen", False):
    PROJECT_ROOT = Path(sys._MEIPASS)
else:
    PROJECT_ROOT = Path(__file__).resolve().parent
    while not (PROJECT_ROOT / "Engine_1_and_2").is_dir():
        parent = PROJECT_ROOT.parent
        if parent == PROJECT_ROOT:
            # Reached the filesystem root without finding it -- fall back to
            # the old assumption rather than looping forever.
            PROJECT_ROOT = Path(__file__).resolve().parent.parent
            break
        PROJECT_ROOT = parent
ENGINE = PROJECT_ROOT / "Engine_1_and_2"
AUDIT = ENGINE / "Auditing"

sys.path.insert(0, str(ENGINE))
import paths  # noqa: E402  (needs ENGINE on sys.path first)


def datasets():
    """Every dataset found in the Data Sheets folder, newest last.
    Nothing here is hardcoded: drop a workbook in the folder and it appears."""
    return list(paths.discover().values())


def lockable():
    """Files a user commonly leaves open in Excel, which blocks writing."""
    files = [paths.REVIEW_FILE]
    for d in datasets():
        files.append(d.source)
        if d.final_review:
            files.append(d.final_review)
    return files

BAR = "=" * 62


def clear():
    if os.name == "nt":
        os.system("cls")
        return
    # The Docker image (python:3.13-slim) has no `clear` binary. Check before
    # shelling out to it -- os.system("clear") when it's missing would print
    # "sh: 1: clear: not found" on every screen redraw. Fall back to the raw
    # ANSI "clear screen, move cursor home" escape, which any real terminal
    # (including the container's) understands directly.
    if shutil.which("clear"):
        os.system("clear")
    else:
        print("\033[2J\033[H", end="")


def ask(prompt_text=""):
    """input() that cannot crash the tool. A closed or redirected stdin (which
    happens when this is launched by something other than a console window)
    reads as EOF. Returns None in that case -- distinct from "", so the menu
    can stop instead of spinning forever on an input it will never get."""
    try:
        return input(prompt_text)
    except (EOFError, KeyboardInterrupt):
        print()
        return None


def pause():
    ask("\nPress Enter to return to the menu...")


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


def warn_if_locked(files):
    """Return True if it's safe to continue."""
    locked = [p for p in files if is_locked(p)]
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
    if getattr(sys, "frozen", False):
        # Frozen, sys.executable IS this tool -- a plain [sys.executable, script]
        # call would just relaunch the menu. --run-script tells the child
        # process (still this same .exe) to execute `script` instead of
        # drawing the menu again. See main() for the dispatch.
        cmd = [sys.executable, "--run-script", str(script), *args]
    else:
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
    if (ask("  Type Y to start, or press Enter to cancel: ") or "").strip().lower() != "y":
        return
    if not warn_if_locked(lockable()):
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
    if not warn_if_locked([paths.REVIEW_FILE]):
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
    print("  Step 2 of 2: write these changes into the Final Review files?")
    print("  (The list above shows every cell that would change.)")
    print(BAR)
    if (ask("\n  Type YES to write them, or press Enter to cancel: ") or "").strip() != "YES":
        print("\n  Cancelled. Nothing was written.")
        return pause()
    if not warn_if_locked(lockable()):
        return pause()
    print()
    if run(AUDIT / "apply_review_corrections.py", ["--apply"]) == 0:
        print("\n  Done. Your corrections are in the Final Review files.")
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

    # Running in the Docker image? Docker itself puts /.dockerenv in every
    # container, so this stays right even for someone on the host who has set
    # ECF_WORKSPACE by hand (a documented override -- see paths.py). Worth
    # showing so a confused user can say exactly where their files are
    # instead of "it's not working".
    in_container = Path("/.dockerenv").exists()
    print(f"\n  Running in the Docker container: {'yes' if in_container else 'no'}")
    if in_container:
        print(f"  Your workspace folder is mapped to:\n     {paths.WORKSPACE}")
    else:
        print(f"\n  Working folders are in:\n     {paths.WORKSPACE}")

    print("\n  Folders:")
    for folder in (paths.DATA_DIR, paths.TAXONOMY_DIR, paths.FINAL_REVIEW_DIR):
        if folder.exists():
            print(f"     OK       {folder.name}")
        else:
            print(f"     MISSING  {folder.name}   -- create this folder")
            ok = False

    tax = paths.taxonomy_file()
    print("\n  Taxonomy definitions:")
    if tax:
        print(f"     OK       {tax.name}")
    else:
        print(f"     MISSING  no definitions workbook in '{paths.TAXONOMY_DIR.name}'")
        ok = False

    print("\n  Datasets found:")
    found = datasets()
    if not found:
        print(f"     NONE     put a funding-request workbook in "
              f"'{paths.DATA_DIR.name}',")
        print( "                named with its year, e.g. 'FR 2026.xlsx'")
        ok = False
    for d in found:
        print(f"     {d.name}")
        print(f"        source        {d.source.name}")
        print(f"        gold          {d.gold.name if d.gold else '(none yet)'}")
        print(f"        final review  "
              f"{d.final_review.name if d.final_review else '(none yet)'}")

    print("\n  Files currently open in Excel:")
    locked = [p for p in lockable() if is_locked(p)]
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


def first_run_setup():
    """Create the working folders (and their READMEs) if they aren't there yet,
    and tell the user where they are. Does nothing on later runs."""
    try:
        created = paths.ensure_workspace()
    except OSError as e:
        clear()
        print(f"{BAR}\n  COULD NOT CREATE THE WORKING FOLDERS\n{BAR}\n")
        print(f"  Tried to create them in:\n      {paths.WORKSPACE}\n")
        print(f"  Windows said: {e}\n")
        print( "  This is usually a permissions problem, or OneDrive still")
        print( "  syncing. Wait for OneDrive to finish, then try again.")
        ask("\nPress Enter to close...")
        return False

    if created:
        clear()
        print(f"{BAR}\n  FOLDERS CREATED\n{BAR}\n")
        print( "  Your working folders have been set up here:\n")
        print(f"      {paths.WORKSPACE}\n")
        for folder in created:
            print(f"      {folder.name}")
        print("\n  Each one contains a README.txt explaining exactly what")
        print( "  files belong in it and what the tool does with them.")
        print( "  There is also a START HERE.txt in the main folder.\n")
        print( "  Put your workbooks in those folders, then run this again.")
        ask("\nPress Enter to close...")
        return False
    return True


def menu():
    if not first_run_setup():
        return 0

    found = datasets()
    if not found:
        clear()
        print(f"{BAR}\n  NO DATA FOUND\n{BAR}\n")
        print( "  There are no funding-request workbooks in:\n")
        print(f"      {paths.DATA_DIR}\n")
        print( "  Put at least one .xlsx there, named with its year, e.g.")
        print( "      Discretionary Funding Requests - 2026.xlsx\n")
        print( "  The README.txt in that folder explains what is expected.")
        ask("\nPress Enter to close...")
        return 1

    idx = 0
    while True:
        d = found[idx]
        dataset = label = d.name
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

  D.  Switch dataset  ({idx + 1} of {len(found)}: {", ".join(x.name for x in found)})
  C.  Check everything is set up
  0.  Exit
""")
        c = ask("  Choose an option: ")
        if c is None:          # stdin closed -- stop rather than loop forever
            return 0
        c = c.strip().lower()

        if c == "1":
            do_classify(dataset, label)
        elif c == "2":
            do_review_report()
        elif c == "3":
            do_apply()
        elif c == "4":
            do_dashboard(dataset, label)
        elif c == "d":
            idx = (idx + 1) % len(found)
        elif c == "c":
            do_healthcheck()
        elif c == "0":
            print("\n  Goodbye.\n")
            return 0


def main():
    # Internal plumbing, not a user-facing option: when frozen, run() re-invokes
    # this same .exe with --run-script so a child process can execute one of the
    # engine scripts instead of drawing the menu again (see run()). Handled
    # before the menu draws, and before the try/except below, so the child's
    # sys.exit() from the script propagates as this process's real exit code.
    if len(sys.argv) > 1 and sys.argv[1] == "--run-script":
        script_path = sys.argv[2]
        sys.argv = [script_path, *sys.argv[3:]]
        try:
            runpy.run_path(script_path, run_name="__main__")
        except SystemExit as e:
            return e.code
        return 0

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
        ask("\nPress Enter to close...")
        return 1


if __name__ == "__main__":
    sys.exit(main())
