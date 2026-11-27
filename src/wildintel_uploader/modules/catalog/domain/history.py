"""Why the states of the locations, the cameras and the SD cards change — said by whoever knows it, for what it writes:

    with because("the visit R0013 to DONA_01", day="2026-10-19"): …

What is written with no reason said is a change by hand. Plain Python: a context variable, read where the history is written — and what the history
says: the lines a change writes, and the lines the visits kept make, when a history is rebuilt from them.

A line says what changed (`kind`: `locations`, `cameras` or `sd_cards`, and the `name` of the one: the id of a location, the label of a camera or a
card), the status it had (`before`, None when it was just made) and the one it has (`after`), the instant it was written (`at`), the day it is of
(`day`: the day of the visit that did it, or the day it was changed) and why (`reason`): the visit that did it, or a person changing it in the
settings. What was kept before the history was has none: it is rebuilt from the visits kept; those lines are `reconstructed`."""
from __future__ import annotations

import contextlib
import contextvars
from typing import Callable, Iterator

from wildintel_uploader.modules.visits.domain import rules as visit_rules
from wildintel_uploader.shared import audit

KINDS = ("locations", "cameras", "sd_cards")
BY_HAND = "Changed by hand in the settings."
# The status of one before the first visit that changed it, in a history rebuilt from the visits: it is not known.
UNKNOWN = "unknown"


_why: contextvars.ContextVar[tuple[str, str | None, dict]] = contextvars.ContextVar("status_history_why", default=(BY_HAND, None, {}))


@contextlib.contextmanager
def because(reason: str, day: str | None = None, each: dict[tuple[str, str], tuple[str, str | None]] | None = None) -> Iterator[None]:
    """What is written inside is a change that has this reason — and is of this day, when it is given. `each` has a reason and a day of its own, for the ones it names: `{(kind, name in lower case): (reason, day)}`."""
    token = _why.set((reason, day, each or {}))
    try:
        yield
    finally:
        _why.reset(token)


def changed_lines(kind: str, before: list[dict], after: list[dict], name_of: Callable[[dict], str], match: Callable[[dict, list[dict]], dict | None],
                  at: str) -> list[dict]:
    """A line for each of `after` whose status is not the one it had in `before` (`match` finds it there; None when it is new, which says its status
    as first), with the reason said for it (`because`)."""
    if kind not in KINDS:
        raise ValueError(f"The history is kept for {', '.join(KINDS)}, not for {kind}.")
    reason, day, each = _why.get()
    lines = []
    for item in after:
        if audit.is_deleted(item) or not item.get("status"):
            continue
        old = match(item, before)
        was = old.get("status") if old is not None else None
        if old is not None and was == item["status"]:
            continue
        name = name_of(item)
        why, when = each.get((kind, name.lower()), (reason, day))
        lines.append({"kind": kind, "name": name, "before": was, "after": item["status"], "at": at, "day": when or item.get("status_date") or at[:10], "reason": why if old is not None else "Created."})
    return lines


def same(line: dict) -> tuple:
    """What tells a line from another, whenever it was written: the same change of the same one, the same day and for the same reason."""
    return (line.get("kind"), str(line.get("name", "")).lower(), line.get("after"), line.get("day"), line.get("reason"))


def in_order(lines: list[dict]) -> list[dict]:
    """The lines by the day they are of, those of the same day as they were; a line that brings one to its status of today goes after the others of it."""
    last: dict[tuple, str] = {}
    for l in lines:
        key = (l.get("kind"), str(l.get("name", "")).lower())
        last[key] = max(last.get(key, ""), str(l.get("day") or ""))
    return sorted(lines, key=lambda l: last[(l.get("kind"), str(l.get("name", "")).lower())] if l.get("to_today") else str(l.get("day") or ""))


def reconstructed_lines(locations: list[dict], equipment: dict[str, list[dict]], visits: list[dict], recorded: set[tuple], at: str) -> list[dict]:
    """The lines the visits kept make, oldest first, of the locations, the cameras and the SD cards a research project keeps (those not removed);
    `recorded` are those that have lines written as they happened (no last line brings them to today).

    What it cannot know: what was changed by hand, and the status before the first visit — its first line is *unknown → X*. When the visits end in
    a status that is not the one the record has now (it was changed by hand before the history was kept), a last line says so, of the day of its
    `status_date` — so the history ends in the status of today; one that has lines written as they happened is brought to it by them, and has none."""
    items: dict[tuple[str, str], dict] = {}          # (kind, name as it is matched) -> the record
    for l in locations:
        items[("locations", str(l["location_id"]).lower())] = {"name": str(l["location_id"]), "status": l.get("status"), "status_date": l.get("status_date")}
    for kind in ("cameras", "sd_cards"):
        for i in equipment.get(kind, []):
            one = {"name": str(i.get("label") or i.get("camera_id") or ""), "status": i.get("status"), "status_date": i.get("status_date")}
            # a camera is found by its label or by its id, as written (7b and 7B are two), as a visit finds it
            for n in {str(i.get("label") or "").strip()} | ({str(i.get("camera_id") or "").strip()} if kind == "cameras" else set()):
                if n:
                    items.setdefault((kind, n), one)

    def found(kind: str, name: str) -> dict | None:
        return items.get((kind, name.lower() if kind == "locations" else name.strip()))

    status: dict[tuple[str, str], str] = {}          # (kind, name) -> the status the visits give it so far
    out: list[dict] = []
    before: list[dict] = []
    for visit in sorted(audit.alive(visits), key=visit_rules._stamp):
        changes = visit_rules.entity_changes(visit, before)
        if "Archive" in (visit.get("actions") or []):
            changes.append({"kind": "locations", "name": str(visit["location_id"]), "status": "archived"})
        before.append(visit)
        for change in changes:
            one = found(change["kind"], change["name"])
            if one is None:
                continue
            key = (change["kind"], one["name"])
            was = status.get(key)
            # as the visits do it: what is archived is for good, and a site that is planned is not in the app yet
            if was == change["status"] or was == "archived" or (change["kind"] == "locations" and was not in (None, "pending", "ready", "active")):
                continue
            status[key] = change["status"]
            out.append({"kind": change["kind"], "name": one["name"], "before": was or UNKNOWN, "after": change["status"], "at": at, "day": visit.get("date") or at[:10],
                        "reason": f"The visit {visit.get('session')} to {visit['location_id']}.", "reconstructed": True})
    for (kind, name), worked_out in status.items():
        one = found(kind, name)
        now = one.get("status") if one else None
        if not now or now == worked_out or (kind, name.lower()) in recorded:
            continue
        out.append({"kind": kind, "name": name, "before": worked_out, "after": now, "at": at, "day": one.get("status_date") or at[:10],
                    "reason": f"The status is {now}, the visits say {worked_out}.", "reconstructed": True, "to_today": True})
    return out
