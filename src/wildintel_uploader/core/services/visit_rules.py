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

ACTIONS = ("Installation", "Revision", "Desinstallation", "Stolen")
# What each action asks: the camera, the card left, the photos collected, and how the camera was found — "required" or "optional".
_ASKED = {
    "Installation": {"camera": "required", "sd": "required"},
    "Revision": {"camera": "required", "sd": "optional", "photos": "required", "status": "optional"},
    "Desinstallation": {"camera": "required", "photos": "required", "status": "optional"},
    "Stolen": {"camera": "required"},
}
_LABELS = {"camera": "The camera", "sd": "The SD card left in the camera", "photos": "The photos on the card collected", "status": "The status of the camera"}
NOT_REVISED = ("not revised", "no revisada", "no revisado")


def _same(a, b) -> bool:
    return str(a or "").strip().lower() == str(b or "").strip().lower()


def _stamp(v: dict) -> str:
    return f"{v.get('date')}T{v.get('time')}"


def _seconds(v: dict) -> float:
    return datetime.fromisoformat(_stamp(v)).timestamp()


def _takes_away(v: dict) -> bool:
    return bool({"Desinstallation", "Stolen"} & set(v.get("actions") or []))


def _collects_card(v: dict) -> bool:
    return _takes_away(v) or "Revision" in (v.get("actions") or [])


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
    actions = visit.get("actions") or []
    value = {"camera": visit.get("camera_id"), "sd": visit.get("sd"), "photos": visit.get("num_photos"), "status": visit.get("status")}
    for field, how in asked(actions).items():
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


def availability_errors(kept: list[dict], visit: dict) -> dict[str, str]:
    """What stops a visit for where its camera or its card is: the camera put up while it is somewhere else, a card left in a camera while it is
    in another one — or the very one the visit collects. Nothing is said while the visit does not say which."""
    errors: dict[str, str] = {}
    when = _stamp(visit)
    site = str(visit["location_id"]).strip()
    actions = visit.get("actions") or []
    installs, revises = "Installation" in actions, "Revision" in actions
    collects = revises or "Desinstallation" in actions or "Stolen" in actions

    camera = visit.get("camera_id")
    if installs and camera:
        there = camera_at(kept, camera, when)
        # A visit that also revises may find the camera in the very site it puts it up at.
        if there and not (revises and _same(there["site"], site)):
            errors["camera"] = (
                f"Camera {camera} is already installed here (since {there['date']}): it has to be uninstalled first."
                if _same(there["site"], site) else
                f"Camera {camera} is installed at {there['site']} (since {there['date']}): it has to be uninstalled there before it is installed here."
            )
    card = str(visit.get("sd") or "").strip()
    if (installs or revises) and card:
        there = card_at(kept, card, when)
        if there and collects and _same(there["site"], site):
            errors["sd"] = f"SD card {card} is the one this visit collects (left on {there['date']}): the card left in the camera has to be another."
        elif there:
            errors["sd"] = f"SD card {card} is in the camera at {there['site']} (left on {there['date']}): it has to be collected before it is left here."
    return errors


def history_warnings(new: list[dict], kept: list[dict]) -> list[str]:
    """What is odd in the visits of a file, among them and with the ones already kept — each said once, with the session and the site. They are
    questions for the one who knows the field, not reasons to refuse a visit."""
    warnings: list[str] = []
    everything = sorted([*kept, *new], key=_stamp)

    def label(v: dict) -> str:
        return f"{v.get('session')} {v['location_id']}"

    # Per session and site: the same thing done twice.
    count: dict[tuple, int] = {}
    for v in new:
        for action in ("Installation", "Revision"):
            if action in v["actions"]:
                key = (v["session"], v["location_id"].lower(), action)
                count[key] = count.get(key, 0) + 1
    for (session, site, action), n in sorted(count.items()):
        if n > 1:
            hint = " (typo in the site number?)" if action == "Installation" else ""
            warnings.append(f"{session}: {site} has {n} \"{action}\" entries in the same session{hint}.")

    for v in new:
        before = [e for e in everything if e is not v]
        # Not after the visit of an earlier session.
        older = [e for e in before if _same(e["location_id"], v["location_id"]) and str(e.get("session", "")) < str(v.get("session", "")) and _stamp(e) >= _stamp(v)]
        if older:
            warnings.append(f"{label(v)}: the visit time {v['date']} {v['time']} is not after the visit of {older[0].get('session')} ({older[0]['date']} {older[0]['time']}).")
        if "Revision" in v["actions"] and v.get("num_photos") is not None and v["num_photos"] <= 0:
            warnings.append(f"{label(v)}: Revision with 0 photos; no deployment will be produced for it.")
        for message in required_errors(v).values():
            warnings.append(f"{label(v)}: {message}")
        # Where its camera and its card are, with what came before it — the visits of the file included.
        for message in availability_errors(before, v).values():
            warnings.append(f"{label(v)}: {message}")
        # An Installation while the card left at the visit before was not collected: nothing closes that deployment.
        if "Installation" in v["actions"] and "Revision" not in v["actions"]:
            last = max((e for e in before if _same(e["location_id"], v["location_id"]) and _stamp(e) < _stamp(v)
                        and str(e.get("status") or "").lower() not in NOT_REVISED), key=_stamp, default=None)
            if last and _leaves_card(last) and not _takes_away(last) and last.get("sd") and _seconds(v) - _seconds(last) >= 86400:
                warnings.append(
                    f"{label(v)}: Installation on {v['date']} while the card left there on {last['date']} ({last.get('session')} {' + '.join(last['actions'])}) "
                    "was not collected — no Revision or Desinstallation before it, so that card has no deployment. Check the field data.")

    # A camera or a card at more than one site in a session.
    for what, key in (("Camera", "camera_id"), ("Card", "sd")):
        by: dict[tuple, set] = {}
        for v in new:
            value = v.get(key)
            if value in (None, ""):
                continue
            by.setdefault((v["session"], str(value).strip().lower(), str(value).strip()), set()).add(v["location_id"])
        for (session, _, shown), sites in sorted(by.items()):
            if len(sites) > 1:
                warnings.append(f"{session}: {what.lower()} {shown} is at {len(sites)} sites ({', '.join(sorted(sites))}).")
    return list(dict.fromkeys(warnings))


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


def refusals(visit: dict, kept: list[dict], locations: list[dict]) -> list[str]:
    """Why a visit made by hand cannot be kept: its site is not a location of the research project, it is already kept (the same site, day and time),
    it lacks what its actions ask, or its camera or card are not where it says. Empty when it can be kept."""
    reasons = []
    if not any(_same(l.get("location_id"), visit["location_id"]) for l in locations):
        reasons.append(f"The site '{visit['location_id']}' is not a location of the research project.")
    if any(_same(v["location_id"], visit["location_id"]) and v.get("date") == visit["date"] and v.get("time") == visit["time"] for v in kept):
        reasons.append(f"There is already a visit to {visit['location_id']} on {visit['date']} at {visit['time']}.")
    reasons += required_errors(visit).values()
    reasons += availability_errors(kept, visit).values()
    return reasons
