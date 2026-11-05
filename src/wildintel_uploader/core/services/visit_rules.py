"""The rules a visit to a camera trap has to follow — the one place they live, for the form (a visit that breaks them is refused) and for a CSV
file (the visits that break them are kept and warned of, as the field records are: what the field says is not changed, only questioned).

  * what is asked of a visit depends on what was done at it (an Installation needs the camera and the card it leaves, a Revision the photos
    it collected…) — `required_errors`;
  * where the cameras and the SD cards are, worked out from the visits before: a camera is put up at a site until a visit takes it away or
    finds it stolen, a card is in a camera until a visit collects it — `availability_errors`;
  * the history of a site: two Revisions or two Installations in one session, a visit that is not after the one before, a Revision with no
    photos, an Installation while the card left before was not collected, a camera or a card at two sites in a session — `history_warnings`;
  * a site that is not a location of the research project, told apart from one misnamed — `new_site`.
"""
from __future__ import annotations

from datetime import datetime
from math import asin, cos, radians, sin, sqrt

ACTIONS = ("Installation", "Revision", "Desinstallation", "Stolen", "Archive")
# What each action asks: the camera, the card left, the photos collected, and how the camera was found — "required" or "optional".
_ASKED = {
    "Installation": {"camera": "required", "sd": "required"},
    "Revision": {"camera": "required", "sd": "optional", "photos": "required", "status": "optional"},
    "Desinstallation": {"camera": "required", "photos": "required", "status": "optional"},
    "Stolen": {"camera": "required"},
    "Archive": {},  # the location is given up: nothing else is asked
}
_LABELS = {"camera": "The camera", "sd": "The SD card left in the camera", "photos": "The photos on the card collected", "status": "The status of the camera"}
NOT_REVISED = ("not revised", "no revisada", "no revisado")


def _same(a, b) -> bool:
    return str(a or "").strip().lower() == str(b or "").strip().lower()


def _stamp(v: dict) -> str:
    """When a visit was, to order visits: its instant (`when`, ISO 8601 UTC) — the wall clock of its location only when it has none."""
    return v.get("when") or f"{v.get('date')}T{v.get('time')}"


def _seconds(v: dict) -> float:
    return datetime.fromisoformat(_stamp(v)).timestamp()


def _takes_away(v: dict) -> bool:
    return bool({"Desinstallation", "Stolen"} & set(v.get("actions") or []))


def is_not_revised(v: dict) -> bool:
    """A visit that could not be made: its status says it was not revised, so nothing was looked at, collected or left."""
    return str(v.get("status") or "").lower() in NOT_REVISED


def _collects_card(v: dict) -> bool:
    return _takes_away(v) or ("Revision" in (v.get("actions") or []) and not is_not_revised(v))


def _leaves_card(v: dict) -> bool:
    return bool({"Installation", "Revision"} & set(v.get("actions") or []))


def asked(actions: list[str]) -> dict[str, str]:
    """Each field a visit may be asked, as strongly as any of its actions asks it."""
    out: dict[str, str] = {}
    for action in actions:
        for field, how in _ASKED.get(action, {}).items():
            if how == "required" or field not in out:
                out[field] = how
    return out


def required_errors(visit: dict) -> dict[str, str]:
    """What a visit lacks of what its actions ask of it, by field (camera, sd, photos, status) — nothing when it is complete."""
    errors = {}
    if is_not_revised(visit):
        return errors  # nothing was done at it: nothing is asked
    actions = visit.get("actions") or []
    value = {"camera": visit.get("camera_id"), "sd": visit.get("sd"), "photos": visit.get("num_photos"), "status": visit.get("status")}
    # With the card full the photos are not counted: the count is not asked (it may still be given).
    full_card = visit.get("card_batteries_ok") in ("CarFull", "CarFullSinPilas")
    for field, how in asked(actions).items():
        if field == "photos" and full_card:
            continue
        if how == "required" and (value[field] is None or str(value[field]).strip() == ""):
            by = " + ".join(a for a in actions if _ASKED.get(a, {}).get(field) == "required")
            errors[field] = f"{_LABELS[field]} is required for {by}."
    return errors


