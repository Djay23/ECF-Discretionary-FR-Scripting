"""
paths.py
--------
Where the project's files live, and how they are found.

The whole point of this module is that FILENAMES ARE NOT CODE. Someone sets up
the working folders next to this project, drops their workbooks in, and everything
downstream discovers them. Renaming a workbook must never require a code edit --
that mistake has already cost this project a silent no-op run.

The convention
    Data Sheets/    the funding-request workbooks to classify. Every workbook
                    here is a dataset, except the reserved names below.
    Taxonomy/       the taxonomy definitions workbook (and, optionally, the
                    hand-audited GOLD snapshots).
    Final Review/   the hand-audited copies that corrections are written into.

Going forward, name a new workbook "Discretionary Funding Requests - 2026.xlsx"
and it becomes dataset "2026" with no code change. A dataset is named after the
year(s) in its filename:
    "Discretionary Funding Requests - 2026.xlsx"  -> "2026"
    "FR_Engine - 2023-2024.xlsx"                  -> "2023_24"
    "anything else.xlsx"                          -> "anything else"
Gold and Final Review files are matched to a dataset by that same name, so
"FR - 2025 (GOLD-AUDIT).xlsx" pairs with any 2025 source automatically.

Nothing here raises on a missing optional file. Callers decide what is fatal;
this module only reports what it found.
"""

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Folder on the Desktop that holds the working folders for a fresh install.
WORKSPACE_NAME = "ECF Classification"


def tool_dir() -> Path:
    """Where the running tool actually lives, for the "did someone already put
    data next to it" check below. Frozen into a .exe (PyInstaller), PROJECT_ROOT
    points at a throwaway temp extraction dir (sys._MEIPASS) that never has
    data next to it -- the folder that matters is wherever the .exe itself
    sits, so use that instead. Unfrozen, this is just PROJECT_ROOT as before."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return PROJECT_ROOT


def desktop_dir() -> Path:
    """The real Desktop. On managed Windows machines this is usually redirected
    into OneDrive, so the registry is asked before falling back to guesses."""
    if os.name == "nt":
        try:
            import winreg
            key = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
                value = winreg.QueryValueEx(k, "Desktop")[0]
            expanded = Path(os.path.expandvars(value))
            if expanded.exists():
                return expanded
        except OSError:
            pass
    for candidate in (Path.home() / "Desktop",
                      Path(os.environ.get("OneDrive", "")) / "Desktop"):
        if str(candidate) != "Desktop" and candidate.exists():
            return candidate
    return Path.home() / "Desktop"


def _looks_populated(root: Path) -> bool:
    """True if this folder is already being used as a workspace -- i.e. it has a
    Data Sheets folder with at least one workbook in it."""
    data = root / "Data Sheets"
    return data.is_dir() and any(p.suffix.lower() == ".xlsx" for p in data.iterdir())


def resolve_workspace() -> Path:
    """Where the working folders live.

    Order matters. An existing installation must keep working untouched, so a
    project folder that already holds data always wins -- repointing it at an
    empty Desktop folder would look exactly like the data had been deleted.
    """
    override = os.environ.get("ECF_WORKSPACE")
    if override:
        return Path(override).expanduser()
    if _looks_populated(tool_dir()):
        return tool_dir()
    return desktop_dir() / WORKSPACE_NAME


WORKSPACE = resolve_workspace()

DATA_DIR = WORKSPACE / "Data Sheets"
TAXONOMY_DIR = WORKSPACE / "Taxonomy"
FINAL_REVIEW_DIR = WORKSPACE / "Final Review"
# Audited GOLD snapshots. Their own folder so Taxonomy/ holds only the
# definitions workbook -- one folder, one job. Gold copies used to live in
# Taxonomy/, so that is still searched as a fallback and an installation that
# has not been rearranged keeps working untouched.
GOLD_DIR = WORKSPACE / "Gold"

# Older checkouts called it "Post Review". Accept it so a half-renamed folder
# doesn't silently produce zero datasets.
if not FINAL_REVIEW_DIR.exists() and (WORKSPACE / "Post Review").exists():
    FINAL_REVIEW_DIR = WORKSPACE / "Post Review"

# The workbook reviewers type their corrections into.
REVIEW_FILE = DATA_DIR / "Classification Review.xlsx"

# The sheet inside every funding-request workbook.
DATA_SHEET = "Discretionary Funding Requests"
TAXONOMY_SHEET = "Ethnic and Cultural Origins"

# Workbooks in Data Sheets/ that are NOT datasets.
RESERVED_STEMS = {
    "classification review",
}
# Substrings that mark a workbook as an artefact rather than a source dataset.
RESERVED_MARKERS = ("review_report", "flagreview", "engine output", "dashboard")

# Workbooks that predate the "... - {year}.xlsx" convention and are deliberately
# NOT being renamed. New files never need an entry here -- put the year in the
# filename instead and discovery handles it.
LEGACY_NAMES = {
    "fr testing": "2025",
}


README_GOLD = """
GOLD - what goes in this folder
===============================

