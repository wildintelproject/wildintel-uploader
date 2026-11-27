"""The visits kept in the folders of the research projects — visits.json, unknown_visits.json, the revisions planned, the upload failures —, told
with the names of what they point to and kept by their ids (the locations, the cameras, the SD cards and the people of the catalog). Moved from
local_folder_service (#248), which still gives these names; what it needs of the catalog it asks its contract, as records."""
from __future__ import annotations

from pathlib import Path

from wildintel_uploader.modules.visits.domain import rules as visit_rules, wall_clock as visit_time
from wildintel_uploader.modules.visits.domain.rules import closes_collection  # noqa: F401 — where the code of before finds it
from wildintel_uploader.shared import audit, identity, ids, storage


def _records(root: Path):
    """The catalog of this collections folder as records — through its contract —, from where the app is put together."""
    from wildintel_uploader.modules.visits.infrastructure import plugs
    return plugs.catalog_of(root).records()


def _raw_visits(root: Path, research_project_id: str) -> list[dict]:
    return storage.open_store(root).read_records(research_project_id, "visits")


def _write_raw_visits(root: Path, research_project_id: str, visits: list[dict]) -> None:
    storage.open_store(root).write_records(research_project_id, "visits", visits)


class _Refs:
    """What the visits of a research project point to, by id and by what it is called: its locations, cameras and SD cards, and the trappers — those that were deleted too."""

    def __init__(self, locations: list[dict], cameras: list[dict], sd_cards: list[dict], trappers: list[dict]):
        self.locations = locations
        self.by_label: dict[str, dict[str, dict]] = {"location": {}, "camera": {}, "sd": {}, "trapper": {}}
        self.by_id: dict[str, dict[str, dict]] = {"location": {}, "camera": {}, "sd": {}, "trapper": {}}
        for l in locations:
            self._add("location", l, [l.get("location_id")])
        for c in cameras:
            self._add("camera", c, [c.get("camera_id"), c.get("label")])
        for c in sd_cards:
            self._add("sd", c, [c.get("label")])
        for t in trappers:
            self._add("trapper", t, [t.get("name"), t.get("username")])

    def _add(self, kind: str, record: dict, labels: list) -> None:
        if record.get("id"):
            self.by_id[kind][record["id"]] = record
        for label in labels:
            if label:
                self.by_label[kind].setdefault(identity.key(kind, label), record)


# What a visit says of what it points to — (told as, kept as an id in, kind): told by what it is called, kept by the id. What cannot be found (a card nobody registered) is kept as it was said.
_POINTS_TO = (("location_id", "location_ref", "location"), ("camera_id", "camera_ref", "camera"), ("sd", "sd_ref", "sd"), ("setup_by", "setup_by_ref", "trapper"))
_CALLED = {
    "location": lambda r: r.get("location_id"), "camera": lambda r: r.get("label") or r.get("camera_id"), "sd": lambda r: r.get("label"), "trapper": lambda r: r.get("name"),
}


def camera_model_of(record: dict) -> str | None:
    """The model of a camera as Camtrap DP's cameraModel says it — the make and the model, make-model — from its record: the model alone when it has no make."""
    make, model = str(record.get("camera_make") or "").strip(), str(record.get("camera_model") or "").strip()
    return f"{make}-{model}" if make and model and not model.lower().startswith(make.lower()) else (model or None)


def _what_the_camera_is(record: dict) -> dict:
    """What a visit tells of its camera from its record (#231): it only points to it (camera_ref), and what the camera is — its model as Camtrap DP says it and
    its serial number — is the record's, copied for whoever needs it (the deployment), never kept in the visit."""
    out: dict = {}
    if (model := camera_model_of(record)) is not None:
        out["camera_model"] = model
    if str(record.get("camera_id") or "").strip():
        out["camera_serial"] = str(record["camera_id"]).strip()
    return out


def _refs(root: Path, research_project_id: str, trappers=None) -> _Refs:
    return _Refs(
        _records(root).locations(research_project_id, include_deleted=True), _records(root).equipment(research_project_id, "cameras", include_deleted=True),
        _records(root).equipment(research_project_id, "sd_cards", include_deleted=True), (_records(root).trapper_records() if trappers is None else [t if isinstance(t, dict) else t.model_dump(mode="json") for t in trappers]),
    )


