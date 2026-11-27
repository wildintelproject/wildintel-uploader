"""What a visit is on its own, whatever reads it — plain Python: the rules one visit keeps to by itself, apart from the others (those are the rules of
`rules`). The adapter that reads a file of visits (infrastructure.records.VisitRecord) checks its shape and then asks these; a visit made any other
way is held to the same.

    >>> problems({"actions": ["Stolen"], "camera_status": "Working"})
    ['The camera of a Stolen visit is stolen: its status is Stolen.']
    >>> problems({"actions": ["Revision"], "card_status": "CardFull", "num_photos": 120})
    ['The images on a full card are not counted: leave their number out.']
    >>> camera_status_of({"actions": ["Stolen"]})
    'Stolen'
"""
from __future__ import annotations

from wildintel_uploader.modules.visits.domain.shapes import Visit

NOT_REVISED = ("not revised", "no revisada", "no revisado")


def camera_status_of(visit: Visit) -> str | None:
    """The status of its camera: a Stolen visit says it with its action — its camera is Stolen even when the status is left out."""
    return "Stolen" if "Stolen" in (visit.get("actions") or []) else visit.get("camera_status")


def problems(visit: Visit) -> list[str]:
    """What is wrong with a visit by itself, each said for the person — none if it can be. In the order they are told: the first is the one shown."""
    actions = set(visit.get("actions") or [])
    status = visit.get("camera_status")
    found: list[str] = []
    # a Stolen visit says it all with its action: the status of the camera is Stolen — and only there is the camera found stolen
    if "Stolen" in actions and status not in (None, "Stolen"):
        found.append("The camera of a Stolen visit is stolen: its status is Stolen.")
    elif "Stolen" not in actions and status == "Stolen":
        found.append("The status Stolen is for the visit that finds the camera stolen: its action is Stolen.")
    # the camera that is taken away goes with its card: nothing is left, unless another camera is put up
    if "Desinstallation" in actions and "Installation" not in actions and visit.get("sd"):
        found.append("No SD card is left where the camera is taken away: leave the card out.")
    # with the card full its photos are not counted: their number is not given
    if visit.get("card_status") == "CardFull" and visit.get("num_photos") is not None:
        found.append("The images on a full card are not counted: leave their number out.")
    # a visit that could not be made did nothing; any other did at least one thing
    if not actions and str(status or "").strip().lower() not in NOT_REVISED:
        found.append("A visit does at least one action — only a visit that could not be made (status Not revised) has none.")
    if visit.get("camera_height") is not None and visit.get("camera_depth") is not None:
        found.append("camera_height and camera_depth are mutually exclusive: only one should be set.")
    return found