PUT HERE: The audited GOLD copies, if you have any.

          Name them with the year and the word GOLD, for example:
              FR - 2026 (GOLD-AUDIT).xlsx

          A GOLD file is a hand-checked snapshot of a year's classifications,
          kept as a record of what was decided. You do NOT need one to use the
          tool. A year without a GOLD file works perfectly well: the review
          workbook is built from the classified workbook instead.

          Where a GOLD file does exist, menu option 2 builds that year's review
          sheet from it, so reviewers see the decisions already made.

NOTHING IN THIS FOLDER IS EVER MODIFIED BY THE TOOL. It only reads from here.

Older setups kept these files in the Taxonomy folder. That still works, so
there is no rush to move them.
"""


README_START = f"""
ECF DISCRETIONARY FUNDING REQUESTS - CLASSIFICATION
===================================================

This folder holds the files the classification tool reads and writes.
There are four folders, and each one has a README.txt explaining exactly
what belongs in it. Open those if you are unsure.

    Data Sheets     the funding request workbooks to be classified
    Taxonomy        the taxonomy definitions workbook, and nothing else
    Gold            audited snapshots of past years, if you have any
    Final Review    the audited copies your corrections are written into

THE ONE RULE
------------
Name each funding request workbook with its year:

    Discretionary Funding Requests - 2026.xlsx

The tool reads the year from the filename. That is how it knows which files
belong together. Everything else is automatic.

TO RUN THE TOOL
---------------
Double-click "ECF Classification.exe" in the tool folder, then choose an
option from the menu. Windows may show a "Windows protected your PC" warning
the first time -- click "More info", then "Run anyway"; that's expected for a
new unsigned program. Press C on that menu at any time to see what the tool
has found and what is still missing.

Close any workbook in Excel before running the tool. Excel locks files it has
open, and the tool cannot write to a locked file. It will tell you which one.
"""

README_DATA = """
DATA SHEETS - what goes in this folder
======================================

PUT HERE: the funding request workbooks you want classified.
          One workbook per year.

NAME THEM: Discretionary Funding Requests - 2026.xlsx
           ^ the year matters. The tool reads it from the filename and uses
             it to match this workbook to its GOLD copy in the Taxonomy
             folder and its copy in the Final Review folder.

Each workbook needs a sheet named:  Discretionary Funding Requests

WHAT THE TOOL DOES WITH THEM
----------------------------
Menu option 1 (Run classification) reads a workbook from this folder and
writes the ethnic, gender and sexual identity columns back into THAT SAME
workbook. The file is updated in place, so keep a copy elsewhere if you need
the original untouched.

ALSO CREATED HERE (you do not add these yourself)
-------------------------------------------------
Classification Review.xlsx
    Created by menu option 2. This is the file you type your corrections
    into. Do not rename it.

stakeholder_dashboard*.html
    Created by menu option 4. Open it in a web browser.
"""

README_TAXONOMY = """
TAXONOMY - what goes in this folder
===================================

PUT HERE: The taxonomy definitions workbook. Exactly one. Nothing else.

          Name it so it contains the word "Definitions", for example:
              Taxonomy - Definitions.xlsx

          It needs a sheet named:  Ethnic and Cultural Origins

          This file tells the tool which terms map to which ethnic and
          cultural categories. The classification cannot run without it.

The audited GOLD copies belong in the Gold folder, not here. (If yours are
still in this folder they will keep working, so there is no rush to move them.)

NOTHING IN THIS FOLDER IS EVER MODIFIED BY THE TOOL. It only reads from here.

Backup copies are ignored, so a file with "backup" or "copy" in its name will
never be mistaken for the real one.
"""

README_FINAL = """
FINAL REVIEW - what goes in this folder
=======================================

PUT HERE: the copies that your hand-audited corrections get written into.

NAME THEM: with the matching year, for example:
               Discretionary Funding Requests - 2026 (GOLD) Final review.xlsx

           The tool matches this file to a year's data by the year in the
           filename. That is the only thing linking them.

Each workbook needs a sheet named:  Discretionary Funding Requests

HOW THESE FILES GET UPDATED
---------------------------
1. Menu option 2 builds Classification Review.xlsx in the Data Sheets folder.
2. You type your corrections into that review workbook and save it.
3. Menu option 3 copies those corrections into the matching file in THIS
   folder.

Option 3 always shows you every single cell it is about to change and asks
you to confirm before writing anything. Press Enter to cancel.

Corrections are matched to rows by funding request ID, never by row position,
so sorting or inserting rows cannot put a correction on the wrong row.