def _location_of(locations: list[dict], location_id) -> dict | None:
    return next((l for l in locations if str(l.get("location_id", "")).lower() == str(location_id or "").lower()), None)


def _site(visit: dict, refs: _Refs) -> str:
    """The site of a visit, as it is called — whether the visit is kept (by the id of its location) or told."""
    return str((refs.by_id["location"].get(visit.get("location_ref")) or {}).get("location_id") or visit.get("location_id") or "")


def _linked(visit: dict, refs: _Refs) -> dict:
    """A visit with what it points to said by id: the location, the camera, the SD card and who went and set it up are the ones the research project has — if it has them —, so the
    visit says *which* — their ids — and not what they are called, which can be corrected. What it points to that the research project has not is kept as it was said, and is
    linked when it has it."""
    out = dict(visit)
    for told, kept, kind in _POINTS_TO:
        if kind == "camera":
            _link_camera(out, refs)
            continue
        text = out.get(told)
        record = refs.by_label[kind].get(identity.key(kind, text)) if text not in (None, "") else None
        if record is not None and record.get("id"):
            out[kept] = record["id"]
            out.pop(told, None)
    names = [n.strip() for n in str(out.get("trappers") or "").split(",") if n.strip()]
    if names:
        found = [refs.by_label["trapper"].get(identity.key("trapper", n)) for n in names]
        known = [*(out.get("trapper_refs") or []), *[r["id"] for r in found if r is not None and r.get("id")]]
        if known:
            out["trapper_refs"] = list(dict.fromkeys(known))
        rest = [n for n, r in zip(names, found) if r is None or not r.get("id")]
        if rest:
            out["trappers"] = ", ".join(rest)
        else:
            out.pop("trappers", None)
    return out


def _link_camera(out: dict, refs: _Refs) -> None:
    """The camera of a visit kept by the id of its record (#231): the one it already points to (camera_ref), else the one it names — by its label, or by its
    serial number when it says only that. Then what the camera is (its model, its serial number) is the record's, and is not kept in the visit — unless the
    record says no model, when the one the visit wrote is kept. A camera with no record is kept as it was said, and is linked when it has one."""
    record = refs.by_id["camera"].get(out.get("camera_ref"))
    if record is None:
        text = out.get("camera_id") or out.get("camera_serial")
        record = refs.by_label["camera"].get(identity.key("camera", text)) if text not in (None, "") else None
    if record is None or not record.get("id"):
        out.pop("camera_ref", None)
        return
    out["camera_ref"] = record["id"]
    out.pop("camera_id", None)
    out.pop("camera_serial", None)
    if str(record.get("camera_model") or "").strip():
        out.pop("camera_model", None)


def _unlinked(visit: dict, refs: _Refs) -> dict:
    """A visit as it is told: what it points to said by what it is called now — and its camera with the id of its record beside (camera_ref) and what the record
    says it is (#231)."""
    out = dict(visit)
    for told, kept, kind in _POINTS_TO:
        record = refs.by_id[kind].get(out.get(kept) if kind == "camera" else out.pop(kept, None))
        if record is not None:
            out[told] = _CALLED[kind](record)
            if kind == "camera":
                out.update(_what_the_camera_is(record))
        elif kind == "camera":
            out.pop(kept, None)
    named = [str(refs.by_id["trapper"][t]["name"]) for t in out.pop("trapper_refs", None) or [] if t in refs.by_id["trapper"]]
    rest = [n.strip() for n in str(out.get("trappers") or "").split(",") if n.strip()]
    if named or "trappers" in out:
        out["trappers"] = ", ".join([*named, *rest]) or None
    return out


def _kept(visit: dict, refs: _Refs) -> dict:
    """A visit as it is kept: the instant, ISO 8601 in UTC with a Z (`when`), and not the day and the time of the wall clock of its location; and what it points to said by id."""
    visit = _two_fields(visit)
    if "status" in visit:   # kept before it was called camera_status
        visit = {("camera_status" if k == "status" else k): v for k, v in visit.items() if not (k == "status" and "camera_status" in visit)}
    if visit.get("when"):
        return _linked({k: v for k, v in visit.items() if k not in ("date", "time")}, refs)
    if not (visit.get("date") and visit.get("time")):
        return _linked(dict(visit), refs)  # no time to keep
    out = {k: v for k, v in visit.items() if k not in ("date", "time")}
    out["when"] = visit_time.to_when(visit["date"], visit["time"], _location_of(refs.locations, _site(visit, refs)))
    return _linked(out, refs)


