"""Whether there is room on a disk for what is going to be written on it — checked before a long copy starts, so that it does not fail half-way (#212):
the copy of an SD card in the temporary folder of the system, and the images prepared in the .staging folder of a collection."""
from __future__ import annotations

import shutil
from pathlib import Path


def free_bytes(path: Path) -> int | None:
    """The free space of the disk a path is on — the path itself, or the nearest of its parents that exists. None when it cannot be told."""
    for candidate in (path, *path.parents):
        if candidate.exists():
            try:
                return shutil.disk_usage(candidate).free
            except OSError:
                return None
    return None


def size_text(size: int) -> str:
    """A size as it is read: 31.2 GB, 640.0 MB, 12 KB."""
    for unit, scale in (("GB", 1e9), ("MB", 1e6), ("KB", 1e3)):
        if size >= scale:
            return f"{size / scale:.1f} {unit}" if unit != "KB" else f"{size / scale:.0f} {unit}"
    return f"{size} bytes"


def shortfall(path: Path, needed: int, what: str, where: str) -> str | None:
    """Why `needed` bytes do not fit on the disk of `path` — None when they do, or when its free space cannot be told (the copy is then tried as before).
    `what` is what needs the room ("The SD card"), `where` the folder it goes in ("the temporary folder of the system")."""
    free = free_bytes(path)
    if free is None or free >= needed:
        return None
    return (f"{what} needs {size_text(needed)} and {where} ({path}) has {size_text(free)} free: "
            f"free {size_text(needed - free)} on that disk and try again.")