def camera_at(visits: list[dict], camera: str, when: str) -> dict | None:
    """The site a camera is put up at on a given moment — None when it is nowhere: never put up, uninstalled or stolen."""
    at = None
    for v in sorted((v for v in visits if _stamp(v) < when), key=_stamp):
        if not _same(v.get("camera_id"), camera):
            continue
        if _takes_away(v):
            at = None
        elif {"Installation", "Revision"} & set(v.get("actions") or []):
            at = {"site": v["location_id"], "date": v["date"]}
    return at


def camera_at_site(visits: list[dict], site: str, when: str) -> dict | None:
    """The camera that is put up at a site on a given moment — None when none is known: nothing was installed there, or it was taken away or stolen."""
    at = None
    for v in sorted((v for v in visits if _stamp(v) < when and _same(v.get("location_id"), site)), key=_stamp):
        if _takes_away(v):
            at = None
        elif {"Installation", "Revision"} & set(v.get("actions") or []) and v.get("camera_id"):
            at = {"camera": v["camera_id"], "date": v["date"]}
    return at


def card_at(visits: list[dict], label: str, when: str) -> dict | None:
    """The site whose camera holds a card on a given moment — None when it is in none: never left, or collected."""
    in_site: dict[str, dict] = {}
    for v in sorted((v for v in visits if _stamp(v) < when), key=_stamp):
        site = str(v["location_id"]).lower()
        if _collects_card(v):
            in_site.pop(site, None)
        if v.get("sd") and _leaves_card(v):
            in_site[site] = {"label": v["sd"], "date": v["date"], "site": v["location_id"]}
    return next(({"site": c["site"], "date": c["date"]} for c in in_site.values() if _same(c["label"], label)), None)


def card_at_site(visits: list[dict], site: str, when: str) -> dict | None:
    """The card the camera at a site holds on a given moment — None when it holds none: never left, or collected."""
    at = None
    for v in sorted((v for v in visits if _stamp(v) < when and _same(v.get("location_id"), site)), key=_stamp):
        if _collects_card(v):
            at = None
        if v.get("sd") and _leaves_card(v):
            at = {"label": v["sd"], "date": v["date"]}
    return at


def card_block(kept: list[dict], visit: dict, cards: list[dict] | None = None) -> str | None:
    """Why a visit cannot leave the card it says in the camera — None when it can, or when it leaves none. A card cannot be left when it is archived (from the
    day it was; with no day, for good), when it is in the camera of another site, when it is the one the visit collects, or when a visit of the same revision
    collected it."""
    card = str(visit.get("sd") or "").strip()
    actions = visit.get("actions") or []
    installs, revises = "Installation" in actions, "Revision" in actions
    if not (installs or revises) or not card:
        return None
    when = _stamp(visit)
    site = str(visit["location_id"]).strip()
    collects = revises or "Desinstallation" in actions or "Stolen" in actions
    settings = next((c for c in cards or [] if _same(c.get("label"), card)), None)
    if settings and settings.get("status") == "archived" and (not settings.get("status_date") or str(settings["status_date"]) <= str(visit.get("date"))):
        since = f" since {settings['status_date']}" if settings.get("status_date") else ""
        reason = f" ({settings['archive_reason']})" if settings.get("archive_reason") else ""
        return f"SD card {card} is not available{since}: it is archived{reason}."
    there = card_at(kept, card, when)
    if there and collects and _same(there["site"], site):
        return f"SD card {card} is the one this visit collects (left on {there['date']}): the card left in the camera has to be another."
    if there:
        return f"SD card {card} is in the camera at {there['site']} (left on {there['date']}): it has to be collected before it is left here."
    session = visit.get("session")
    if session:
        for w in kept:
            if w is not visit and w.get("session") == session and _collects_card(w):
                held = card_at_site(kept, w["location_id"], _stamp(w))
                if held and _same(held["label"], card):
                    return f"SD card {card} was collected at {w['location_id']} in this revision ({session}): it cannot be left again in the same revision."
    return None