def _two_fields(visit: dict) -> dict:
    """A visit kept with card_batteries_ok — one field for the batteries and the card — says each in a field of its own."""
    if "card_batteries_ok" not in visit:
        return visit
    battery, card = visit_rules.split_card_batteries(visit["card_batteries_ok"])
    out = {k: v for k, v in visit.items() if k != "card_batteries_ok"}
    if battery and not out.get("battery_status"):
        out["battery_status"] = battery
    if card and not out.get("card_status"):
        out["card_status"] = card
    return out


def _told(visit: dict, refs: _Refs) -> dict:
    """A visit as it is told: with the day and the time of the wall clock of its location, from its instant, beside it, and what it points to by what it is called. The card and
    the batteries are told as they are written now: a visit kept with SinPilas or CarFullSinPilas says NoBatteries or CarFullNoBatteries."""
    told = _unlinked(visit, refs)
    if not told.get("when"):
        return told
    date, time = visit_time.to_wall(told["when"], _location_of(refs.locations, told.get("location_id")))
    return {**told, "date": date, "time": time}


def _with_the_camera_there(visits: list[dict]) -> list[dict]:
    """The visits told with the camera they are of: a Revision, a Desinstallation or a Stolen visit does not say which camera — it is the one at its site, which the visit before says —,
    so it is told as that one (it is not kept: it would say twice what the visit that put it up says)."""
    out = [dict(v) for v in visits]
    there: dict[str, tuple[str, str | None]] = {}
    for v in sorted(out, key=visit_rules._stamp):
        site = str(v.get("location_id") or "").lower()
        if visit_rules.is_not_revised(v):
            continue
        actions = set(v.get("actions") or [])
        if not v.get("camera_id") and {"Revision", "Desinstallation", "Stolen"} & actions and "Installation" not in actions and site in there:
            v["camera_id"], model = there[site]
            if model and not v.get("camera_model"):
                v["camera_model"] = model
        if visit_rules._takes_away(v):
            there.pop(site, None)
        if visit_rules._leaves_camera(v) and v.get("camera_id"):
            there[site] = (v["camera_id"], v.get("camera_model"))
    return out


def list_visits(root: Path, research_project_id: str, location_id: str | None = None, trappers=None) -> list[dict]:
    """The visits kept for a research project, in the order they were registered — those to one location (found ignoring
    case) when it is given. Empty until one is registered.

    A visit is kept as an instant, `when` (ISO 8601, UTC, with a Z), and told with the day (`date`) and the time (`time`) of the wall clock of its
    location, in the timezone the location says. It is kept pointing to its location, its camera, its SD card and the trappers by their ids, and told with what they are called
    now (see ids). A file kept with a day and a time only, or with the names (an earlier version), is moved to instants and to ids when it is read — in the timezone its
    locations say —, and written back so; and the visits come the same.

    Raises:
        storage.StorageError: the research project id can't be a folder name.
    """
    raw = _raw_visits(root, research_project_id)
    refs = _refs(root, research_project_id, trappers)
    kept = []
    for visit in raw:
        try:
            one = _kept(visit, refs)
        except (KeyError, ValueError, TypeError):
            one = visit  # not a visit it can read the time of: left as it is
        if not one.get("id"):   # kept before the ids existed: the same one whenever it is read
            one = {**one, "id": ids.legacy_id("visit", f"{_site(one, refs)}|{one.get('when') or ''}", research_project_id)}
        kept.append(one)
    if kept != raw and raw:
        _write_raw_visits(root, research_project_id, kept)
    visits = _with_the_camera_there([_told(v, refs) for v in kept])
    if location_id is None:
        return visits
    return [v for v in visits if str(v.get("location_id", "")).lower() == location_id.lower()]


def write_visit(root: Path, research_project_id: str, visit: dict) -> dict:
    """Registers a visit to a research project that's already kept here — given with the day and the time of the wall clock of its location,
    kept as an instant (see list_visits) and returned told.

    Raises:
        storage.StorageError: the research project isn't there.
    """
    write_visits(root, research_project_id, [visit])
    return _told(_raw_visits(root, research_project_id)[-1], _refs(root, research_project_id))


