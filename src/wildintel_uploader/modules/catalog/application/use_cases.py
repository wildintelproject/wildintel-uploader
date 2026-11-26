"""The use cases of the catalog: `CatalogUseCases` implements its port in (`domain.ports.CatalogService`), given its ports out — where the records are
kept (`CatalogRepository`), the people versions before kept in the settings (`LegacyTrappers`) and the instant (`Clock`) — and how a new id is made."""
from __future__ import annotations

from collections.abc import Callable

from wildintel_uploader.modules.catalog.domain import rules
from wildintel_uploader.modules.catalog.domain.models import Trapper
from wildintel_uploader.modules.catalog.domain.ports import AddedTrappers, CatalogRepository, CatalogService, Clock, LegacyTrappers
from wildintel_uploader.shared import ids


class CatalogUseCases(CatalogService):
    def __init__(self, repository: CatalogRepository, *, legacy_trappers: LegacyTrappers, clock: Clock, new_id: Callable[[], str] = ids.new_id) -> None:
        self.repository, self.legacy_trappers, self.clock, self.new_id = repository, legacy_trappers, clock, new_id

    # ── the people ──

    def _all_trappers(self) -> list[Trapper]:
        """All the people kept — the first time, the ones versions before left in the settings come into the catalog."""
        kept = self.repository.read_trappers()
        if kept:
            return kept
        # as they were kept — with the id they had, which the roles and the visits point to —, not as new ones
        adopted = rules.checked_trappers(self.legacy_trappers.take())
        if adopted:
            self.repository.write_trappers(adopted)
        return adopted

    def trappers(self, include_deleted: bool = False) -> list[Trapper]:
        everyone = self._all_trappers()
        return everyone if include_deleted else [t for t in everyone if not t.deleted]

    def save_trappers(self, trappers: list[Trapper]) -> list[Trapper]:
        wanted = rules.checked_trappers(trappers)
        kept = rules.saved_trappers(self._all_trappers(), wanted, self.clock.now(), self.new_id)
        self.repository.write_trappers(kept)
        return [t for t in kept if not t.deleted]

    def add_trappers(self, trappers: list[Trapper]) -> AddedTrappers:
        alive = self.trappers()
        taken = {t.username.lower() for t in alive}
        added, skipped, new = [], [], []
        for trapper in trappers:
            if trapper.username.lower() in taken:
                skipped.append(trapper.username)
                continue
            taken.add(trapper.username.lower())
            new.append(Trapper(**{**{k: getattr(trapper, k) for k in ("username", "name", "affiliation", "email", "trapper_pk")}, "status": "active"}))
            added.append(trapper.username)
        if new:
            self.save_trappers([*alive, *new])
        return AddedTrappers(added=added, skipped=skipped)