def availability_errors(kept: list[dict], visit: dict, cards: list[dict] | None = None) -> dict[str, str]:
    """What stops a visit for where its camera or its card is: the camera put up while it is somewhere else, a card left in a camera while it is
    in another one — or the very one the visit collects. Nothing is said while the visit does not say which."""
    errors: dict[str, str] = {}
    when = _stamp(visit)
    site = str(visit["location_id"]).strip()
    actions = visit.get("actions") or []
    installs, revises = "Installation" in actions, "Revision" in actions
    collects = revises or "Desinstallation" in actions or "Stolen" in actions

    camera = visit.get("camera_id")
    # A visit that does not put a camera up — a Revision, a Desinstallation, a Stolen camera — is of the camera that is at the site.
    if camera and not installs and (collects or revises):
        there = camera_at_site(kept, site, when)
        if there and not _same(there["camera"], camera):
            what = " + ".join(x for x in actions if x in ACTIONS)
            errors["camera"] = f"The camera at {site} is {there['camera']} (since {there['date']}): a {what} is of that camera. If it was replaced, add an Installation to the visit."
    if installs and camera:
        there = camera_at(kept, camera, when)
        # A visit that also revises may find the camera in the very site it puts it up at.
        if there and not (revises and _same(there["site"], site)):
            errors["camera"] = (
                f"Camera {camera} is already installed here (since {there['date']}): it has to be uninstalled first."
                if _same(there["site"], site) else
                f"Camera {camera} is installed at {there['site']} (since {there['date']}): it has to be uninstalled there before it is installed here."
            )
    sd = card_block(kept, visit, cards)
    if sd:
        errors["sd"] = sd
    return errors


def history_warning_items(new: list[dict], kept: list[dict], cards: list[dict] | None = None) -> list[tuple[str, list[dict]]]:
    """What is odd in the visits of a file, among them and with the ones already kept — each said once, with the session and the site, and with the visits of the
    file that it is about (the ones that make it odd). They are questions for the one who knows the field, not reasons to refuse a visit."""
    items: dict[str, list[dict]] = {}
    everything = sorted([*kept, *new], key=_stamp)

    def say(message: str, *visits: dict) -> None:
        about = items.setdefault(message, [])
        about += [v for v in visits if not any(v is w for w in about)]

    def label(v: dict) -> str:
        return f"{v.get('session')} {v['location_id']}"

    # Per session and site: the same thing done twice.
    count: dict[tuple, list[dict]] = {}
    for v in new:
        for action in ("Installation", "Revision"):
            if action in v["actions"]:
                count.setdefault((v["session"], v["location_id"].lower(), action), []).append(v)
    for (session, site, action), of in sorted(count.items(), key=lambda kv: kv[0]):
        if len(of) > 1:
            hint = " (typo in the site number?)" if action == "Installation" else ""
            say(f"{session}: {site} has {len(of)} \"{action}\" entries in the same session{hint}.", *of)

    for v in new:
        before = [e for e in everything if e is not v]
        # Not after the visit of an earlier session.
        older = [e for e in before if _same(e["location_id"], v["location_id"]) and str(e.get("session", "")) < str(v.get("session", "")) and _stamp(e) >= _stamp(v)]
        if older:
            say(f"{label(v)}: the visit time {v['date']} {v['time']} is not after the visit of {older[0].get('session')} ({older[0]['date']} {older[0]['time']}).", v)
        if "Revision" in v["actions"] and v.get("num_photos") is not None and v["num_photos"] <= 0:
            say(f"{label(v)}: Revision with 0 photos; no deployment will be produced for it.", v)
        for message in required_errors(v).values():
            say(f"{label(v)}: {message}", v)
        # Where its camera and its card are, with what came before it — the visits of the file included.
        for message in availability_errors(before, v, cards).values():
            say(f"{label(v)}: {message}", v)
        # An Installation while the card left at the visit before was not collected: nothing closes that deployment.
        if "Installation" in v["actions"] and "Revision" not in v["actions"]:
            last = max((e for e in before if _same(e["location_id"], v["location_id"]) and _stamp(e) < _stamp(v)
                        and str(e.get("status") or "").lower() not in NOT_REVISED), key=_stamp, default=None)
            if last and _leaves_card(last) and not _takes_away(last) and last.get("sd") and _seconds(v) - _seconds(last) >= 86400:
                say(f"{label(v)}: Installation on {v['date']} while the card left there on {last['date']} ({last.get('session')} {' + '.join(last['actions'])}) "
                    "was not collected — no Revision or Desinstallation before it, so that card has no deployment. Check the field data.", v)

    # A camera or a card at more than one site in a session.
    for what, key in (("Camera", "camera_id"), ("Card", "sd")):
        by: dict[tuple, list[dict]] = {}
        for v in new:
            value = v.get(key)
            if value in (None, ""):
                continue
            by.setdefault((v["session"], str(value).strip().lower(), str(value).strip()), []).append(v)
        for (session, _, shown), of in sorted(by.items(), key=lambda kv: kv[0]):
            sites = {v["location_id"] for v in of}
            if len(sites) > 1:
                say(f"{session}: {what.lower()} {shown} is at {len(sites)} sites ({', '.join(sorted(sites))}).", *of)
    return list(items.items())


