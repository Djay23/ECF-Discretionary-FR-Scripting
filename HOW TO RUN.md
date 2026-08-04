# How to run this tool

You do not need to know anything about code to use this.

## Starting it

**Double-click `RUN.bat`.**

That's it. A black window opens with a numbered menu. Type a number, press
Enter.

The very first time you do this on a new computer it will spend a minute or two
setting itself up, then create its working folders on your Desktop and tell you
where they are. That only happens once. If it says Python is not installed,
follow the instructions it prints — install Python from python.org, and **tick
"Add python.exe to PATH"** on the installer's first screen.

## Where the files go — the tool creates these for you

**The first time you run it, it creates a folder called `ECF Classification` on
your Desktop**, containing the three folders it needs and a `START HERE.txt`:

```
Desktop/ECF Classification/
    START HERE.txt
    Data Sheets/     README.txt
    Taxonomy/        README.txt
    Final Review/    README.txt
```

**Every one of those folders has a README.txt inside it** explaining exactly
what files belong there, how to name them, and what the tool does with them.
Open the README in a folder whenever you're unsure — it's written for exactly
that moment. They open in Notepad with a double-click.

In short:

| Folder | What belongs in it |
|---|---|
| **Data Sheets** | The funding-request workbooks to classify. One per year. |
| **Taxonomy** | `Taxonomy - Definitions.xlsx`, and the hand-audited GOLD copies. |
| **Final Review** | The audited copies your corrections get written into. |

The tool tells you where these folders are when it makes them, and option **C**
on the menu shows you the location again at any time.

**Name each new workbook with its year:**

```
Discretionary Funding Requests - 2026.xlsx
```

That's the only rule. The tool reads the year from the filename, calls that
dataset `2026`, and automatically pairs it with anything else carrying 2026 —
its GOLD file in `Taxonomy`, its copy in `Final Review`. Next year, drop in
`... - 2027.xlsx` and it appears in the menu on its own.

A dataset works fine before its GOLD and Final Review files exist; the health
check (option C) shows `(none yet)` for whatever is still missing.

Your READMEs are never overwritten, so any notes you add to them are safe.

> **Already set up?** If the tool folder itself already contains a `Data Sheets`
> folder with workbooks in it, the tool keeps using those and does **not** create
> anything on your Desktop. Existing installations carry on unchanged.

## Before you run anything: close Excel

If a workbook is open in Excel, this tool cannot save to it. The menu checks for
this and will tell you which file to close. Just close it and try again.

## The menu

| Option | What it does |
|---|---|
| **1. Run classification** | Reads the funding-request workbook and fills in the ethnic, gender and sexual-identity columns. Takes a few minutes. |
| **2. Build review workbook** | Creates `Data Sheets/Classification Review.xlsx` — the file you type your corrections into. Changes no gold file. |
| **3. Apply my review corrections** | Copies your corrections from that review workbook into the Final Review files. Shows you everything it will change first, and asks before writing. |
| **4. Build stakeholder dashboard** | Produces the dashboard `.html` file in `Data Sheets`. Open it in a browser. |
| **D. Switch dataset** | Cycles through the datasets found in `Data Sheets`. The header always shows which one you're on. |
| **C. Check everything is set up** | Confirms the required files are present and nothing is open in Excel. Run this first if something seems wrong. |

## The normal working order

1. **Option 1** — run the classification.
2. **Option 2** — build the review workbook.
3. Open `Data Sheets/Classification Review.xlsx` and type your corrections
   directly into the classification columns. Save and close it.
4. **Option 3** — apply those corrections. Read the list it shows you, then type
   `YES` to write them.
5. **Option 4** — build the dashboard, if you need it.

## If something goes wrong

The window tells you what happened in plain language. The two common causes are:

- **A file is open in Excel.** Close it, try again.
- **A file was renamed or moved.** The tool prints exactly which file it expected
  and where. Put it back, or pass the message to whoever maintains the tool.

Nothing is written unless a step succeeds completely, and option 3 always shows
you the full list of changes before it writes anything. If you're unsure, press
Enter to cancel — cancelling never changes a file.

If you see a message ending in "Send this message to whoever maintains the
tool", take a photo or screenshot of the window. That message contains what's
needed to diagnose it.

---

## For whoever maintains this (technical)

Day-to-day use is `RUN.bat` → `Tools/launcher.py`. The launcher shells out to the
existing entry points and sets `ECF_DATASET`; it adds no classification logic of
its own, so the engines remain independently runnable:

```
python Engine_1_and_2/run_all.py
python Engine_1_and_2/Auditing/generate_review_report.py
python Engine_1_and_2/Auditing/apply_review_corrections.py [--apply]
python Engine_1_and_2/Auditing/generate_stakeholder_dashboard.py
```

A Docker path exists for reproducible or server-side runs:

```
docker compose build
docker compose run --rm ecf help
docker compose run --rm ecf classify
docker compose run --rm -e ECF_DATASET=2023_24 ecf dashboard
```

The image carries code and dependencies only. `Data Sheets/`, `Taxonomy/` and
`Final Review/` are bind-mounted, so the container works on the same files you
see in Explorer and nothing confidential is baked into an image layer. Only
`requirements.txt` is installed — the ML extras in `requirements-ml.txt` are
excluded on purpose (~650 MB of packages plus ~1.1 GB of weights).

Note that Excel's file locks apply to the container too: close the workbooks
before any command that writes.
