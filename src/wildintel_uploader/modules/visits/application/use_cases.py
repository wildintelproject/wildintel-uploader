"""The use cases of the visits — what was the router of the visits: registering one, editing it, planning a revision and finishing it, reading a
file or a source of visits and keeping them, and what the visits say of the deployments. A visit is kept only if it follows the rules
(domain.rules); what it does to the locations, the cameras and the SD cards is done with it, with the visit as the reason in the history."""
from __future__ import annotations

import csv
import io
import threading

from wildintel_uploader.modules.sources.domain.models import SourceError
from wildintel_uploader.modules.sources.domain.ports import SourcesService
from wildintel_uploader.modules.sources.domain.models import VISIT_COLUMNS
from wildintel_uploader.modules.visits.application.visit_file import VisitFiles
from wildintel_uploader.modules.visits.domain import deployments as visit_deployments, rules, wall_clock
from wildintel_uploader.modules.visits.domain.models import ImportOptions, VisitLocked, VisitMissing, VisitRefused, VisitsError, VisitsFailed
from wildintel_uploader.modules.visits.domain.ports import (
    Clock, StateHistory, Uploads, Visit, VisitCatalog, VisitDeployments, VisitFile, VisitReports, VisitRepository, VisitSettings, VisitsService,
)
from wildintel_uploader.modules.visits.domain.shapes import Camera, ClosedVisit, Location, SdCard

# One save of visits at a time for a research project: two saves of the same file, run together, would each keep what the other is keeping.
_saving: dict[str, threading.Lock] = {}
_saving_guard = threading.Lock()


def save_lock(project: str) -> threading.Lock:
    with _saving_guard:
        return _saving.setdefault(project.lower(), threading.Lock())


def _location_of(locations: list[Location], location_id) -> Location | None:
    return next((loc for loc in locations if str(loc.get("location_id", "")).lower() == str(location_id or "").lower()), None)


def _zones(locations: list[Location]) -> dict[str, str | None]:
    return {str(loc.get("location_id", "")).lower(): loc.get("timezone") for loc in locations}


def _wall_clock(visit: Visit) -> str:
    """The day and the time of a visit on the wall clock of its location (2026-09-14T08:30:00) — what the visit says, not the instant."""
    return f"{visit.get('date')}T{visit.get('time')}"


def with_location_coordinates(text: str) -> str:
    """The CSV of the visits of Epicollect5 with two columns more, the coordinates of the location: the form says only the place of the visit, which
    a new location takes."""
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        return text
    names = [*rows[0].keys(), "location_latitude", "location_longitude"]
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=names, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({**row, "location_latitude": row.get("latitude", ""), "location_longitude": row.get("longitude", "")})
    return out.getvalue()