def history_warnings(new: list[dict], kept: list[dict], cards: list[dict] | None = None) -> list[str]:
    """What is odd in the visits of a file — see history_warning_items — as the messages only."""
    return [message for message, _ in history_warning_items(new, kept, cards)]


# The farthest the GPS of a note may be from its location before the site is doubted.
GPS_TOLERANCE_M = 1000


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """The distance between two points on the Earth, in metres (haversine)."""
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * 6371000 * asin(sqrt(a))


def one_apart(a: str, b: str) -> bool:
    """Whether two ids differ by one character — typed, missed or swapped: TATR_0004 / TATR_0005, but DONA_0022 / DONA_0022_B is not."""
    a, b = a.lower(), b.lower()
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        diff = [i for i in range(len(a)) if a[i] != b[i]]
        return len(diff) == 1 or (len(diff) == 2 and diff[1] == diff[0] + 1 and a[diff[0]] == b[diff[1]] and a[diff[1]] == b[diff[0]])
    short, long_ = (a, b) if len(a) < len(b) else (b, a)
    return any(long_[:i] + long_[i + 1:] == short for i in range(len(long_)))


def new_site(site: str, visits: list[dict], known: list[dict]) -> dict:
    """A site of a file that is not a location of the research project, with what helps tell a really new site from a misnamed one: the coordinates of
    its first visit, the nearest location kept and how far it is, and the ids one character apart from its own."""
    first = min(visits, key=_stamp)
    lat, lon = first.get("latitude"), first.get("longitude")
    nearest = None
    if lat is not None and lon is not None:
        distances = [(distance_m(lat, lon, float(l["latitude"]), float(l["longitude"])), l["location_id"])
                     for l in known if l.get("latitude") is not None and l.get("longitude") is not None]
        if distances:
            metres, location_id = min(distances)
            nearest = {"location_id": location_id, "distance_m": round(metres)}
    return {
        "site": site, "session": first.get("session"), "actions": first["actions"], "date": first["date"], "time": first["time"],
        "latitude": lat, "longitude": lon, "visits": len(visits), "nearest": nearest,
        "similar": sorted(str(l["location_id"]) for l in known if one_apart(site, str(l["location_id"]))),
    }


def refusals(visit: dict, kept: list[dict], locations: list[dict], cards: list[dict] | None = None) -> list[str]:
    """Why a visit made by hand cannot be kept: its site is not a location of the research project, it is already kept (the same site, day and time),
    it is the first to its site and not an Installation, it lacks what its actions ask, or its camera or card are not where it says. Empty when it can be kept."""
    reasons = []
    if not any(_same(l.get("location_id"), visit["location_id"]) for l in locations):
        reasons.append(f"The site '{visit['location_id']}' is not a location of the research project.")
    if any(_same(v["location_id"], visit["location_id"]) and v.get("date") == visit["date"] and v.get("time") == visit["time"] for v in kept):
        reasons.append(f"There is already a visit to {visit['location_id']} on {visit['date']} at {visit['time']}.")
    reasons += order_errors(visit, kept)
    # The first visit to a site puts the camera up: nothing else can be done where no camera is known to be.
    if not is_not_revised(visit) and not any(_same(v["location_id"], visit["location_id"]) and _stamp(v) < _stamp(visit) for v in kept) and list(visit.get("actions") or []) != ["Installation"]:
        reasons.append(f"The first visit to {visit['location_id']} can only be an Installation.")
    reasons += required_errors(visit).values()
    reasons += availability_errors(kept, visit, cards).values()
    reasons += archive_errors(visit, kept, next((l for l in locations if _same(l.get("location_id"), visit["location_id"])), None))
    reasons += [why for _, why in revision_gate([visit], kept, locations)]
    return reasons


