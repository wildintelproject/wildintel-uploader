"""Why the status of a location, a camera or an SD card can't be set by hand to what is asked — what the visits say of them: a camera that is out,
a card in a camera, a visit still to be made. Plain Python, over the visits as their rules read them."""
from __future__ import annotations

from wildintel_uploader.modules.visits.domain import rules


def site_status_refusal(visits: list[dict], unknown: list[dict], locations: list[dict], location: dict, wanted: str) -> str | None:
    """Why the status of a site cannot be set by hand to `wanted` — None when it can. The visits say what is there: a camera that is out, and the visits still to be made."""
    site = str(location.get("location_id", ""))
    camera = rules.camera_at_site(visits, site, "9999-12-31T23:59:59Z")
    if wanted == "active" and camera is None:
        return f"{site} is active when it has a camera: a visit puts it up (an Installation); the status cannot be set to active by hand."
    if wanted in ("ready", "planned", "archived") and camera is not None:
        return f"{site} has a camera out (put up in {camera.get('session')}): take it away with a visit — a Desinstallation, or a Stolen visit — before it is {wanted}."
    if wanted == "ready" and location.get("status") != "ready":
        return f"{site} is ready when a visit says Location start: its status cannot be set to ready by hand."
    if wanted in ("planned", "archived"):
        numbers = sorted({n for n in (rules._session_number(v.get("session")) for v in visits) if n is not None})
        pending = [f"R{n:04d}" for n in numbers if any(str(s).lower() == site.lower() for s in rules.revision_missing(n, visits, locations, "", unknown))]
        if pending:
            return f"{site} still has a visit to be made in {', '.join(pending)}: it cannot be {wanted} until the revision is finished."
    return None


def camera_status_refusal(camera: dict, wanted: str, visits: list[dict]) -> str | None:
    """Why the status of a camera cannot be set by hand to `wanted` — None when it can. A camera is active when a visit puts it up at a site (an Installation): it cannot be made so by
    hand, and it cannot leave the field — back to ready, to planned, or archived — while it is put up: a visit takes it away (a Desinstallation) or finds it stolen first."""
    name = str(camera.get("label") or camera.get("camera_id") or "")
    if wanted == "active":
        return f"The camera {name} is active when it is put up at a location: a visit does it (an Installation); its status cannot be set to active by hand."
    if wanted in ("ready", "planned", "archived"):
        for key in (camera.get("camera_id"), camera.get("label")):
            there = rules.camera_at(visits, str(key), "9999-12-31T23:59:59Z") if key else None
            if there:
                return f"The camera {name} is put up at {there['site']} (since {there['date']}): take it away with a visit — a Desinstallation, or a Stolen visit — before it is {wanted}."
    return None


def card_status_refusal(card: dict, wanted: str, visits: list[dict]) -> str | None:
    """Why the status of an SD card cannot be set by hand to `wanted` — None when it can. A card is active when a visit leaves it in a camera (an Installation, or a Revision that
    changes it): it cannot be made so by hand, and it cannot leave the field — back to ready, to planned, or archived — while it is in a camera: a visit collects it first."""
    name = str(card.get("label") or "")
    if wanted == "active":
        return f"The SD card {name} is active when it is in a camera: a visit leaves it there (an Installation, or a Revision); its status cannot be set to active by hand."
    if wanted in ("ready", "planned", "archived"):
        there = rules.card_at(visits, name, "9999-12-31T23:59:59Z") if name else None
        if there:
            return f"The SD card {name} is in the camera at {there['site']} (since {there['date']}): collect it with a visit — a Revision, a Desinstallation, or a Stolen visit — before it is {wanted}."
    return None