def list_unknown(root: Path, research_project_id: str) -> list[dict]:
    """The visits that are unknown — {"location_id", "session"}: the revisions before the first one kept to a site, of which nothing is known (see visit_rules.unknown_records)."""
    where = {l["id"]: l for l in _records(root).locations(research_project_id, include_deleted=True) if l.get("id")}
    out = []
    for u in storage.open_store(root).read_records(research_project_id, "unknown_visits"):
        site = (where.get(u.get("location_ref")) or {}).get("location_id") or u.get("location_id")
        if site and u.get("session"):
            out.append({"location_id": site, "session": u["session"]})
    return out


def _write_unknown(root: Path, research_project_id: str, unknown: list[dict]) -> None:
    """Keeps the unknown visits — each pointing to its location by id, when the research project has it."""
    if not unknown:
        storage.open_store(root).delete_records(research_project_id, "unknown_visits")
        return
    where = {str(l.get("location_id", "")).lower(): l for l in _records(root).locations(research_project_id, include_deleted=True)}
    stored = []
    for u in unknown:
        place = where.get(str(u["location_id"]).lower())
        stored.append({"location_ref": place["id"], "session": u["session"]} if place and place.get("id") else {"location_id": u["location_id"], "session": u["session"]})
    storage.open_store(root).write_records(research_project_id, "unknown_visits", stored)


def write_unknown(root: Path, research_project_id: str, new: list[dict]) -> int:
    """Keeps more unknown visits — those already kept are not repeated; returns how many were added.

    Raises:
        storage.StorageError: the research project isn't there."""
    _records(root).require_modifiable(research_project_id)
    _records(root).require_project(research_project_id)
    have = list_unknown(root, research_project_id)
    keys = {(u["location_id"].lower(), u["session"].upper()) for u in have}
    added = [{"location_id": u["location_id"], "session": u["session"].upper()} for u in new if (u["location_id"].lower(), u["session"].upper()) not in keys]
    if added:
        _write_unknown(root, research_project_id, [*have, *added])
    return len(added)


def list_planned_revisions(root: Path, research_project_id: str) -> list[str]:
    """The revisions that were planned before any visit was made to them — "R0003": a revision is a trip to every location, and it exists in the visit book, with a planned
    visit to each location, from the day it is planned, not only from its first visit. Oldest first."""
    kept = {str(r.get("session") or "").upper() for r in storage.open_store(root).read_records(research_project_id, "planned_revisions") if r.get("session")}
    return sorted(kept)


def plan_revision(root: Path, research_project_id: str, session: str) -> str:
    """Keeps a revision as planned — `session` is "R0003" —, and says when it was.

    Raises:
        storage.StorageError: the research project isn't there or cannot be changed."""
    _records(root).require_modifiable(research_project_id)
    _records(root).require_project(research_project_id)
    session = session.upper()
    if session not in list_planned_revisions(root, research_project_id):
        records = storage.open_store(root).read_records(research_project_id, "planned_revisions")
        storage.open_store(root).write_records(research_project_id, "planned_revisions", [*records, {"session": session, "created_at": audit.now()}])
    return session


def update_visit(root: Path, research_project_id: str, location_id: str, session: str, visit: dict) -> dict:
    """Replaces a visit kept — found by its site (ignoring case) and its revision, which is its key and does not change — with `visit`, given with the day and the
    time of the wall clock of its location; the deployment it closed, when it has one, stays. Returned told.

    Raises:
        storage.StorageError: the research project isn't there, or it has no visit to that site in that revision."""
    _records(root).require_modifiable(research_project_id)
    _records(root).require_project(research_project_id)
    list_visits(root, research_project_id)  # an earlier file is moved to instants and to ids first
    refs = _refs(root, research_project_id)
    raw = _raw_visits(root, research_project_id)
    index = next((i for i, v in enumerate(raw) if _site(v, refs).lower() == location_id.lower() and str(v.get("session") or "").upper() == session.upper()), None)
    if index is None:
        raise storage.StorageError(f"There is no visit to {location_id} in {session}.")
    kept = _kept({**visit, "location_id": _site(raw[index], refs), "session": raw[index]["session"]}, refs)
    if raw[index].get("deployment_id"):
        kept["deployment_id"] = raw[index]["deployment_id"]
    raw[index] = audit.stamped(kept, raw[index])
    _write_raw_visits(root, research_project_id, raw)
    return _told(raw[index], refs)