def order_errors(visit: dict, kept: list[dict]) -> list[str]:
    """What stops a visit for when it was: a site has one visit in a revision, and a visit is after the last one to its site and after every visit of the revisions
    before its own — a revision starts when the one before it is finished (see revision_gate)."""
    errors: list[str] = []
    number = _session_number(visit.get("session"))
    site = str(visit["location_id"]).strip()
    if number is not None and any(_same(v["location_id"], site) and _session_number(v.get("session")) == number for v in kept):
        errors.append(f"{site} already has a visit in R{number:04d}: a revision is one visit to each site.")
    last = max((v for v in kept if _same(v["location_id"], site)), key=_stamp, default=None)
    if last is not None and _stamp(last) >= _stamp(visit):
        errors.append(f"The visit to {site} has to be after the last one, on {last['date']} at {last['time']} ({last.get('session')}).")
    if number is not None:
        before = [v for v in kept if (_session_number(v.get("session")) or number) < number]
        latest = max(before, key=_stamp, default=None)
        if latest is not None and _stamp(latest) >= _stamp(visit) and not (last is not None and latest is last):
            errors.append(f"R{number:04d} has to be after R{_session_number(latest.get('session')):04d}: its last visit was to {latest['location_id']} on {latest['date']} at {latest['time']}.")
    return errors


def _session_number(session) -> int | None:
    import re  # noqa: PLC0415
    m = re.search(r"\d+", str(session or ""))
    return int(m.group(0)) if m else None


def archive_errors(visit: dict, kept: list[dict], location: dict | None) -> list[str]:
    """What stops a visit for the state of its location: an archived location is archived for good, so nothing is done there after the day it was archived;
    and a visit that archives it leaves no camera there — it takes the one that is out away, or finds it stolen — and does not put one up."""
    errors: list[str] = []
    site = str(visit["location_id"]).strip()
    if location and location.get("status") == "archived" and (not location.get("status_date") or str(visit.get("date")) > str(location["status_date"])):
        errors.append(f"{site} is archived{' since ' + str(location['status_date']) if location.get('status_date') else ''}: no visit is kept for it after that.")
    actions = visit.get("actions") or []
    if "Archive" in actions:
        if "Installation" in actions:
            errors.append(f"A visit that archives {site} cannot put a camera up there.")
        there = camera_at_site(kept, site, _stamp(visit))
        if there and not _takes_away(visit):
            errors.append(f"The camera at {site} ({there['camera']}) is still there: take it away (Desinstallation) or say it was stolen in the visit that archives the location.")
    return errors


def not_visited_records(previous: int, visits: list[dict], locations: list[dict]) -> list[dict]:
    """The visits that finish revision `previous` as not visited: one for each location that is not archived when it starts and has no visit in it —
    status "Not revised", on the last day of the revision, with the camera that is at the site (none is asked of them)."""
    of = [v for v in visits if _session_number(v.get("session")) == previous]
    if not of:
        return []
    start, last = min(str(v["date"]) for v in of), max(str(v["date"]) for v in of)
    visited = {str(v["location_id"]).lower() for v in of}
    records = []
    for l in locations:
        site = str(l.get("location_id") or "")
        if not site or site.lower() in visited or (l.get("status") == "archived" and (not l.get("status_date") or str(l["status_date"]) <= start)):
            continue
        camera = camera_at_site(visits, site, f"{last}T23:59:59")
        records.append({"location_id": site, "session": f"R{previous:04d}", "date": last, "time": "23:59:00", "actions": [], "status": "Not revised",
                        "camera_id": camera["camera"] if camera else None, "comments": "Marked as not visited when the next revision was started."})
    return records


def revision_missing(number: int, visits: list[dict], locations: list[dict], day: str = "") -> list[str]:
    """The locations still to be visited in revision `number`: those that are not archived when it starts (the day of its first visit, or `day` if it has none)
    and have no visit in it. Empty when the revision is complete — closed."""
    of = [v for v in visits if _session_number(v.get("session")) == number]
    start = min((str(v["date"]) for v in of), default=day)
    expected = [str(l["location_id"]) for l in locations
                if l.get("location_id") and not (l.get("status") == "archived" and (not l.get("status_date") or str(l["status_date"]) <= start))]
    visited = {str(v["location_id"]).lower() for v in of}
    return sorted(s for s in expected if s.lower() not in visited)


