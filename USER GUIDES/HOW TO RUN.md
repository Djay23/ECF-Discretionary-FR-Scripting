# How to run this tool

You do not need to know anything about code to use this.

## Starting it

**Double-click `ECF Classification.exe`.** That's it — nothing to install, no
Python, no Docker, no admin rights needed. A window opens with the numbered
menu described below. Type a number, press Enter.

> **Windows may warn you first.** Because this is a new, unsigned program,
> Windows SmartScreen can show a blue box saying "Windows protected your PC".
> This is expected for a small in-house tool — it isn't a sign anything is
> wrong. Click **"More info"**, then **"Run anyway"**. You only need to do
> this once per computer.

That's the whole setup. Everything below — where the files go, the menu, the
working order — applies exactly the same whether you're running the `.exe` or
one of the alternatives further down.

## Where the files go — the tool creates these for you

**The first time you run it, it creates a folder called `ECF Classification`
on your Desktop**, containing the four folders it needs and a
`START HERE.txt`:

```
Desktop/ECF Classification/
    START HERE.txt
    Data Sheets/     README.txt
    Taxonomy/        README.txt
    Gold/            README.txt
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
| **Taxonomy** | `Taxonomy - Definitions.xlsx`. Just that one file. |
| **Gold** | Hand-audited snapshots of past years, if you have any. Optional. |
| **Final Review** | The audited copies your corrections get written into. |

The tool tells you where these folders are when it makes them, and option **C**
on the menu shows you the location again at any time.

**Name each new workbook with its year:**

```
Discretionary Funding Requests - 2026.xlsx
```

That's the only rule. The tool reads the year from the filename, calls that
dataset `2026`, and automatically pairs it with anything else carrying 2026 —
its GOLD file in `Gold`, its copy in `Final Review`. Next year, drop in
`... - 2027.xlsx` and it appears in the menu on its own.

A dataset works fine before its GOLD and Final Review files exist — you do not
need to create either by hand. The health check (option C) shows `(none yet)`
for whatever is still missing.

Your READMEs are never overwritten, so any notes you add to them are safe.

> **Already set up?** If the tool folder itself already contains a `Data Sheets`
> folder with workbooks in it, the tool keeps using those and does **not** create
> anything on your Desktop. Existing installations carry on unchanged.

## What you provide, and what the tool creates

Only **two** files are ever created that you didn't supply. Everything else is
written *into* workbooks you provided — which is why the tool asks you to close
Excel first.

**You provide:**

| File | Goes in | Needed |
|---|---|---|
| `Discretionary Funding Requests - 2026.xlsx` | `Data Sheets/` | Always — this is the workbook being classified |
| `Taxonomy - Definitions.xlsx` | `Taxonomy/` | Always — nothing runs without it |
| `FR - 2026 (GOLD-AUDIT).xlsx` | `Gold/` | Optional. Only if you already have a hand-audited snapshot of that year |

**The tool creates:**

| File | Made by | Where |
|---|---|---|
| `Classification Review.xlsx` | Option 2 | `Data Sheets/` |
| `...2026... (GOLD) Final review.xlsx` | Option 3, the first time | `Final Review/` |
| `stakeholder_dashboard_2026.html` | Option 4 | `Data Sheets/` |

### The stages, in order

1. **Put your workbook in `Data Sheets/`** with the year in its name, and make
   sure `Taxonomy - Definitions.xlsx` is in `Taxonomy/`.
2. **Option 1 — Run classification.** Fills the ethnic, gender and sexual
   columns **into your workbook**. Nothing new appears.
3. **Option 2 — Build review workbook.** Creates
   `Data Sheets/Classification Review.xlsx`, containing the rows the engine
   flagged. Built from that year's GOLD file if you have one; otherwise from the
   workbook you just classified.
4. **You review.** Open `Classification Review.xlsx`, type your corrections into
   the classification columns, save and close it.
5. **Option 3 — Apply my review corrections.** Shows every cell it would change
   and waits for you to type `YES`. It writes into that year's file in
   `Final Review/`, **creating it for you** the first time. Your original
   workbook is left exactly as the engine wrote it.
6. **Option 4 — Build stakeholder dashboard.** Reads the `Final Review/` copy,
   so the dashboard reflects your corrections.

Steps 2 to 6 can be repeated as often as you like. Re-running step 1 is always
safe: it only ever touches the workbook in `Data Sheets/`, never your
corrections in `Final Review/`.

## Before you run anything: close Excel

If a workbook is open in Excel, this tool cannot save to it. This applies no
matter how you're running the tool. The menu checks for this and will tell
you which file to close. Just close it and try again.

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

## Letting an AI assistant run it for you

Everything above works fine with just the `.exe` and a mouse — this section
is for people who'd rather type what they want in plain language than click
through the menu. It's an **alternative**, not a requirement.

### What you need first

1. **Get this whole folder onto your computer** — the same one you'd use to
   run `ECF Classification.exe`. Nothing in it needs to change.
2. **Install Claude Code**: <https://claude.com/claude-code>. Claude Code is
   a separate paid tool from Anthropic, run from a terminal (or from inside
   VS Code) — it is not part of this project and isn't required to use the
   `.exe`. Follow Anthropic's install instructions for your computer.

### How to start it

Open a terminal (or VS Code's terminal panel) **in this folder** and run:

```
claude
```

That drops you into a conversation. From there, describe what you want, or
paste one of the prompts below.

### Ready-to-paste prompts

Copy one of these into the terminal exactly as written.

**Run the classification:**
```
Run the classification on my data. First read HOW TO RUN.md and
Documentation/AI-HANDOFF.md so you understand the tool. Confirm with me
which dataset to use, make sure I've closed the workbook in Excel, then run
the classification step (menu option 1 / Engine_1_and_2/run_all.py) and
show me the summary counts afterwards. Don't change any code.
```

**Take me through the whole review cycle:**
```
Take me through the whole review cycle: run classification, build the
review workbook, tell me where to make my corrections, then apply them and
build the dashboard. Stop and explain each stage before moving to the next.
Don't change any code.
```

**Build the dashboard:**
```
Build or refresh the stakeholder dashboard for my current dataset. Tell me
where the HTML file ends up. Don't change any code.
```

**Explain a specific request:**
```
Explain what the engine did with a specific funding request — [describe or
paste the row]. Walk me through which text triggered which rule, and
whether it was flagged for review. Don't change any code.
```

**Write or refresh the user guide:**
```
Write or refresh the user guide for this tool, using
Documentation/AI-HANDOFF.md as the spec for what it must cover. Don't
change any code.
```

### A safety note

An AI assistant can read and write files just like you can, so the same
rules from earlier in this document still apply: **close Excel first**, and
remember that applying your review corrections (option 3) writes into the
`Final Review/` copies — read what the assistant proposes to change before
you approve it, the same way you'd read option 3's own confirmation list.

## If something goes wrong

The window tells you what happened in plain language.

| Symptom | What it means | What to do |
|---|---|---|
| Blue "Windows protected your PC" screen | SmartScreen warning about a new, unsigned program. Expected. | Click "More info", then "Run anyway". Only needed once per computer. |
| A file is open in Excel | The tool cannot write to a file Excel has locked. | Close it, try again. |
| "NO DATA FOUND" | No workbook in `Data Sheets`, or it isn't named with a year. | Put one there, named e.g. `Discretionary Funding Requests - 2026.xlsx`. |
| A file was renamed or moved | The tool expected an exact file it can't find. | Put it back, or pass the message to whoever maintains the tool. |
| Antivirus quarantined or deleted the `.exe` | Some antivirus tools are suspicious of new, unsigned, single-file programs. | Restore it from quarantine and add an exception, or ask IT to allow it. Re-download/re-copy the file if it was deleted outright. |

Nothing is written unless a step succeeds completely, and option 3 always shows
you the full list of changes before it writes anything. If you're unsure, press
Enter to cancel — cancelling never changes a file.

If you see a message ending in "Send this message to whoever maintains the
tool", take a photo or screenshot of the window. That message contains what's
needed to diagnose it.

---

## For whoever maintains this (technical)

Everything in this section lives in the **`Maintainer/`** folder — it holds
the build and container tooling, not anything a non-technical user opens.

Day-to-day use for non-technical staff is **`ECF Classification.exe`** (at
the top level of the folder, beside `Data Sheets/` etc.), built by
`Maintainer\build-exe.bat` (PyInstaller, spec file
`Maintainer\ECF Classification.spec`) straight from
`Maintainer\Tools\launcher.py`. It's a single onefile executable with
`Engine_1_and_2/` bundled in as data; PyInstaller extracts it to a temp dir
(`sys._MEIPASS`) at startup. Frozen, `sys.executable` is the `.exe` itself, so
`launcher.run()` re-invokes it with an internal `--run-script <path>` flag
(handled in `main()` via `runpy.run_path`) instead of trying to shell out to a
Python interpreter that doesn't exist standalone — each engine step still runs
as its own subprocess, exactly as it does unfrozen. `Engine_1_and_2/paths.py`
has a matching frozen-mode adjustment: the "does an install already have data
sitting next to it" check looks at the folder the `.exe` lives in
(`paths.tool_dir()`), not the temp extraction dir.

To rebuild after a code change: run `Maintainer\build-exe.bat` (needs `.venv`
already set up — run `Maintainer\RUN.bat` once first if not). It builds from
the repo root (the .bat `cd`s there first, since `.venv` and `Engine_1_and_2`
live there) and, on success, copies the result from `dist\ECF Classification.exe`
to `ECF Classification.exe` at the top level of the folder — overwriting any
previous copy — ready to hand to staff or drop straight into SharePoint. If a
rebuilt exe fails at runtime with "No module named X", add X to
`hiddenimports` in `Maintainer\ECF Classification.spec` and rebuild — the
engine scripts are loaded at runtime via `runpy`, so PyInstaller can't see
their imports statically. The ML layer (`torch`, `sentence_transformers`,
`faiss`, etc.) is deliberately excluded — it was removed from the pipeline
and is ~1 GB of packages the classification path never uses.

Two other ways to run this remain, for the maintainer:

**Docker** — for reproducible or server-side runs. `Maintainer\RUN (Docker).bat` /
`Maintainer/run-docker.sh` → `docker run -it --rm -v "<workspace>:/data"
ecf-discretionary-fr:latest`, which drops straight into
`Maintainer\Tools\launcher.py` (the same menu the `.exe` gives). Both scripts
`cd` to the repo root first, so the build context is still the whole project.
The image separates code from data: code lives at `/app` (`Engine_1_and_2/`
and `Tools/`, baked in at build time from `Maintainer/Tools/`), and the
workspace — `Data Sheets/`, `Taxonomy/` and `Final Review/` — is
bind-mounted at `/data` at run time, with `ECF_WORKSPACE=/data` set so
`paths.py` resolves straight to the mount. Only `requirements.txt` is
installed — the ML extras in `requirements-ml.txt` are excluded on purpose.

**`RUN.bat`** — for a maintainer's machine that already has Python. Identical
menu, no packaging step; the very first run installs the project's own
`.venv`. If it says Python is not installed, install it from python.org and
tick "Add python.exe to PATH" on the installer's first screen.

None of these three paths add classification logic of their own — they all
shell out to the same entry points and set `ECF_DATASET`, so the engines
remain independently runnable:

```
python Engine_1_and_2/run_all.py
python Engine_1_and_2/Auditing/generate_review_report.py
python Engine_1_and_2/Auditing/apply_review_corrections.py [--apply]
python Engine_1_and_2/Auditing/generate_stakeholder_dashboard.py
```

Verb-driven, non-interactive runs still work for scripting or CI, via either
`docker run` or `docker compose` (run from the repo root, or adjust the `-f`
path accordingly):

```
docker build -t ecf-discretionary-fr -f Maintainer/Dockerfile .
docker compose -f Maintainer/docker-compose.yml build
docker compose -f Maintainer/docker-compose.yml run --rm ecf help
docker compose -f Maintainer/docker-compose.yml run --rm ecf classify
docker compose -f Maintainer/docker-compose.yml run --rm ecf preview
docker compose -f Maintainer/docker-compose.yml run --rm -e ECF_DATASET=2023_24 ecf dashboard
```

`docker compose` builds with the repo root as context (`context: ..` in
`Maintainer/docker-compose.yml`, since the file itself lives one level down)
and mounts `${ECF_WORKSPACE_HOST:-..}` (the repo root, by default) at `/data`
— set `ECF_WORKSPACE_HOST` to point it at a different workspace.
`Tools/docker_entrypoint.py` runs with no arguments in two ways: with an
interactive terminal attached (`docker run -it`, which the host launchers
use) it hands off to the menu; without one, it prints the help text instead
of hanging on an `input()` nobody can answer.

Note that Excel's file locks apply to the container too: close the workbooks
before any command that writes.

### If the `.exe` ever stops being allowed

Distributing this as an `.exe` through SharePoint depends on a Microsoft 365
tenant policy that can change — most often when IT tightens the rules on
unsigned executables. Nothing about the tool depends on that policy: the `.exe`
is a convenience for staff, not the product. Everything needed to run or
rebuild it ships in this folder.

If staff suddenly cannot download or run `ECF Classification.exe`:

| Fallback | What it costs |
|---|---|
| **Get it code-signed** by IT and carry on as before | The most durable fix — blocking policies almost always target *unsigned* executables, and signing also removes the SmartScreen warning for good. Ask whether IT already holds a signing certificate; many do. |
| **Put the `.exe` on a network share** instead of SharePoint | Nothing changes for staff except where they get the file. Files run from an internal share usually aren't web-marked either, so the SmartScreen warning goes away too. |
| **Zip it** and upload that | Often permitted where a bare `.exe` isn't. Staff right-click → "Extract All" before double-clicking. |
| **Skip the `.exe` entirely** — `Maintainer\RUN.bat` | Identical menu, but each machine needs Python installed. Fine for one or two people, poor for a whole team. |

Rebuilding the `.exe` at any time is `Maintainer\build-exe.bat` on a machine
with the project's `.venv` set up. That is the only step that needs a
technical person, and it takes about two minutes.