class VisitsUseCases(VisitsService):
    def __init__(self, repository: VisitRepository, catalog: VisitCatalog, *, deployments: VisitDeployments, file: VisitFile, sources: SourcesService,
                 uploads: Uploads, reports: VisitReports, history: StateHistory, settings: VisitSettings, clock: Clock) -> None:
        self._visits, self._catalog, self._deployments, self._file, self._sources = repository, catalog, deployments, VisitFiles(file), sources
        self._uploads, self._reports, self._history, self._settings, self._clock = uploads, reports, history, settings, clock

    # ── what the visits kept do ──

    def _refresh_states(self, project: str) -> None:
        """A visit that left a camera is collected once a later one took its card, and the one just added has its own."""
        self._visits.write_states(project, visit_deployments.visit_states(self._visits.list(project), self._settings.keep_seconds()))

    def _make_folders(self, project: str, new: list[Visit]) -> dict:
        """The folders of the collections the new visits change — made when a visit is registered, not when its deployment is imported."""
        if not new:
            return {"collections": []}
        self._catalog.require_project(project)
        visits, keep_seconds = self._visits.list(project), self._settings.keep_seconds()
        wanted = set(visit_deployments.collections_of(visits, new, keep_seconds))
        by_collection: dict[str, list[dict]] = {}
        for d in visit_deployments.deployments(visits, keep_seconds):
            if d["collection"] in wanted:
                by_collection.setdefault(d["collection"], []).append(d)
        made = []
        for collection, items in sorted(by_collection.items()):
            self._deployments.make_collection(project, collection)
            made.append({"collection": collection, "closed": sum(d["status"] == "closed" for d in items), "open": sum(d["status"] == "open" for d in items)})
        return {"collections": made}

    def _archive_locations(self, project: str, new: list[Visit]) -> list[str]:
        """The locations that the visits with an Archive action give up: archived from the day of the visit, with a note that says which visit did it."""
        done = []
        for v in new:
            if "Archive" not in (v.get("actions") or []):
                continue
            note = f"Archived in the visit {v.get('session')}" + (f": {v['comments']}" if v.get("comments") else "")
            try:
                with self._history.because(f"The visit {v.get('session')} to {v['location_id']}.", v.get("date")):
                    self._catalog.change_location(project, v["location_id"], {"status": "archived", "status_date": v["date"], "status_note": note})
                done.append(v["location_id"])
            except VisitsFailed:
                continue
        return done

    def _apply_to_entities(self, project: str, new: list[Visit], before: list[Visit]) -> None:
        """What the visits just kept do to the locations, the cameras and the SD cards (rules.entity_changes): in the field, back to ready, or archived
        when stolen. What is archived is for good, and is never changed; what the research project does not keep is left alone."""
        history = list(before)
        changes: list[tuple[Visit, dict]] = []
        for visit in sorted(new, key=rules._stamp):
            changes += [(visit, c) for c in rules.entity_changes(visit, history)]
            history.append(visit)
        for visit, change in [(v, c) for v, c in changes if c["kind"] == "locations"]:
            site = _location_of(self._catalog.locations(project), change["name"])
            if site is not None and site.get("status") in (None, "pending", "ready", "active") and site.get("status") != change["status"]:
                try:
                    with self._history.because(f"The visit {visit.get('session')} to {visit['location_id']}.", visit.get("date")):
                        self._catalog.change_location(project, site["location_id"], {"status": change["status"]})
                except VisitsFailed:
                    continue
        for kind in ("cameras", "sd_cards"):
            wanted = [(v, c) for v, c in changes if c["kind"] == kind]
            if not wanted:
                continue
            items = self._catalog.equipment(project, kind)
            changed = False
            why: dict[tuple[str, str], tuple[str, str | None]] = {}
            for visit, change in wanted:
                for item in items:
                    names = {str(item.get("label") or "").strip()} | ({str(item.get("camera_id") or "").strip()} if kind == "cameras" else set())   # as written
                    if change["name"].strip() not in names or item.get("status") == "archived" or item.get("status") == change["status"]:
                        continue
                    item["status"] = change["status"]
                    why[(kind, str(item.get("label") or item.get("camera_id") or "").lower())] = (f"The visit {visit.get('session')} to {visit['location_id']}.",
                                                                                                 visit.get("date"))
                    if change["status"] == "archived":
                        item["archive_reason"], item["status_date"] = change["reason"], visit.get("date")
                        item["status_note"] = "Stolen" if kind == "cameras" else "Stolen with the camera"
                    changed = True
            if changed:
                with self._history.because("The visits.", None, why):
                    self._catalog.keep_equipment(project, kind, items)

    def _not_entities(self, project: str, old: Visit | None, visit: Visit) -> list[str]:
        """What a visit says that is not an entity: a camera or an SD card that is not one of the research project's, a trapper that is not one. Only
        what changed from `old` is said — what the visit already had stays, as it may have been kept without being listed."""
        reasons = []
        cameras = {str(x) for c in self._catalog.equipment(project, "cameras") if c.get("status") != "planned" for x in (c.get("camera_id"), c.get("label")) if x}
        cards = {str(c.get("label")) for c in self._catalog.equipment(project, "sd_cards") if c.get("status") != "planned"}
        trappers = {t["name"] for t in self._catalog.trappers()}
        names = lambda text: [n.strip() for n in str(text or "").split(",") if n.strip()]  # noqa: E731
        camera, card = visit.get("camera_id"), visit.get("sd")
        if camera and str(camera) not in cameras and str(camera) != str((old or {}).get("camera_id") or ""):
            reasons.append(f"The camera {camera} is not one of the cameras of {project}.")
        if card and str(card) not in cards and str(card) != str((old or {}).get("sd") or ""):
            reasons.append(f"The SD card {card} is not one of the SD cards of {project}.")
        before = set(names((old or {}).get("trappers")))
        reasons += [f"{n} is not one of the trappers." for n in names(visit.get("trappers")) if n not in trappers and n not in before]
        return reasons

    # ── one visit ──

    def visits(self, project: str, location_id: str | None = None) -> list[Visit]:
        return self._visits.list(project, location_id)

    def unknown(self, project: str) -> list[Visit]:
        return self._visits.unknown(project)

    def kept_count(self, project: str) -> int:
        return self._visits.kept_count(project)

    def replace_all(self, project: str, visits: list[Visit]) -> None:
        self._visits.replace_all(project, visits)

    def save(self, project: str, visit: Visit) -> Visit:
        self._catalog.require_project(project, active=True)
        visit = dict(visit)
        locations = self._catalog.locations(project)
        # the rules compare instants: the day and the time are the wall clock of the location
        location = _location_of(locations, visit["location_id"])
        visit["when"] = wall_clock.to_when(visit["date"], visit["time"], location)
        kept_visits = self._visits.list(project)
        visit = rules.with_site_start(visit, kept_visits, location)
        cards = self._catalog.equipment(project, "sd_cards")
        unknown = self._visits.unknown(project)
        # a visit that takes the place of an unknown one is put where its instant says, among the visits that are kept
        fills = any(u["location_id"].lower() == visit["location_id"].lower() and u["session"].upper() == str(visit["session"]).upper() for u in unknown)
        reasons = self._not_entities(project, None, visit) + (rules.edit_errors(None, visit, kept_visits, locations, cards, unknown) if fills
                                                               else rules.refusals(visit, kept_visits, locations, cards, unknown))
        if reasons:
            raise VisitRefused(" ".join(reasons))
        kept = self._visits.add(project, visit)
        self._archive_locations(project, [kept])
        self._apply_to_entities(project, [kept], kept_visits)
        self._refresh_states(project)
        return {**kept, "collection_folders": self._make_folders(project, [kept])}

    def update(self, project: str, location_id: str, session: str, visit: Visit) -> Visit:
        self._catalog.require_project(project)
        kept_visits = self._visits.list(project)
        old = next((v for v in kept_visits if v["location_id"].lower() == location_id.lower() and str(v.get("session") or "").upper() == session.upper()), None)
        if old is None:
            raise VisitMissing(f"There is no visit to {location_id} in {session}.")
        if (str(old["location_id"]).lower(), str(old.get("when") or "")) in visit_deployments.locked(kept_visits, self._settings.keep_seconds()):
            raise VisitLocked(f"The visit to {old['location_id']} in {old['session']} starts or closes a deployment that is imported: it cannot be edited.")
        visit = {**visit, "location_id": old["location_id"], "session": old["session"]}
        if ("Archive" in (old.get("actions") or [])) != ("Archive" in visit["actions"]):
            raise VisitRefused("The action Archive cannot be added to a visit or taken from it by editing.")
        locations = self._catalog.locations(project)
        location = _location_of(locations, visit["location_id"])
        visit["when"] = wall_clock.to_when(visit["date"], visit["time"], location)
        others = [v for v in kept_visits if v is not old]
        if rules.camera_status_code(visit.get("camera_status")) == "New site":
            visit = rules.with_site_start(visit, others, location)
        reasons = self._not_entities(project, old, visit) + rules.edit_errors(old, visit, others, locations, self._catalog.equipment(project, "sd_cards"),
                                                                              self._visits.unknown(project))
        if reasons:
            raise VisitRefused(" ".join(reasons))
        kept = self._visits.update(project, location_id, session, visit)
        self._refresh_states(project)
        return {**kept, "collection_folders": self._make_folders(project, [kept])}

    # ── the revisions ──

    def create_revision(self, project: str) -> dict:
        """A revision is one trip to every location, so the one before has to be finished for visits to be made in the new one: when it is not, the
        answer says which locations are still to be visited in it (`previous`). A revision planned with no visit yet is the last."""
        self._catalog.require_project(project, active=True)
        visits, locations = self._visits.list(project), self._catalog.locations(project)
        unknown, planned = self._visits.unknown(project), self._visits.planned_revisions(project)
        made = {n for n in (rules._session_number(v.get("session")) for v in visits) if n is not None}
        known = made | {n for n in (rules._session_number(s) for s in planned) if n is not None} | \
            {n for n in (rules._session_number(u.get("session")) for u in unknown) if n is not None}
        latest = max(known, default=0)
        if latest and latest not in made:
            raise VisitLocked(f"R{latest:04d} is planned and has no visit yet: register its first visit before planning the next revision.")
        sites = [str(loc["location_id"]) for loc in locations if loc.get("location_id") and loc.get("status") not in ("archived", "planned")]
        if not sites:
            raise VisitLocked("No location can be visited: none is ready or active. Add one, or make one ready, in the settings.")
        previous = None
        if latest:
            missing = rules.revision_missing(latest, visits, locations, "", unknown)
            previous = {"session": f"R{latest:04d}", "missing": missing} if missing else None
        session = self._visits.plan_revision(project, f"R{latest + 1:04d}")
        return {"session": session, "planned": sorted(sites, key=str.lower), "previous": previous}

    def mark_not_visited(self, project: str, session: str) -> dict:
        self._catalog.require_project(project)
        locations, kept = self._catalog.locations(project), self._visits.list(project)
        number = int(session[1:])
        planned = {n for n in (rules._session_number(x) for x in self._visits.planned_revisions(project)) if n is not None}
        # a revision that was planned and has no visit yet is marked as not visited on today's day: it has no day of its own
        records = rules.not_visited_records(number, kept, locations, on=self._clock.today() if number in planned else None)
        for record in records:
            record["when"] = wall_clock.to_when(record["date"], record["time"], _location_of(locations, record["location_id"]))
        self._visits.add_many(project, [self._file.normalized(r) for r in records])
        self._refresh_states(project)
        return {"session": session, "marked": [r["location_id"] for r in records]}

    # ── a file of visits ──

    def import_file(self, options: ImportOptions) -> dict:
        """Only one save at a time for a research project: another one is refused while it runs."""
        if not options.save:
            return self._import(options)
        lock = save_lock(options.research_project_id)
        if not lock.acquire(blocking=False):
            raise VisitLocked(f"The visits of {options.research_project_id} are already being saved: wait until that save finishes.")
        try:
            return self._import(options)
        finally:
            lock.release()

    def _source_rows(self, options: ImportOptions) -> tuple[str, str, dict | None, str]:
        """The text to read, its format, its mapping and where the time of a visit comes from — the rows of a source, when the file is one."""
        text, fmt, mapping, time_source = options.csv, options.format, options.mapping, self._settings.time_source()
        if fmt in ("epicollect-api", "epicollect-csv"):
            try:
                rows = self._sources.visits(fmt, text)
            except SourceError as exc:
                raise VisitsFailed(str(exc)) from exc
            # the entries of the API take the time the settings say; the form downloaded has no date or time: when its entry was created
            text, fmt, mapping, time_source = rows.csv, "mapped", {c: c for c in VISIT_COLUMNS}, rows.time_source or time_source
            # the form gives one place, the one of the visit: a location that is created from it has those coordinates
            text = with_location_coordinates(text)
            mapping = {**mapping, "location_latitude": "location_latitude", "location_longitude": "location_longitude"}
        return text, fmt, mapping, time_source

    def _import(self, options: ImportOptions) -> dict:
        project = options.research_project_id
        if options.save:
            self._catalog.require_project(project, active=True)
        locations, kept = self._catalog.locations(project), self._visits.list(project)
        cards, cameras = self._catalog.equipment(project, "sd_cards"), self._catalog.equipment(project, "cameras")
        text, _, mapping, time_source = self._source_rows(options)
        # the form of Epicollect5 lets a site be made on the spot (New site): its timezone is the one asked for, UTC when none was
        from_epicollect = options.format in ("epicollect-csv", "epicollect-api")
        defaults = {"timezone": "UTC", "daylight_saving": "no", **(options.defaults or {})} if from_epicollect else options.defaults
        trappers = self._catalog.trappers()
        result = self._file.parse(text, locations, kept, mapping, {
            "time_source": time_source, "cards": cards, "cameras": cameras, "create": options.create, "close_revisions": options.close_revisions,
            "close_after": options.close_after, "coordinates_from_location": options.coordinates_from_location,
            "photos_not_counted": options.photos_not_counted, "defaults": defaults, "new_site_makes_location": from_epicollect,
            "trappers": self._catalog.trapper_names(), "trapper_usernames": [t.get("username", "") for t in trappers], "unknown": self._visits.unknown(project)})
        saved = collection_folders = report = None
        if options.save and result["problems"]:
            # all or nothing (#206): a file with rows that cannot be added is not kept in part — the rows are corrected and the file read again
            errors = len(result["blocking"]["errors"])
            raise VisitsFailed(f"The file has {len(result['problems'])} row(s) that cannot be added ({errors} with an error of their own): nothing is kept. "
                               "Correct them and read the file again.")
        if options.save:
            saved, collection_folders, report = self._keep(project, result, kept, cameras, cards)
        # each visit is told on the wall clock of its location: the timezone of the location goes with it (the ones this file creates, too)
        zones = _zones([*locations, *result["create"]["locations"]])
        visits = [{**v, "timezone": zones.get(str(v.get("location_id", "")).lower())} for v in result["visits"]]
        return {**result, "visits": visits, "saved": saved, "collection_folders": collection_folders, "report": report}

    def _keep(self, project: str, result: dict, kept: list[Visit], cameras: list[Camera], cards: list[SdCard]) -> tuple[int, dict, str | None]:
        """What the visits need is created first — the trappers who went, their locations, cameras and SD cards —, then the visits."""
        if result["create"]["trappers"]:
            self._catalog.add_trappers(result["create"]["trappers"])
        for location in result["create"]["locations"]:
            self._catalog.add_location(project, location)
        # what the rows say of cameras whose records lacked it — their serial number, make or model — completes them, never overwriting (#231)
        if result["create"].get("complete_cameras"):
            adds = {c["label"]: {k: v for k, v in c.items() if k != "label"} for c in result["create"]["complete_cameras"]}
            cameras = [{**c, **{k: v for k, v in adds.get(str(c.get("label")), {}).items() if not c.get(k)}} for c in cameras]
            self._catalog.keep_equipment(project, "cameras", cameras)
        for kind, kept_items in (("cameras", cameras), ("sd_cards", cards)):
            if result["create"][kind]:
                self._catalog.keep_equipment(project, kind, [*kept_items, *result["create"][kind]])
        # the revision before is closed first, when asked: its locations still planned are kept as not visited
        if result["closed"]:
            self._visits.add_many(project, [self._file.normalized(m) for m in result["closed"]])
        saved = self._visits.add_many(project, result["visits"])
        self._visits.add_unknown(project, result["unknown"])
        self._archive_locations(project, result["visits"])
        self._apply_to_entities(project, result["visits"], kept)
        self._refresh_states(project)
        folders = self._make_folders(project, result["visits"])
        return saved, folders, self._reports.import_report(project, result, saved)

    def export_file(self, project: str, location_id: str | None = None) -> dict:
        visits = self._visits.list(project)
        if location_id:
            visits = [v for v in visits if str(v.get("location_id", "")).lower() == location_id.lower()]
        return {"csv": self._file.export(visits), "filename": f"{project}_visits.csv", "count": len(visits)}

    def epicollect_download(self) -> dict:
        try:
            text = self._sources.visits("epicollect-api").csv
        except SourceError as exc:
            raise VisitsFailed(str(exc)) from exc
        return {"csv": text, "count": max(text.count("\n") - 1, 0)}

    def file_columns(self, text: str) -> dict:
        form = self._sources.form_columns(text)
        return {**self._file.columns(text), "kind": "form" if form else "other", "form_columns": form,
                "form_error": None if form else self._sources.form_error(text)}

    # ── the deployments the visits say ──

    def closed(self, project: str) -> list[ClosedVisit]:
        closed = self._visits.closed(project)
        # each visit is told on the wall clock of its location: the timezone of the location goes with it
        zones = _zones(self._catalog.locations(project, include_deleted=True))

        def zoned(visit: Visit) -> Visit:
            return {**visit, "timezone": zones.get(str(visit.get("location_id", "")).lower())}
        return [{"visit": zoned(c["visit"]), "end": zoned(c["end"]), "details": visit_deployments.merged_details(c["visit"], c["end"])} for c in closed]

    def link(self, project: str, location_id: str, date: str, time: str, deployment_id: str) -> Visit:
        linked = self._visits.link(project, location_id, date, time, deployment_id)
        self._refresh_states(project)
        return linked

    def deployments(self, project: str, location_id: str | None = None) -> list[dict]:
        self._catalog.require_project(project)
        found = visit_deployments.deployments(self._visits.list(project, location_id), self._settings.keep_seconds())
        zones = _zones(self._catalog.locations(project, include_deleted=True))
        results = []
        for d in found:
            imported = d["start_visit"].get("deployment_id")
            uploaded_at, on_trapper = self._uploads.trapper_state(project, imported)
            results.append({k: v for k, v in d.items() if k not in ("start_visit", "end_visit")} | {
                "start_session": d["start_visit"].get("session"), "end_session": (d["end_visit"] or {}).get("session"),
                "start_local": _wall_clock(d["start_visit"]), "end_local": _wall_clock(d["end_visit"]) if d["end_visit"] else None,
                "timezone": zones.get(str(d["site"]).lower()),
                # whether the deployment was created and its images imported (its visit says which deployment it gave), and whether it is on Trapper
                "images_stored": bool(imported), "uploaded_at": uploaded_at, "on_trapper": on_trapper,
                "uploads": self._uploads.uploads_of(project, imported) if imported else [],
                # the upload to each uploader in use is its own: planned, done or failed; a deployment that will not be made has none
                "upload_states": [] if d["no_images"] else self._uploads.upload_states(project, imported, d["deployment_id"]),
            })
        return results

    def book(self, project: str, location_id: str | None = None) -> list[dict]:
        self._catalog.require_project(project)
        self._refresh_states(project)  # what was kept before the states were is given its own
        visits = self._visits.list(project, location_id)
        locations = self._catalog.locations(project) if location_id is None else None
        unknown = [u for u in self._visits.unknown(project) if location_id is None or u["location_id"].lower() == location_id.lower()]
        book = visit_deployments.visit_book(visits, self._settings.keep_seconds(), locations, unknown, self._visits.planned_revisions(project))
        zones = _zones(self._catalog.locations(project, include_deleted=True))
        for visit in book:
            visit["uploaded_at"], visit["on_trapper"] = self._uploads.trapper_state(project, visit.get("deployment_id"))
            visit["timezone"] = zones.get(str(visit.get("location_id", "")).lower())
        return book

    def has_deployment(self, project: str, deployment_id: str) -> bool:
        visits = self._visits.list(project)
        if any(v.get("deployment_id") == deployment_id for v in visits):
            return True
        return any(d["deployment_id"] == deployment_id for d in visit_deployments.deployments(visits, True))


__all__ = ["VisitsError", "VisitsUseCases", "save_lock", "with_location_coordinates"]
