"""Copying a camera's memory card to a temporary folder of this computer — plain Python.

The images of a deployment can be on the card itself: it is copied — never changed, it is only read — to a temporary folder, and what is done after is
done to that folder as to any other local one. Each copy is made in a folder of its own (its holder) inside the folder of the copies, and is named like
the card, so the folder name says what the card was; it is removed when the import is over, and the copies left behind by an import that never finished
are removed the next time a card is copied. Only a copy inside the folder of the copies is ever removed."""
from __future__ import annotations

from pathlib import PurePath

from wildintel_uploader.modules.deployments.domain.models import DeploymentsFailed

# The folder the copies are made in: inside the temporary folder of the system, so that nothing else is ever removed.
BASE_NAME = "wildintel-sd"
# A copy that was not removed after this long is a leftover.
STALE_SECONDS = 24 * 3600
# What needs the room, and where, as the shortfall of the disk says it.
WHAT, WHERE = "The SD card", "the temporary folder of the system"


class CardCopyError(DeploymentsFailed):
    """The card could not be copied — and why."""


def not_a_folder(card: str) -> CardCopyError:
    return CardCopyError(f"The SD card '{card}' is not a folder that can be read.")


def unreadable(card: str, why: object) -> CardCopyError:
    return CardCopyError(f"The SD card '{card}' cannot be read: {why}")


def empty(card: str) -> CardCopyError:
    return CardCopyError(f"There is nothing on the SD card '{card}'.")


def not_copied(why: object) -> CardCopyError:
    return CardCopyError(f"The SD card could not be copied: {why}")


def copy_name(card: PurePath) -> str:
    """The copy is named like the card: its folder name, or its label."""
    return card.name or "card"


def stale(modified: float, now: float) -> bool:
    return modified < now - STALE_SECONDS


def holder_of(base: PurePath, copy: PurePath) -> PurePath | None:
    """The folder of the copies' own folder that holds `copy` — None when `copy` is not inside the folder of the copies."""
    if base not in copy.parents:
        return None
    holder = copy
    while holder.parent != base:
        holder = holder.parent
    return holder


def started(files: int, size: int) -> dict:
    return {"type": "start", "files": files, "bytes": size}


def progress(copied: int, files: int, bytes_copied: int, size: int) -> dict:
    return {"type": "progress", "copied": copied, "files": files, "bytes_copied": bytes_copied, "bytes": size}


def done(path: PurePath, files: int, size: int) -> dict:
    return {"type": "done", "path": str(path), "files": files, "bytes": size}
