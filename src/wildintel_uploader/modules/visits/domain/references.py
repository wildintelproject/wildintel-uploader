"""What the visits point to — plain Python: a visit is kept pointing by id to its location, its camera, its SD card and the people who went (the
records of the catalog), and told with what they are called now; kept as an instant (`when`, ISO 8601 in UTC with a Z) and told with the day and
the time of the wall clock of its location. A visit that points to what the research project has not is kept as it was said, and is linked when
it has it."""
from __future__ import annotations

from typing import Any

from wildintel_uploader.modules.visits.domain import rules as visit_rules, wall_clock as visit_time
from wildintel_uploader.shared import identity, ids
from wildintel_uploader.modules.visits.domain.shapes import Camera, ClosedVisit, Location, SdCard, Trapper, UnknownVisit, Visit


class Refs:
    """What the visits of a research project point to, by id and by what it is called: its locations, cameras and SD cards, and the trappers — those that were deleted too."""

    def __init__(self, locations: list[Location], cameras: list[Camera], sd_cards: list[SdCard], trappers: list[Trapper]):
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

    def _add(self, kind: str, record: Any, labels: list) -> None:
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


def camera_model_of(record: Camera) -> str | None:
    """The model of a camera as Camtrap DP's cameraModel says it — the make and the model, make-model — from its record: the model alone when it has no make."""
    make, model = str(record.get("camera_make") or "").strip(), str(record.get("camera_model") or "").strip()
    return f"{make}-{model}" if make and model and not model.lower().startswith(make.lower()) else (model or None)


def _what_the_camera_is(record: Camera) -> dict:
    """What a visit tells of its camera from its record (#231): it only points to it (camera_ref), and what the camera is — its model as Camtrap DP says it and
    its serial number — is the record's, copied for whoever needs it (the deployment), never kept in the visit."""
    out: dict = {}
    if (model := camera_model_of(record)) is not None:
        out["camera_model"] = model
    if str(record.get("camera_id") or "").strip():
        out["camera_serial"] = str(record["camera_id"]).strip()
    return out


def location_of(locations: list[Location], location_id) -> Location | None:
    return next((l for l in locations if str(l.get("location_id", "")).lower() == str(location_id or "").lower()), None)


def site(visit: Visit, refs: Refs) -> str:
    """The site of a visit, as it is called — whether the visit is kept (by the id of its location) or told."""
    return str((refs.by_id["location"].get(visit.get("location_ref")) or {}).get("location_id") or visit.get("location_id") or "")


def linked(visit: Visit, refs: Refs) -> Visit:
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


def _link_camera(out: Visit, refs: Refs) -> None:
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


def unlinked(visit: Visit, refs: Refs) -> Visit:
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


def as_kept(visit: Visit, refs: Refs) -> Visit:
    """A visit as it is kept: the instant, ISO 8601 in UTC with a Z (`when`), and not the day and the time of the wall clock of its location; and what it points to said by id."""
    visit = two_fields(visit)
    if "status" in visit:   # kept before it was called camera_status
        visit = {("camera_status" if k == "status" else k): v for k, v in visit.items() if not (k == "status" and "camera_status" in visit)}
    if visit.get("when"):
        return linked({k: v for k, v in visit.items() if k not in ("date", "time")}, refs)
    if not (visit.get("date") and visit.get("time")):
        return linked(dict(visit), refs)  # no time to keep
    out = {k: v for k, v in visit.items() if k not in ("date", "time")}
    out["when"] = visit_time.to_when(visit["date"], visit["time"], location_of(refs.locations, site(visit, refs)))
    return linked(out, refs)


def two_fields(visit: Visit) -> Visit:
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


def as_told(visit: Visit, refs: Refs) -> Visit:
    """A visit as it is told: with the day and the time of the wall clock of its location, from its instant, beside it, and what it points to by what it is called. The card and
    the batteries are told as they are written now: a visit kept with SinPilas or CarFullSinPilas says NoBatteries or CarFullNoBatteries."""
    told = unlinked(visit, refs)
    if not told.get("when"):
        return told
    date, time = visit_time.to_wall(told["when"], location_of(refs.locations, told.get("location_id")))
    return {**told, "date": date, "time": time}


def with_the_camera_there(visits: list[Visit]) -> list[Visit]:
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


def closed(visits: list[Visit]) -> list[ClosedVisit]:
    """The visits that left a camera (an Installation or a Revision) whose card a later visit collected, and that have no deployment linked yet,
    newest first: {"visit", "end"} — the visit that left the camera and the next one at the same location, which collected the card. `visits` are
    told."""
    by_location: dict[str, list[Visit]] = {}
    for visit in visits:
        by_location.setdefault(str(visit.get("location_id", "")).lower(), []).append(visit)
    out = []
    for group in by_location.values():
        group.sort(key=lambda v: (str(v.get("date")), str(v.get("time"))))
        for start, end in zip(group, group[1:]):
            if start.get("deployment_id") or not visit_rules.closes_collection(end):
                continue
            if {"Installation", "Revision"} & set(start.get("actions") or []):
                out.append({"visit": start, "end": end})
    return sorted(out, key=lambda c: (str(c["visit"].get("date")), str(c["visit"].get("time"))), reverse=True)


def unknown_told(stored: list[UnknownVisit], locations: list[Location]) -> list[UnknownVisit]:
    """The unknown visits as they are told — {"location_id", "session"} —, from how they are kept (pointing to their location by id)."""
    where = {loc["id"]: loc for loc in locations if loc.get("id")}
    out = []
    for u in stored:
        site_of = (where.get(u.get("location_ref")) or {}).get("location_id") or u.get("location_id")
        if site_of and u.get("session"):
            out.append({"location_id": site_of, "session": u["session"]})
    return out


def unknown_kept(unknown: list[UnknownVisit], locations: list[Location]) -> list[UnknownVisit]:
    """The unknown visits as they are kept — each pointing to its location by id, when the research project has it."""
    where = {str(loc.get("location_id", "")).lower(): loc for loc in locations}
    out = []
    for u in unknown:
        place = where.get(str(u["location_id"]).lower())
        out.append({"location_ref": place["id"], "session": u["session"]} if place and place.get("id") else {"location_id": u["location_id"], "session": u["session"]})
    return out


def read_kept(raw: list[Visit], refs: Refs, project: str) -> tuple[list[Visit], list[Visit]]:
    """The visits of a research project as they are kept, read: each moved to instants and to ids when it was kept otherwise (an earlier
    version), with an id of its own when it was kept before there were ids — the same one whenever it is read —; and the same visits told with
    the names of what they point to, the camera that is at each site said. (kept, told): what to write back when it changed, and what to show."""
    kept = []
    for visit in raw:
        try:
            one = as_kept(visit, refs)
        except (KeyError, ValueError, TypeError):
            one = visit   # not a visit it can read the time of: left as it is
        if not one.get("id"):   # kept before the ids existed: the same one whenever it is read
            one = {**one, "id": ids.legacy_id("visit", f"{site(one, refs)}|{one.get('when') or ''}", project)}
        kept.append(one)
    return kept, with_the_camera_there([as_told(v, refs) for v in kept])

