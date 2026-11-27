"""The visits kept with the records of the research projects — their visits, the unknown ones, the revisions planned —, kept by the ids of what
they point to and told with what it is called (domain.references): the catalog says it, through its contract, as records."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from wildintel_uploader.modules.catalog.domain.records import CatalogRecords
from wildintel_uploader.modules.visits.domain import references as refs_of
from wildintel_uploader.modules.visits.domain.references import Refs
from wildintel_uploader.shared import audit, storage


class KeptVisits:
    """The visits of the research projects of a collections folder; `records` is its catalog, as records."""

    def __init__(self, root: Path, records: Callable[[], CatalogRecords]) -> None:
        self.root, self._records = root, records

    def _store(self) -> storage.ProjectStore:
        return storage.open_store(self.root)

    def _raw(self, project: str) -> list[dict]:
        return self._store().read_records(project, "visits")

    def _write_raw(self, project: str, visits: list[dict]) -> None:
        self._store().write_records(project, "visits", visits)

    def _refs(self, project: str, trappers=None) -> Refs:
        records = self._records()
        return Refs(records.locations(project, include_deleted=True), records.equipment(project, "cameras", include_deleted=True),
                    records.equipment(project, "sd_cards", include_deleted=True),
                    records.trapper_records() if trappers is None else [t if isinstance(t, dict) else t.model_dump(mode="json") for t in trappers])

    def _modifiable(self, project: str) -> None:
        records = self._records()
        records.require_modifiable(project)
        records.require_project(project)

    def kept_count(self, project: str) -> int:
        return len(self._raw(project))

    def list(self, project: str, location_id: str | None = None, trappers=None) -> list[dict]:
        """The visits kept for a research project, in the order they were registered — those to one location (found ignoring case) when it is
        given. A file kept with a day and a time only, or with the names (an earlier version), is moved to instants and to ids when it is read — in
        the timezone its locations say —, and written back so.

        Raises:
            storage.StorageError: the research project id can't be a folder name."""
        raw = self._raw(project)
        kept, visits = refs_of.read_kept(raw, self._refs(project, trappers), project)
        if kept != raw and raw:
            self._write_raw(project, kept)
        if location_id is None:
            return visits
        return [v for v in visits if str(v.get("location_id", "")).lower() == location_id.lower()]

    def add(self, project: str, visit: dict) -> dict:
        self.add_many(project, [visit])
        return refs_of.as_told(self._raw(project)[-1], self._refs(project))

    def add_many(self, project: str, new: list[dict]) -> int:
        """Registers visits to a research project that's already kept here; a visit that is known takes the place of the unknown one of its site in
        its revision. Says how many."""
        self._modifiable(project)
        if new:
            self.list(project)   # an earlier file is moved to instants and to ids first
            refs = self._refs(project)
            at = audit.now()
            self._write_raw(project, self._raw(project) + [audit.stamped(refs_of.as_kept(v, refs), None, at) for v in new])
            known = {(str(v.get("location_id", "")).lower(), str(v.get("session") or "").upper()) for v in new}
            unknown = self.unknown(project)
            left = [u for u in unknown if (u["location_id"].lower(), u["session"].upper()) not in known]
            if len(left) != len(unknown):
                self._write_unknown(project, left)
        return len(new)

    def update(self, project: str, location_id: str, session: str, visit: dict) -> dict:
        """Replaces a visit kept — found by its site (ignoring case) and its revision, which is its key and does not change —; the deployment it
        closed stays.

        Raises:
            storage.StorageError: the research project isn't there, or it has no visit to that site in that revision."""
        self._modifiable(project)
        self.list(project)
        refs = self._refs(project)
        raw = self._raw(project)
        index = next((i for i, v in enumerate(raw) if refs_of.site(v, refs).lower() == location_id.lower()
                      and str(v.get("session") or "").upper() == session.upper()), None)
        if index is None:
            raise storage.StorageError(f"There is no visit to {location_id} in {session}.")
        kept = refs_of.as_kept({**visit, "location_id": refs_of.site(raw[index], refs), "session": raw[index]["session"]}, refs)
        if raw[index].get("deployment_id"):
            kept["deployment_id"] = raw[index]["deployment_id"]
        raw[index] = audit.stamped(kept, raw[index])
        self._write_raw(project, raw)
        return refs_of.as_told(raw[index], refs)

    def replace_all(self, project: str, visits: list[dict]) -> None:
        """Keeps these visits — told — as all the research project's (a backup restored): each keeps its own id and its dates."""
        self._modifiable(project)
        refs = self._refs(project)
        self._write_raw(project, [refs_of.as_kept(v, refs) for v in visits])

    def write_states(self, project: str, states: dict[tuple[str, str], str | None]) -> int:
        """Keeps the state of the visits — found by their site (ignoring case) and their instant — where it changed; says how many changed."""
        self.list(project)
        refs = self._refs(project)
        raw = self._raw(project)
        changed = 0
        for visit in raw:
            key = (refs_of.site(visit, refs).lower(), str(visit.get("when") or ""))
            if key in states and visit.get("state") != states[key]:
                visit["state"] = states[key]
                audit.touched(visit)
                changed += 1
        if changed:
            self._write_raw(project, raw)
        return changed

    def closed(self, project: str) -> list[dict]:
        return refs_of.closed(self.list(project))

    def link(self, project: str, location_id: str, date: str, time: str, deployment_id: str) -> dict:
        """Records on a visit (found by its location, ignoring case, day and time) the deployment it closed.

        Raises:
            storage.StorageError: the visit isn't in the research project."""
        self.list(project)
        raw = self._raw(project)
        refs = self._refs(project)
        visit = next((v for v in raw if refs_of.site(v, refs).lower() == location_id.lower()
                      and (refs_of.as_told(v, refs).get("date"), refs_of.as_told(v, refs).get("time")) == (date, time)), None)
        if visit is None:
            raise storage.StorageError(f"There is no visit to {location_id} on {date} at {time} in {project}.")
        if visit.get("deployment_id") != deployment_id:
            visit["deployment_id"] = deployment_id
            audit.touched(visit)
        self._write_raw(project, raw)
        return refs_of.as_told(visit, refs)

    # the unknown visits and the revisions planned

    def unknown(self, project: str) -> list[dict]:
        return refs_of.unknown_told(self._store().read_records(project, "unknown_visits"), self._records().locations(project, include_deleted=True))

    def _write_unknown(self, project: str, unknown: list[dict]) -> None:
        if not unknown:
            self._store().delete_records(project, "unknown_visits")
            return
        self._store().write_records(project, "unknown_visits", refs_of.unknown_kept(unknown, self._records().locations(project, include_deleted=True)))

    def add_unknown(self, project: str, new: list[dict]) -> int:
        """Keeps more unknown visits — those already kept are not repeated —; says how many were added."""
        self._modifiable(project)
        have = self.unknown(project)
        keys = {(u["location_id"].lower(), u["session"].upper()) for u in have}
        added = [{"location_id": u["location_id"], "session": u["session"].upper()} for u in new if (u["location_id"].lower(), u["session"].upper()) not in keys]
        if added:
            self._write_unknown(project, [*have, *added])
        return len(added)

    def planned_revisions(self, project: str) -> list[str]:
        """The revisions planned before any visit was made to them — "R0003" —, oldest first."""
        return sorted({str(r.get("session") or "").upper() for r in self._store().read_records(project, "planned_revisions") if r.get("session")})

    def plan_revision(self, project: str, session: str) -> str:
        self._modifiable(project)
        session = session.upper()
        if session not in self.planned_revisions(project):
            records = self._store().read_records(project, "planned_revisions")
            self._store().write_records(project, "planned_revisions", [*records, {"session": session, "created_at": audit.now()}])
        return session
