# PyInstaller spec -- the single source of truth for the packaged .exe.
# Built by build-exe.bat via: .venv\Scripts\python.exe -m PyInstaller --noconfirm "Maintainer\ECF Classification.spec"
# Run with the REPO ROOT as the working directory (build-exe.bat cds there
# first), so engine_sources()'s Path("Engine_1_and_2") below is unchanged.
# PyInstaller re-resolves every relative path in the spec (entry script,
# datas, ...) against the SPEC FILE'S OWN folder (its built-in SPECPATH
# global) when it builds the bundle -- NOT the process cwd, no matter what
# directory the "PyInstaller ..." command was actually run from. Since this
# spec now lives in Maintainer/ alongside Tools/, the entry path below stays
# "Tools\\launcher.py" unchanged (don't prefix it with "Maintainer\\" or
# PyInstaller doubles it). But Engine_1_and_2/ is one level UP from here, so
# engine_sources() below builds an absolute path from SPECPATH instead of a
# plain Path("Engine_1_and_2") -- a bare relative string there would get the
# same "Maintainer\\" prefix wrongly re-added and fail to find anything.
#
# --onefile equivalent (single output exe), entry point Tools/launcher.py.
# Engine_1_and_2 is bundled as data (not compiled in) because launcher.py's
# frozen path runs those scripts at runtime via runpy from the extracted
# bundle (sys._MEIPASS) -- see Tools/launcher.py's --run-script handling.
# Because those scripts are loaded at runtime rather than imported statically,
# PyInstaller cannot discover their imports on its own; the hidden imports
# below cover what the classification path actually needs (pandas, numpy,
# openpyxl). The ML layer (torch, sentence_transformers, faiss, etc.) was
# removed from the pipeline and is excluded so the exe doesn't try to pull in
# ~1 GB of dependencies that are no longer used.
#
# If a built exe fails at runtime with "No module named X", add X to
# hiddenimports below and rebuild -- do not silently swallow the error
# elsewhere.

import sys
from pathlib import Path

block_cipher = None


def engine_sources():
    """Every engine .py file, and nothing else.

    Bundling the Engine_1_and_2 FOLDER wholesale would sweep in
    Semantic_Engine/models/ -- 1.1 GB of ML model weights belonging to the
    layer that was removed from the pipeline -- and produce an 810 MB exe
    nobody can email. Only the source files are needed: launcher.py runs them
    at runtime with runpy. Caches and the maintainer's regression baseline are
    not part of the classification path either.
    """
    skip = {"__pycache__", "models", ".pytest_cache", ".semantic_cache", ".ml_cache"}
    engine_root = Path(SPECPATH).parent / "Engine_1_and_2"
    out = []
    for src in engine_root.rglob("*.py"):
        if skip.intersection(src.parts):
            continue
        # dest dir, relative to the bundle root -- keep it "Engine_1_and_2/...",
        # not the absolute host path, or the frozen layout would leak this
        # machine's folder structure into the exe.
        rel_parent = src.parent.relative_to(Path(SPECPATH).parent)
        out.append((str(src), str(rel_parent)))
    return out

a = Analysis(
    ["Tools\\launcher.py"],
    pathex=[],
    binaries=[],
    datas=engine_sources(),
    hiddenimports=["pandas", "numpy", "openpyxl"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "torch",
        "sentence_transformers",
        "faiss",
        "huggingface_hub",
        "sklearn",
        "scipy",
        "matplotlib",
        "pytest",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="ECF Classification",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