def write_visits(root: Path, research_project_id: str, new: list[dict]) -> int:
    """Registers several visits at once to a research project that's already kept here; returns how many.

    Raises:
        storage.StorageError: the research project isn't there.
    """
    _records(root).require_modifiable(research_project_id)
    _records(root).require_project(research_project_id)
    if new:
        list_visits(root, research_project_id)  # an earlier file is moved to instants and to ids first
        refs = _refs(root, research_project_id)
        at = audit.now()
        _write_raw_visits(root, research_project_id, _raw_visits(root, research_project_id) + [audit.stamped(_kept(v, refs), None, at) for v in new])
        # a visit that is known takes the place of the unknown one of its site in its revision
        known = {(str(v.get("location_id", "")).lower(), str(v.get("session") or "").upper()) for v in new}
        unknown = list_unknown(root, research_project_id)
        left = [u for u in unknown if (u["location_id"].lower(), u["session"].upper()) not in known]
        if len(left) != len(unknown):
            _write_unknown(root, research_project_id, left)
    return len(new)


def replace_visits(root: Path, research_project_id: str, visits: list[dict]) -> None:
    """Keeps these visits — told, as `list_visits` gives them — as all the research project's: a backup that is restored, say. Each is kept as an instant and pointing by id to
    what the research project has that it is called; it keeps its own `id` and its dates.

    Raises:
        storage.StorageError: the research project isn't there."""
    _records(root).require_modifiable(research_project_id)
    _records(root).require_project(research_project_id)
    refs = _refs(root, research_project_id)
    _write_raw_visits(root, research_project_id, [_kept(v, refs) for v in visits])


def write_states(root: Path, research_project_id: str, states: dict[tuple[str, str], str | None]) -> int:
    """Keeps the `state` of the visits — found by their site (ignoring case) and their instant — where it changed; returns how many changed."""
    list_visits(root, research_project_id)  # an earlier file is moved to instants and to ids first
    refs = _refs(root, research_project_id)
    raw = _raw_visits(root, research_project_id)
    changed = 0
    for visit in raw:
        key = (_site(visit, refs).lower(), str(visit.get("when") or ""))
        if key in states and visit.get("state") != states[key]:
            visit["state"] = states[key]
            audit.touched(visit)
            changed += 1
    if changed:
        _write_raw_visits(root, research_project_id, raw)
    return changed


def closed_visits(root: Path, research_project_id: str) -> list[dict]:
    """The visits of a research project that left a camera (an Installation or a Revision) whose card a later visit has collected, and
    that have no deployment yet linked, newest first: {"visit", "end"} — the visit that left the camera and the next one at the same
    location, which collected the card (see closes_collection). The deployment is of the first: its card is the one that was collected.

    Raises:
        storage.StorageError: the research project id can't be a folder name.
    """
    by_location: dict[str, list[dict]] = {}
    for visit in list_visits(root, research_project_id):
        by_location.setdefault(str(visit.get("location_id", "")).lower(), []).append(visit)
    out = []
    for visits in by_location.values():
        visits.sort(key=lambda v: (str(v.get("date")), str(v.get("time"))))
        for start, end in zip(visits, visits[1:]):
            if start.get("deployment_id") or not closes_collection(end):
                continue
            if {"Installation", "Revision"} & set(start.get("actions") or []):
                out.append({"visit": start, "end": end})
    return sorted(out, key=lambda c: (str(c["visit"].get("date")), str(c["visit"].get("time"))), reverse=True)


def link_visit(root: Path, research_project_id: str, location_id: str, date: str, time: str, deployment_id: str) -> dict:
    """Records on a visit (found by its location, ignoring case, day and time) the deployment it closed.

    Raises:
        storage.StorageError: the visit isn't in the research project.
    """
    list_visits(root, research_project_id)  # an earlier file is moved to instants and to ids first
    raw = _raw_visits(root, research_project_id)
    refs = _refs(root, research_project_id)
    visit = next((v for v in raw if _site(v, refs).lower() == location_id.lower()
                  and (_told(v, refs).get("date"), _told(v, refs).get("time")) == (date, time)), None)
    if visit is None:
        raise storage.StorageError(f"There is no visit to {location_id} on {date} at {time} in {research_project_id}.")
    if visit.get("deployment_id") != deployment_id:
        visit["deployment_id"] = deployment_id
        audit.touched(visit)
    _write_raw_visits(root, research_project_id, raw)
    return _told(visit, refs)