The GOLD files in the Taxonomy folder are never written to. Only the files in
this folder are updated.
"""


def _is_workbook(p: Path) -> bool:
    """A real .xlsx, not an Excel lock file (~$...) or a hidden temp file."""
    return (p.suffix.lower() == ".xlsx"
            and not p.name.startswith("~$")
            and not p.name.startswith("."))


def _is_backup(p: Path) -> bool:
    """Copies kept alongside the real thing must never win a match."""
    low = p.name.lower()
    return any(m in low for m in (".backup", "backup", " copy", "(copy)", " old", ".old"))


def dataset_name_from(filename: str) -> str:
    """Derive a dataset name from a workbook filename.

    A year range wins over a single year, so "FR - 2023-2024 (GOLD).xlsx"
    becomes "2023_24" rather than "2023". Falls back to the bare stem when the
    filename carries no year at all."""
    stem = Path(filename).stem
    if stem.lower() in LEGACY_NAMES:
        return LEGACY_NAMES[stem.lower()]
    m = re.search(r"(20\d{2})\s*[-–_]\s*(20\d{2}|\d{2})", stem)
    if m:
        start, end = m.group(1), m.group(2)
        return f"{start}_{end[-2:]}"
    m = re.search(r"(20\d{2})", stem)
    if m:
        return m.group(1)
    return stem


def _match_by_name(directory: Path, name: str, marker: Optional[str] = None):
    """The workbook in `directory` whose derived dataset name is `name`.
    `marker` (e.g. "gold") further restricts to filenames containing it."""
    if not directory.exists():
        return None
    hits = []
    for p in sorted(directory.iterdir()):
        if not _is_workbook(p) or _is_backup(p):
            continue
        if marker and marker.lower() not in p.name.lower():
            continue
        if dataset_name_from(p.name) == name:
            hits.append(p)
    return hits[0] if hits else None


def taxonomy_file() -> Optional[Path]:
    """The taxonomy definitions workbook. Prefers a filename containing
    'definition'; otherwise the only non-GOLD workbook in Taxonomy/."""
    if not TAXONOMY_DIR.exists():
        return None
    books = [p for p in sorted(TAXONOMY_DIR.iterdir()) if _is_workbook(p)]
    for p in books:
        if "definition" in p.name.lower():
            return p
    plain = [p for p in books if "gold" not in p.name.lower()
             and "backup" not in p.name.lower()]
    return plain[0] if len(plain) == 1 else None


def source_workbooks():
    """Every workbook in Data Sheets/ that is a dataset to classify."""
    if not DATA_DIR.exists():
        return []
    out = []
    for p in sorted(DATA_DIR.iterdir()):
        if not _is_workbook(p):
            continue
        low = p.stem.lower()
        if low in RESERVED_STEMS or any(m in low for m in RESERVED_MARKERS):
            continue
        out.append(p)
    return out


@dataclass(frozen=True)
class Discovered:
    name: str
    source: Path                  # read AND written by the engines
    gold: Optional[Path]          # hand-audited snapshot; review report input
    final_review: Optional[Path]  # target of apply_review_corrections
    taxonomy: Optional[Path]


def discover():
    """Map every source workbook to its partner files. Returns {name: Discovered},
    ordered by name so the oldest dataset reads first."""
    tax = taxonomy_file()
    found = {}
    for src in source_workbooks():
        name = dataset_name_from(src.name)
        if name in found:            # first one wins; report the collision
            continue
        found[name] = Discovered(
            name=name,
            source=src,
            gold=(_match_by_name(GOLD_DIR, name, marker="gold")
                  or _match_by_name(TAXONOMY_DIR, name, marker="gold")),
            final_review=_match_by_name(FINAL_REVIEW_DIR, name),
            taxonomy=tax,
        )
    return dict(sorted(found.items()))


def ensure_workspace():
    """Create the working folders and their READMEs if missing.

    Safe to call on every start: existing folders are left alone, and an
    existing README is never overwritten so notes someone added to one
    survive. Returns the folders it had to create (empty when all present)."""
    created = []
    for folder, text in ((DATA_DIR, README_DATA),
                         (TAXONOMY_DIR, README_TAXONOMY),
                         (GOLD_DIR, README_GOLD),
                         (FINAL_REVIEW_DIR, README_FINAL)):
        if not folder.exists():
            folder.mkdir(parents=True, exist_ok=True)
            created.append(folder)
        readme = folder / "README.txt"
        if not readme.exists():
            readme.write_text(text.strip() + "\n", encoding="utf-8")

    start = WORKSPACE / "START HERE.txt"
    if not start.exists():
        WORKSPACE.mkdir(parents=True, exist_ok=True)
        start.write_text(README_START.strip() + "\n", encoding="utf-8")
    return created


def describe():
    """Human-readable inventory, used by the launcher's health check."""
    lines = [f"workspace      {WORKSPACE}", ""]
    for folder, label in ((DATA_DIR, "Data Sheets"),
                          (TAXONOMY_DIR, "Taxonomy"),
                          (GOLD_DIR, "Gold"),
                          (FINAL_REVIEW_DIR, "Final Review")):
        lines.append(f"{label:<14} {'OK  ' if folder.exists() else 'MISSING'}  {folder}")
    tax = taxonomy_file()
    lines.append(f"{'taxonomy file':<14} {'OK  ' if tax else 'MISSING'}  "
                 f"{tax.name if tax else '(none found in Taxonomy/)'}")
    for name, d in discover().items():
        lines.append(f"\n  dataset '{name}'")
        lines.append(f"      source        {d.source.name}")
        lines.append(f"      gold          {d.gold.name if d.gold else '(none)'}")
        lines.append(f"      final review  {d.final_review.name if d.final_review else '(none)'}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(describe())
