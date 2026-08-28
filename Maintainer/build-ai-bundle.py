r"""
build-ai-bundle.py
------------------
Rebuild Documentation/AI-HANDOFF-BUNDLE.md -- the single file you upload to an
AI that CANNOT see your files (ChatGPT, Claude on the web, and so on) when you
want it to write documentation or explain how this tool works.

Claude Code, running in this folder, does not need the bundle: it can open the
real files, so point it at Documentation/AI-HANDOFF.md instead.

Run it from anywhere:
    .venv\Scripts\python.exe Maintainer\build-ai-bundle.py

Regenerate the bundle whenever the source documents change, otherwise you will
be handing someone a stale copy of your own instructions.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "Documentation" / "AI-HANDOFF-BUNDLE.md"

# Order matters: the brief first, so an AI reads the instructions before the
# material they apply to.
PARTS = [
    ("Documentation/AI-HANDOFF.md",
     "The brief. What this project is, how it runs, and the rules an AI must not break."),
    ("USER GUIDES/HOW TO RUN.md",
     "The current end-user instructions. The guide you are asked to write replaces "
     "or extends this, so read it before writing anything."),
    ("README.md",
     "Developer documentation: the classification method, the module map (what every "
     "file does), and the execution guide."),
    ("Documentation/PROCESS.md",
     "Reference only. The classification rules case by case, with examples. Use it to "
     "understand behaviour -- do NOT restate it in a user guide."),
    ("Engine_1_and_2/paths.py",
     "Source code, included because it defines the folder and filename convention "
     "everything else depends on."),
]

HEADER = """# ECF Classification — AI handoff bundle

This one file contains everything an AI needs to understand this tool and write
documentation for it. It is a GENERATED copy of the project's real documents,
bundled for an assistant that cannot open files on your computer.

**How to use it:** upload this file and paste the prompt below.

---

## The prompt

> Read this whole document first. It contains the brief, the current user
> instructions, the developer documentation, and the file-discovery source code
> for an internal tool called ECF Classification.
>
> Write a user guide for it, following the brief in section 1 ("Brief for
> building a user guide"). The audience is non-technical foundation staff who
> need to run the tool, plus one technical maintainer who looks after it.
>
> Cover: the three ways to run it, the four working folders, which files the
> user supplies and which the tool creates, the six stages in order, the menu,
> and troubleshooting. Explain in plain language what the engine actually does.
>
> Do not restate the case-by-case classification rules in full — summarise them.
> Do not invent features, file names, screenshots, or menu options that are not
> in this document. If something is unclear, list your questions at the end
> rather than guessing.

---

## What is in this bundle

| Section | Source file | Why it is here |
|---|---|---|
"""


def main():
    rows, bodies = [], []
    for rel, why in PARTS:
        src = ROOT / rel
        if not src.exists():
            raise SystemExit(f"Missing source document: {src}\n"
                             f"Fix the PARTS list in {Path(__file__).name}.")
        rows.append(f"| {len(rows) + 1} | `{rel}` | {why} |")
        fence = "```python" if src.suffix == ".py" else ""
        text = src.read_text(encoding="utf-8")
        body = f"\n\n---\n\n# {len(bodies) + 1}. {rel}\n\n"
        body += f"{fence}\n{text}\n```\n" if fence else text
        bodies.append(body)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(HEADER + "\n".join(rows) + "\n" + "".join(bodies), encoding="utf-8")
    kb = OUT.stat().st_size / 1024
    print(f"Wrote {OUT.relative_to(ROOT)}  ({kb:,.0f} KB, {len(PARTS)} documents)")
    print("Upload that one file to an AI, along with the prompt at the top of it.")


if __name__ == "__main__":
    main()
