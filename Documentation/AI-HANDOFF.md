# AI Handoff — Context Pack for an AI Assistant

This file exists so an owner can hand this codebase to an AI assistant (Claude
Code or otherwise) and have it run the engine correctly and write user
documentation, without re-discovering the project from scratch or breaking
anything. Read this file first, then read the files it points at — don't
guess at behaviour this project already documents.

---

## 1. What this project is

This is a deterministic classification pipeline for Edmonton Community
Foundation's discretionary funding-request (FR) data. It reads free-text
fields from a funding-request workbook — project descriptions, purpose,
organization name — and classifies each row along three axes: **ethnic and
cultural origins**, **gender identity**, and **sexual identity**, against a
standardized taxonomy. There is no machine-learning model in the decision
path: every label comes from a rule-based state machine, so the same input
always produces the same output and every decision can be traced to a rule.
A human-review workflow sits on top of the engine so staff can audit and
correct its output before it's treated as final.

---

## 2. Where the truth already lives

Read these before asking questions the docs already answer:

| Source | What it covers |
| :--- | :--- |
| `README.md` sections 1–6 | The classification method: architecture, the three-layer pipeline, the case-by-case logic (Cases 1–13), audit-flag rules, the gender/sexual-identity engines, and why the ML layer is hibernated. |
| `README.md` section 7 | Full module map — every file's purpose — plus the file-discovery convention and how to extend a rule. |
| `README.md` section 8 | Technical execution guide: exact commands, what each script does, which columns get written. |
| `USER GUIDES/HOW TO RUN.md` | End-user instructions (the three ways to run it, the four folders, the menu, the stages, troubleshooting) and a maintainer section at the bottom (build/Docker/rebuild details). |
| `Documentation/PROCESS.md` | Informal, evolving case-by-case classification notes and examples — the working notes behind the rules in `README.md` section 3. Treat `README.md` as the authoritative current description; `PROCESS.md` is background/history. |
| `Engine_1_and_2/paths.py` | The file-discovery convention, in code, with a docstring explaining *why*: filenames are not code, and renaming a workbook must never require a code edit. Read this before touching anything path-related. |

Do not re-derive the classification rules, the module layout, or the
file-discovery convention from scratch — they are documented and read faster
than they can be reverse-engineered.

---

## 3. How to run it

There are three ways to reach the same numbered menu
(`Maintainer/Tools/launcher.py`):

| Path | Command | Needs |
| :--- | :--- | :--- |
| Built executable | Double-click `ECF Classification.exe` at the repo root | Nothing — no Python, no Docker |
| Local Python | `Maintainer\RUN.bat` | System Python (builds a `.venv` on first run) |
| Docker | `Maintainer\RUN (Docker).bat` or `Maintainer/run-docker.sh` | Docker Desktop running |

Menu options and the scripts behind them:

| Option | Script |
| :--- | :--- |
| 1. Run classification | `Engine_1_and_2/run_all.py` |
| 2. Build review workbook | `Engine_1_and_2/Auditing/generate_review_report.py` |
| 3. Apply my review corrections | `Engine_1_and_2/Auditing/apply_review_corrections.py` (dry run by default; `--apply` writes) |
| 4. Build stakeholder dashboard | `Engine_1_and_2/Auditing/generate_stakeholder_dashboard.py` |
| D | Switch dataset |
| C | Health check (shows what's found/missing) |
| 0 | Exit |

Every engine script can also be run directly and takes no arguments — it
reads/writes the paths `paths.discover()` resolves for the active dataset
(set via the `ECF_DATASET` environment variable, or the first dataset found
alphabetically):

```powershell
python Engine_1_and_2/run_all.py
$env:ECF_DATASET="2023_24"; python Engine_1_and_2/run_all.py
```

For Docker specifically, see the verb-driven non-interactive form in
`HOW TO RUN.md`'s maintainer section (`docker compose run --rm ecf classify`,
etc.) — useful for scripting rather than the interactive menu.

---

## 4. The data model

Four working folders at the repo root, described in full in `HOW TO RUN.md`
("Where the files go" and "What you provide, and what the tool creates"):

| Folder | Contents | Who puts files there |
| :--- | :--- | :--- |
| `Data Sheets/` | Funding-request workbooks to classify, one per year, named `Discretionary Funding Requests - {year}.xlsx` | User supplies |
| `Taxonomy/` | `Taxonomy - Definitions.xlsx` — exactly one file | User supplies |
| `Gold/` | Hand-audited snapshots of past years — optional | User supplies (optional) |
| `Final Review/` | Audited copies corrections get written into | Tool creates on first use of option 3 |

The tool also creates `Data Sheets/Classification Review.xlsx` (option 2) and
`stakeholder_dashboard*.html` (option 4). Nothing else is generated.

The six stages, in order:

1. Put a workbook in `Data Sheets/` (year in the filename) and the taxonomy
   file in `Taxonomy/`.
2. **Option 1 — classify.** Writes ethnic/gender/sexual columns directly into
   the source workbook.
