"""
docker_entrypoint.py
--------------------
Maps short, memorable commands onto the project's entry points so the Docker
usage reads as `docker compose run --rm ecf classify` rather than a long
python path. Used only by the container; RUN.bat does not go through this.

Run with no command at all and this behaves like RUN.bat: if there is an
interactive terminal attached (someone ran `docker run -it ...`, which is what
"RUN (Docker).bat" / run-docker.sh do), it hands off to the same numbered menu
non-technical staff already know. With no terminal attached, it prints the
usage below instead of hanging on an input() nobody can answer.
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "Engine_1_and_2" / "Auditing"

COMMANDS = {
    "classify":  (ROOT / "Engine_1_and_2" / "run_all.py",   [],
                  "Run the full classification pass over ECF_DATASET"),
    "review":    (AUDIT / "generate_review_report.py",      [],
                  "Build Data Sheets/Classification Review.xlsx"),
    "preview":   (AUDIT / "apply_review_corrections.py",    [],
                  "Show which corrections would be applied (writes nothing)"),
    "apply":     (AUDIT / "apply_review_corrections.py",    ["--apply"],
                  "Write the corrections into the Final Review files"),
    "dashboard": (AUDIT / "generate_stakeholder_dashboard.py", [],
                  "Build the stakeholder dashboard for ECF_DATASET"),
}


def usage(code=0):
    ds = os.environ.get("ECF_DATASET", "2025")
    print(__doc__.strip())
    print(f"\nCurrent dataset (ECF_DATASET): {ds}\n")
    print("Commands:")
    for name, (_, _, desc) in COMMANDS.items():
        print(f"  {name:<11} {desc}")
    print("\nExamples:")
    print("  RUN (Docker).bat                 (Windows -- the numbered menu)")
    print("  bash run-docker.sh                (macOS/Linux -- the same menu)")
    print('  docker run -it --rm -v "<workspace>:/data" ecf-discretionary-fr classify')
    print('  docker run -it --rm -v "<workspace>:/data" -e ECF_DATASET=2023_24 '
          "ecf-discretionary-fr dashboard")
    return code


def main(argv):
    if not argv:
        # No command at all: if a real user is attached, give them the same
        # menu RUN.bat gives. If not (e.g. a script piped this without -it),
        # fall through to the help text instead of blocking on input() forever.
        if sys.stdin.isatty():
            launcher = Path(__file__).resolve().parent / "launcher.py"
            return subprocess.run([sys.executable, str(launcher)],
                                  cwd=str(ROOT)).returncode
        return usage()
    if argv[0] in ("help", "-h", "--help"):
        return usage()
    cmd = argv[0]
    if cmd not in COMMANDS:
        print(f"Unknown command: {cmd!r}\n")
        return usage(2)
    script, args, _ = COMMANDS[cmd]
    if not script.exists():
        print(f"ERROR: {script} is missing from the image.")
        return 1
    return subprocess.run([sys.executable, str(script), *args, *argv[1:]],
                          cwd=str(ROOT)).returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
