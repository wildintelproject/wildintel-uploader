"""Copying a camera's memory card to a temporary folder of this computer, removing the copy when the import is over, and ejecting the card. The
rules are the domain's (domain.cards); the card and the folder of the copies are what it is given."""
from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from pathlib import Path

from wildintel_uploader.modules.deployments.domain import cards as rules
from wildintel_uploader.modules.deployments.domain.ports import CardCopies, MemoryCard


class CardCopying:
    def __init__(self, card: MemoryCard, copies: CardCopies, now: Callable[[], float] = time.time) -> None:
        self._card, self._copies, self._now = card, copies, now

    def clean_stale(self) -> int:
        """Removes the copies left behind longer than STALE_SECONDS ago; returns how many."""
        now = self._now()
        return sum(self._copies.remove(holder) for holder, modified in self._copies.holders() if rules.stale(modified, now))

    def copy(self, card: str) -> Iterator[dict]:
        """Copies the files of the card to a new folder of the copies, named like the card: "start", "progress" after each file and "done" with
        the `path` of the copy.

        Raises:
            CardCopyError: the card is not a folder that can be read, or has nothing on it, or the folder of the copies has no room for it (checked
                before anything is copied), or a file could not be copied (what was copied is removed)."""
        source, files = self._card.files(card)
        if not files:
            raise rules.empty(card)
        self.clean_stale()
        total = sum(size for _, size in files)
        # there has to be room for the whole card before it starts, not to fail half-way
        short = self._copies.shortfall(total)
        if short:
            raise rules.CardCopyError(short)
        holder = self._copies.new_holder()
        destination = holder / rules.copy_name(source)
        yield rules.started(len(files), total)
        copied = 0
        try:
            for n, (file, size) in enumerate(files, start=1):
                self._copies.copy(source, file, destination)
                copied += size
                yield rules.progress(n, len(files), copied, total)
        except rules.CardCopyError:
            self._copies.remove(holder)
            raise
        yield rules.done(destination, len(files), total)

    def discard(self, copy: str) -> bool:
        """Removes a copy made by `copy` — only one inside the folder of the copies, whatever the path says. Whether something was removed."""
        holder = rules.holder_of(self._copies.base(), Path(copy).expanduser().resolve())
        return holder is not None and self._copies.remove(Path(holder))

    def eject(self, card: str) -> dict:
        return self._card.eject(card)