def is_closed_revision(session: str | None, visits: list[dict], locations: list[dict]) -> bool:
    """Whether the revision has a visit — kept — and every location that is not archived has its visit in it: nothing new can be added to it."""
    number = _session_number(session)
    return number is not None and any(_session_number(v.get("session")) == number for v in visits) and not revision_missing(number, visits, locations)


def unfinished_revision(number: int, visits: list[dict], locations: list[dict], floor: int, day: str = "") -> str | None:
    """Why revision `number` cannot be started: the one before it is not finished. A revision is one visit to each of the locations that are not archived
    when it starts (the day of its first visit; an archived location with no date is archived for good); the first revision of the visits (`floor`) has none before it."""
    previous = number - 1
    if previous < floor:
        return None
    missing = revision_missing(previous, visits, locations, day)
    if not missing:
        return None
    return f"R{number:04d} cannot start: R{previous:04d} is not finished, {len(missing)} location(s) still to be visited in it: {', '.join(missing)}."


def revision_gate(new: list[dict], kept: list[dict], locations: list[dict]) -> list[tuple[dict, str]]:
    """The visits of `new` that cannot be kept because the revision before theirs is not finished — each with why. The revisions are taken in order, so a
    revision that is refused does not finish the one after it."""
    numbers = [n for n in (_session_number(v.get("session")) for v in [*kept, *new]) if n is not None]
    if not numbers:
        return []
    floor, accepted, refused = min(numbers), list(kept), []
    for number in sorted({n for n in (_session_number(v.get("session")) for v in new) if n is not None}):
        group = [v for v in new if _session_number(v.get("session")) == number]
        reason = unfinished_revision(number, accepted, locations, floor, min(str(v["date"]) for v in group))
        if reason:
            refused += [(v, reason) for v in group]
        else:
            accepted += group
    return refused


def session_jump_items(new: list[dict], kept: list[dict]) -> list[tuple[str, list[dict]]]:
    """A warning when the sessions of the visits of a file start after the one next to the last kept: a trip is missing — with the visits of the session that starts after the gap."""
    last = max((n for n in (_session_number(v.get("session")) for v in kept) if n is not None), default=None)
    first = min((n for n in (_session_number(v.get("session")) for v in new) if n is not None), default=None)
    if last is not None and first is not None and first > last + 1:
        return [(f"Session numbers jump from R{last:04d} to R{first:04d}.", [v for v in new if _session_number(v.get("session")) == first])]
    return []


def session_jump(new: list[dict], kept: list[dict]) -> list[str]:
    """A warning when the sessions of the visits of a file start after the one next to the last kept: a trip is missing."""
    return [message for message, _ in session_jump_items(new, kept)]


def history_notes(new: list[dict], kept: list[dict]) -> list[str]:
    """What is worth knowing of the visits of a file, without being wrong: the sites visited on the trip before and not on this one — their cameras are still out,
    their deployments stay open —, the visits where nothing was collected (status "Not revised") and the ones with no photo count."""
    notes: list[str] = []
    everything = [*kept, *new]
    for session in sorted({n for n in (_session_number(v.get("session")) for v in new) if n is not None}):
        here = {str(v["location_id"]).lower() for v in everything if _session_number(v.get("session")) == session}
        before = {str(v["location_id"]) for v in everything if _session_number(v.get("session")) == session - 1}
        missing = sorted(s for s in before if s.lower() not in here)
        if missing:
            notes.append(f"R{session:04d}: sites visited in R{session - 1:04d} and not on this trip, their cameras still out: {', '.join(missing)}.")
        current = [v for v in new if _session_number(v.get("session")) == session]
        skipped = sorted(v["location_id"] for v in current if str(v.get("status") or "").lower() in NOT_REVISED)
        if skipped:
            notes.append(f"R{session:04d}: {len(skipped)} visit(s) with status \"Not revised\", ignored (no card collected): {', '.join(skipped)}.")
        nocount = sorted(v["location_id"] for v in current if {"Revision", "Desinstallation"} & set(v["actions"]) and v.get("num_photos") is None
                         and v.get("card_batteries_ok") not in ("CarFull", "CarFullSinPilas") and str(v.get("status") or "").lower() not in NOT_REVISED)
        if nocount:
            notes.append(f"R{session:04d}: {len(nocount)} visit(s) without photo count (count forgotten), counted as the end of the collection: {', '.join(nocount)}.")
    return notes
