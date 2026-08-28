"""
safe_save.py
------------
Saving a workbook without risking the one it replaces.

openpyxl's wb.save(path) empties the target file and then streams the new
workbook into it. If anything interrupts that -- the window is closed, the
machine sleeps, the process is killed -- the original is already gone and what
is left on disk is a truncated, unopenable file. The engines write back into
the SAME workbook they read, so an interrupted save destroys the user's data
with no way back.

Everything here writes a complete file alongside the target first, then swaps
it in with os.replace(), which is atomic on the same drive. Interrupt it and
the worst case is a leftover .~name.tmp file; the real workbook is untouched,
because it was never opened for writing.
"""

import os
import tempfile
import time
from pathlib import Path


def _temp_beside(path: Path) -> Path:
    """Create an empty scratch file in the SAME folder as the target, and
    return it.

    Two things this has to get right:

    Same folder -- os.replace is only atomic within one drive, and the system
    temp directory is easily on another one.

    A SHORT name, not one derived from the target's. Windows still caps most
    paths at 260 characters, and these workbooks live under paths like
    "OneDrive - Edmonton Community Foundation/Desktop/..." that are already
    long. Naming the scratch file ".~<target name>.tmp" adds six characters and
    can push a path that just fits over the limit -- the save then fails with a
    confusing "No such file or directory" on a file we are trying to CREATE.
    (Measured: a 254-character target became 260 exactly, and broke.) A short
    fixed-length name is shorter than the workbook's own, so if the real file
    fits, the scratch file fits. mkstemp also guarantees a unique name, so two
    runs at once cannot collide."""
    _sweep_orphans(path.parent)
    fd, name = tempfile.mkstemp(dir=str(path.parent), prefix=".~", suffix=".tmp")
    os.close(fd)          # openpyxl/pandas want the path, not the handle
    return Path(name)


def _sweep_orphans(folder: Path) -> None:
    """Delete scratch files abandoned by an earlier run.

    A process killed outright (Task Manager, power loss) never gets to clean up
    after itself, so its .~*.tmp is left behind. Nothing reads them and dataset
    discovery ignores them -- they only look like clutter in a folder staff are
    told to keep tidy. One hour old is the cut-off, comfortably longer than any
    save takes, so a save running RIGHT NOW in another window is never touched.
    """
    cutoff = time.time() - 3600
    try:
        for old in folder.glob(".~*.tmp"):
            try:
                if old.stat().st_mtime < cutoff:
                    old.unlink()
            except OSError:
                pass          # in use, or gone already -- either way, leave it
    except OSError:
        pass                  # unreadable folder is the caller's problem, not ours


def _swap_into_place(tmp: Path, path: Path) -> None:
    try:
        os.replace(tmp, path)
    except PermissionError:
        # Almost always Excel holding the file open. Say so, rather than
        # letting a bare PermissionError reach the user.
        tmp.unlink(missing_ok=True)
        raise PermissionError(
            f"Could not update '{path.name}' because it is open in Excel.\n"
            f"Close it and run this again. Nothing was changed."
        ) from None


def save_workbook(wb, path) -> Path:
    """Save an openpyxl workbook so an interrupted write cannot destroy the
    file being replaced. Returns the path written."""
    path = Path(path)
    tmp = _temp_beside(path)
    try:
        wb.save(tmp)
        _swap_into_place(tmp, path)
    except BaseException:
        # BaseException, not Exception: a Ctrl-C mid-save must still clean up
        # after itself rather than leaving .~something.tmp behind.
        tmp.unlink(missing_ok=True)
        raise
    return path


def save_via(path, write):
    """Same protection for anything that writes by being handed a path --
    pandas' ExcelWriter, for instance. `write` is called with the temp path
    and must produce the complete file there."""
    path = Path(path)
    tmp = _temp_beside(path)
    try:
        write(tmp)
        _swap_into_place(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return path