3. **Option 2 — build review workbook.** Creates
   `Data Sheets/Classification Review.xlsx` containing the flagged rows.
4. **Human review.** Staff open that file, type corrections into the
   classification columns, save and close it.
5. **Option 3 — apply corrections.** Shows every cell it will change, waits
   for a typed `YES`, then writes into the year's file in `Final Review/`
   (creating it the first time).
6. **Option 4 — dashboard.** Reads the `Final Review/` copy, so it reflects
   the human corrections.

Dataset matching is by year parsed from the filename — see
`Engine_1_and_2/paths.py` (`dataset_name_from`, `discover`).

---

## 5. Invariants an AI must not break

- **Engines write in place** into the user's own workbook in `Data Sheets/`.
  Never redirect output elsewhere "to be safe" — that breaks the discovery
  convention and orphans the user's data.
- **Excel holds exclusive file locks.** A workbook open in Excel cannot be
  written by the tool (or by you). Always confirm Excel is closed before
  running option 1 or option 3, or any script that writes.
- **Option 3 is the only destructive step.** It previews every change and
  requires the user to type `YES`. Never script around that confirmation or
  auto-supply `YES` on someone's behalf.
- **Never edit files in `Data Sheets/`, `Taxonomy/`, `Gold/`, or
  `Final Review/` directly.** These are the user's data, not project source.
  Reading them to help the user is fine; editing them by hand is not — that's
  what the engine and option 3 are for.
- **Filenames are not code.** Never hardcode a path or a dataset name
  anywhere. Discovery reads the year out of the filename
  (`Engine_1_and_2/paths.py`); a new year's workbook must work with zero code
  changes.
- **Gold is optional.** Never require a `Gold/` file to exist or make it a
  precondition for running anything.
- **No autonomous git.** Do not commit or push in this repo unless the user
  explicitly asks in that moment.
- **Regression-check any engine change.** Before an engine change ships,
  re-run it against the audited gold rows with
  `Engine_1_and_2/Auditing/regression_audited_rows.py` and confirm no
  previously-correct row flips. See `regression_baseline.json` and the
  "Regression discipline" note in `README.md` section 7.
- **The ML layer is hibernated on purpose** (`Engine_1_and_2/Semantic_Engine/`
  — excluded from both the `.exe` build and the Docker image; see `README.md`
  section 6). Do not re-enable it, wire it back into the pipeline, or treat
  its presence in the tree as an invitation to "improve" results with it.

---

## 6. Brief for building a user guide

If asked to write or refresh end-user documentation, treat this section as
the spec.

**Audience:** two readers in one document — non-technical staff running the
tool day-to-day, and a technical maintainer who occasionally rebuilds or
troubleshoots it. `HOW TO RUN.md` already splits this way (staff-facing body,
"For whoever maintains this (technical)" section at the end) — match that
pattern rather than inventing a new structure.

**Must cover:**
- The three ways to run it (executable, `RUN.bat`, Docker) and when each
  applies.
- The four working folders and what belongs in each.
- The six stages, in order, and which menu option maps to which.
- The menu table (options 1–4, D, C, 0).
- Troubleshooting: a file locked by Excel, the SmartScreen warning on first
  run, "NO DATA FOUND" (no dataset in `Data Sheets/`), Docker not running.
- A plain-language explanation of what the engine does — drawn from
  `README.md` sections 2–4 (the three-layer pipeline, signal vs. decision
  separation, the audit-flag philosophy) — described for a non-technical
  reader, not reproduced verbatim.

**Do not:**
- Restate `Documentation/PROCESS.md`'s case-by-case rules in full — link to
  it or summarize in one or two sentences at most.
- Invent screenshots or UI descriptions that aren't verifiable from the code
  or existing docs.
- Change any code, `.bat`/`.sh` script, Dockerfile, or spec file while
  writing documentation. Documentation tasks are read-only with respect to
  everything except the docs themselves.

---

## 7. Ready-to-paste prompts

These are the same prompts offered to end users in `HOW TO RUN.md`'s
"Letting an AI assistant run it for you" section. Reproduced here so this
file is self-contained.

```
Run the classification on my data. First read "USER GUIDES/HOW TO RUN.md" and
Documentation/AI-HANDOFF.md so you understand the tool. Confirm with me
which dataset to use, make sure I've closed the workbook in Excel, then run
the classification step (menu option 1 / Engine_1_and_2/run_all.py) and
show me the summary counts afterwards. Don't change any code.
```

```
Take me through the whole review cycle: run classification, build the
review workbook, tell me where to make my corrections, then apply them and
build the dashboard. Stop and explain each stage before moving to the next.
Don't change any code.
```

```
Build or refresh the stakeholder dashboard for my current dataset. Tell me
where the HTML file ends up. Don't change any code.
```

```
Explain what the engine did with a specific funding request — [describe or
paste the row]. Walk me through which text triggered which rule, and
whether it was flagged for review. Don't change any code.
```

```
Write or refresh the user guide for this tool, using
Documentation/AI-HANDOFF.md as the spec for what it must cover. Don't
change any code.
```
