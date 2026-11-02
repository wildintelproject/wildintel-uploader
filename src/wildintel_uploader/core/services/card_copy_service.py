"""Copying a camera's memory card to a temporary folder of this computer.

The images of a deployment can be on the card itself: it is copied — never changed, it is only read — to a temporary folder, and what is done after is done to
that folder as to any other local one. The copy is named like the card, so the folder name says what the card was; it is removed when the import is over
(`discard`), and the ones that were left behind by an import that never finished are removed the next time a card is copied (`clean_stale`)."""

from __future__ import annotations

import logging
import shutil
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path

logger = logging.getLogger(__name__)

# The folder the copies are made in: inside the temporary folder of the system, so that nothing else is ever removed.
BASE_NAME = "wildintel-sd"
# A copy that was not removed after this long is a leftover.
STALE_SECONDS = 24 * 3600


class CardCopyError(Exception):
    """The card could not be copied."""


def base_dir() -> Path:
    return Path(tempfile.gettempdir()) / BASE_NAME


def _files(source: Path) -> list[Path]:
    return sorted(p for p in source.rglob("*") if p.is_file())


def clean_stale(now: float | None = None) -> int:
    """Removes the copies left behind longer than STALE_SECONDS ago; returns how many."""
    base = base_dir()
    if not base.is_dir():
        return 0
    limit = (now if now is not None else time.time()) - STALE_SECONDS
    removed = 0
    for entry in base.iterdir():
        try:
            if entry.is_dir() and entry.stat().st_mtime < limit:
                shutil.rmtree(entry)
                removed += 1
        except OSError as exc:
            logger.warning("Could not remove the old copy of a card %s: %s", entry, exc)
    return removed


def copy_card(source_dir: str) -> Iterator[dict]:
    """Copies the files of the card at `source_dir` to a new temporary folder, named like the card. Events: {"type": "start", "files", "bytes"},
    {"type": "progress", "copied", "files", "bytes_copied", "bytes"} after each file and {"type": "done", "path", "files", "bytes"} — `path` is the copy.

    Raises:
        CardCopyError: the card is not a folder that can be read, or has nothing on it, or a file could not be copied (what was copied is removed)."""
    source = Path(source_dir).expanduser()
    if not source.is_dir():
        raise CardCopyError(f"The memory card '{source_dir}' is not a folder that can be read.")
    try:
        files = _files(source)
    except OSError as exc:
        raise CardCopyError(f"The memory card '{source_dir}' cannot be read: {exc}") from exc
    if not files:
        raise CardCopyError(f"There is nothing on the memory card '{source_dir}'.")
    clean_stale()
    base_dir().mkdir(parents=True, exist_ok=True)
    holder = Path(tempfile.mkdtemp(prefix="card-", dir=base_dir()))
    # named like the card: its folder name, or its label
    destination = holder / (source.name or "card")
    sizes = [f.stat().st_size for f in files]
    total = sum(sizes)
    yield {"type": "start", "files": len(files), "bytes": total}
    copied_bytes = 0
    try:
        for n, (file, size) in enumerate(zip(files, sizes), start=1):
            target = destination / file.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, target)
            copied_bytes += size
            yield {"type": "progress", "copied": n, "files": len(files), "bytes_copied": copied_bytes, "bytes": total}
    except OSError as exc:
        shutil.rmtree(holder, ignore_errors=True)
        raise CardCopyError(f"The memory card could not be copied: {exc}") from exc
    yield {"type": "done", "path": str(destination), "files": len(files), "bytes": total}


def discard(path: str) -> bool:
    """Removes a copy made by copy_card — only one inside its own folder, whatever the path says. Returns whether something was removed."""
    base = base_dir().resolve()
    target = Path(path).expanduser().resolve()
    if base not in target.parents:
        return False
    holder = target
    while holder.parent != base:
        holder = holder.parent
    if not holder.is_dir():
        return False
    shutil.rmtree(holder, ignore_errors=True)
    return True
