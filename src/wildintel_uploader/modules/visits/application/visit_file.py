"""Reading a file of visits into the visits that can be kept — checked against the rules of a visit as the form checks one by hand, with what is
wrong with the rest, what is odd in what is kept, and what the file creates —, writing the visits as a file the import reads back, and the
columns of a file. The rules are the domain's (domain.visit_file, domain.rules); the text of the file, its cells and its records are what the
file (VisitFile) says."""
from __future__ import annotations

import re

from wildintel_uploader.modules.visits.domain import created
from wildintel_uploader.modules.visits.domain import rules as visit_rules
from wildintel_uploader.modules.visits.domain import visit_file as rules
from wildintel_uploader.modules.visits.domain import wall_clock as visit_time
from wildintel_uploader.modules.visits.domain.ports import Visit, VisitFile


class VisitFiles:
    """The files of visits, over the file the app reads and writes them as (a CSV)."""

    def __init__(self, file: VisitFile) -> None:
        self._file = file

    def parse(self, text: str, locations: list[dict], kept: list[Visit], mapping: dict | None, options: dict) -> dict:
        return parse_visits(self._file, text, locations, kept, mapping, options)

    def export(self, visits: list[Visit]) -> str:
        return self._file.write(rules.export_rows(visits))

    def columns(self, text: str) -> dict:
        """The columns of a file, a few of its rows, the column that most likely gives each field of a visit, and the fields a file can give."""
        table = self._file.table(text)
        return {"columns": table[0], "sample": table[1:4], "mapping": rules.suggest(table[0]), "fields": rules.field_list()}

    def normalized(self, visit: Visit) -> Visit:
        return self._file.normalized(visit)


def parse_visits(file: VisitFile, text: str, locations: list[dict], kept: list[dict], mapping: dict[str, str] | None = None, options: dict | None = None) -> dict:
    """The visits in the CSV `text` that can be kept, and what is wrong with the rest.

    `mapping` ({field: column}) says the column that gives each field of a visit — see domain.visit_file. `file` reads the text, the cells and the records.
    A site must be a location of the research project (found ignoring case); its coordinates
    are the visit's unless the row has its own. A row without a session gets the next of its location, counted from the visits already
    kept. A visit already kept — the same location, day and time — is left as it is, and counted as skipped.

    A site that is not a location is not a problem to throw the rows away for: it may be a site that is really new, or one misnamed in the field. Its
    visits are held and the site comes back in "new_sites" with what tells the two apart (the coordinates of its first visit, the nearest location and
    how far, the ids one character apart — see visit_rules.new_site), to add it as a location or to correct the file. What is odd in the visits that are
    kept — what their actions ask and they lack, a camera or a card where it cannot be, two Revisions in a session… — comes back in "warnings": the
    visits are kept as the field wrote them and questioned, as the field records are.

    `options` are the settings of the field records: "time_source" ("created_at", or "hour" to read the date and the hour typed) and "cards" (the SD cards of the settings, to tell which are archived). A row whose session and site are those of a visit already
    kept is that visit: left as it is, and counted as skipped.

    Returns {"visits": [...], "problems": [{"row", "message"}], "skipped": int, "new_sites": [...], "warnings": [str], "notes": [str]} — the rows
    numbered as in the file, the header being 1. "notes" are what is worth knowing but not wrong: the sites of the trip before not visited on this one (their cameras
    are still out), visits where nothing was collected, visits with no photo count.

    Raises:
        VisitsCsvError: the file is empty or lacks a required column.
    """
    options = options or {}
    time_source = options.get("time_source") or "created_at"
    create = {entity: bool(on) for entity, on in (options.get("create") or {}).items() if entity in rules.CREATABLE}
    _, rows = rules.rows_of(file.table(text), mapping, options.get("defaults"), create)
    known = {str(l.get("location_id", "")).lower(): l for l in locations}
    # What a row creates when its location, camera or SD card does not exist and it is asked to: {row: {"locations": [...], "cameras": [...], "sd_cards": [...]}}, and the
    # locations made from the first row that gave each site (the other rows of it are read in its timezone).
    cameras_known = {str(c.get(k) or "") for c in options.get("cameras") or [] if c.get("status") != "planned" for k in ("camera_id", "label")} - {""}   # as written: 7b and 7B are two
    # the record of each camera by what a row may call it — its label or its serial number (#231): a row is resolved to it once, and points to it by its id
    camera_by: dict[str, dict] = {}
    for c in options.get("cameras") or []:
        if c.get("status") != "planned":
            for k in ("label", "camera_id"):
                if str(c.get(k) or "").strip():
                    camera_by.setdefault(str(c[k]).strip(), c)
    completed: dict[str, dict] = {}   # what the rows add to records that lacked it: {label: {field: value}}
    camera_warnings: list[tuple[int, str]] = []
    cards_known = {str(c.get("label") or "") for c in options.get("cards") or [] if c.get("status") != "planned"} - {""}
    made_by_row: dict[int, dict[str, list[dict]]] = {}
    new_locations: dict[str, dict] = {}
    already = {(str(v.get("location_id", "")).lower(), v.get("date"), v.get("time")) for v in kept}
    problems: list[dict] = []
    parsed: list[tuple[int, dict]] = []
    skipped = 0
    held: dict[str, list[dict]] = {}  # the visits to sites that are not locations of the research project, by site
    row_warnings: list[tuple[int, str]] = []  # what is odd in a row by itself: its row, and what
    took_location_coordinates: list[int] = []  # the rows that have no coordinates of the visit: they take those of their location
    from_location = options.get("coordinates_from_location", True)   # a row with none takes its location's — unless the import is asked not to
    # A revision is one visit to each site: the session and the site of a visit already kept are taken, whatever its camera or its actions
    in_file: dict[tuple[str, str], int] = {}
    kept_by_site = visit_rules.History(kept)   # the visits kept, found by site: a row asks of its site's, not of all of them
    same_visit = {(str(v.get("session") or "").upper(), str(v.get("location_id", "")).lower()) for v in kept if v.get("session")}

    # What became of each row of the file: {row: {"row", "site", "result", "message"}} — result is ok, problem, already_kept, new_site or ignored.
    report: dict[int, dict] = {}

    def problem(n: int, message: str, code: str = "other", waits: bool = False) -> None:
        """A row that cannot be added, and why. `waits`: it has no error of its own — it only waits for the revision before, which a row with an error
        left unfinished (#206)."""
        problems.append({"row": n, "message": message, **({"waits": True} if waits else {})})
        report[n] = {**report.get(n, {"row": n, "site": ""}), "result": "problem", "label": rules.error_label(code), "message": message}

    by_new_site: list[dict] = []   # the locations that a visit that says New site made
    for n, row in enumerate(rows, start=2):
        found = re.search(r"\d+", row.get("session", ""))
        report[n] = {"row": n, "site": row.get("location_id", ""), "session": f"R{int(found.group(0)):04d}" if found else "", "actions": row.get("actions", ""), "result": "ok", "label": "", "message": "", "data": dict(row)}
        site = row.get("location_id", "")
        location = known.get(site.lower()) or new_locations.get(site.lower())
        unknown = location is None
        made: dict[str, list[dict]] = {"locations": [], "cameras": [], "sd_cards": []}
        try:
            # a visit that says New site makes its site — the form lets a site be made on the spot —, when the file is asked to (the one of Epicollect5 is), with no need of the switch
            says_new_site = bool(options.get("new_site_makes_location")) and str(row.get("camera_status") or "").strip().lower() == "new site"
            if unknown and (create.get("locations") or says_new_site):
                location = file.location(rules.location_fields(site, row))
                made["locations"].append(location)
                unknown = False
                if says_new_site and not create.get("locations"):
                    by_new_site.append(location)
        except rules.RowError as exc:
            problem(n, str(exc), exc.code)
            continue
        if unknown:
            location = {}  # held with its site apart: the time is read as UTC, as nothing says better
        try:
            date, time = rules.when(row, location, time_source)
            report[n] |= {"date": date, "time": time[:5]}
            # what the cells say of the visit — each one read as its field takes it, or refused with the code of what is wrong
            cells = file.cells(row)
            # the coordinates of a visit are required, but a file need not have them: a row that has none takes those of its location (said once, in a note) unless the import is asked not to. One of the two is not enough.
            if cells.get("latitude") is None and cells.get("longitude") is None:
                if not from_location:
                    raise rules.RowError("coordinates_missing", "The row needs the coordinates of the visit: a latitude and a longitude.")
                if location.get("latitude") is None or location.get("longitude") is None:
                    raise rules.RowError("coordinates_missing", "The row has no coordinates of the visit (a latitude and a longitude), and its location has none to take instead.")
                cells["latitude"], cells["longitude"] = float(location["latitude"]), float(location["longitude"])
                took_location_coordinates.append(n)
            elif cells.get("latitude") is None or cells.get("longitude") is None:
                raise rules.RowError("coordinates_missing", "The row has only one of the coordinates of the visit: it needs a latitude and a longitude" + (", or none (then those of its location are used)." if from_location else "."))
            actions = cells.get("actions", [])
            # a camera and an SD card are what their cell says, stripped; the ones that exist are found ignoring the case
            named = cells.get("camera_id") or cells.get("camera_serial")
            record_of = camera_by.get(named or "") or camera_by.get(cells.get("camera_serial") or "")
            if record_of is not None:
                _complete_camera(record_of, cells, completed, camera_warnings, n)
            elif create.get("cameras") and named and named not in cameras_known:
                made["cameras"].append(created.new_camera(named, cells.get("camera_serial") or None, cells.get("camera_make") or None, row.get("camera_model") or None))
            card = cells.get("sd")
            if create.get("sd_cards") and card and card not in cards_known:
                made["sd_cards"].append(created.new_card(card, row.get("sd_brand") or None, row.get("sd_capacity") or None))
            # an id that is out of the ordinary is said once for its card, in the rows it is in; the card that is kept already was accepted as it is
            if card and card not in cards_known and visit_rules.unusual_card_id(card):
                row_warnings.append((n, visit_rules.unusual_card_message(card)))
            data = {field: value for field, value in cells.items() if field not in ("actions", "camera_make")}
            if record_of is not None:   # told by its label, pointing to its record; what the camera is, is the record's (#231)
                data["camera_id"] = str(record_of.get("label") or record_of.get("camera_id"))
                if record_of.get("id"):
                    data["camera_ref"] = record_of["id"]
                data.pop("camera_serial", None)
            elif named:
                data["camera_id"] = named
            if "card_batteries_ok" in data:   # one column for both, as it was: the batteries and the card each in its own field
                battery, card = visit_rules.split_card_batteries(data.pop("card_batteries_ok"))
                data.setdefault("battery_status", battery)
                data.setdefault("card_status", card)
            # the GPS of the note is compared with the location's, to check that the site is the right one
            if data.get("latitude") is not None and data.get("longitude") is not None and location.get("latitude") is not None and location.get("longitude") is not None:
                gap = visit_rules.distance_m(data["latitude"], data["longitude"], float(location["latitude"]), float(location["longitude"]))
                if gap > visit_rules.GPS_TOLERANCE_M:
                    row_warnings.append((n, f"Row {n} ({site}): the GPS of the note is {round(gap)} m from the location; check that the location is the right one."))
            visit = {"location_id": location.get("location_id", site), "date": date, "time": time, "actions": actions, **data}
            visit.setdefault("session", "R0000")  # worked out below, when the order of the visits is known
            record = file.record(visit)
            record["when"] = visit_time.to_when(record["date"], record["time"], location)
            record = visit_rules.with_site_start(record, kept_by_site, None)
            report[n]["actions"] = " + ".join(record["actions"])
        except rules.RowError as exc:
            problem(n, str(exc), exc.code)
            continue
        except ValueError as exc:
            problem(n, str(exc))
            continue
        if unknown:
            held.setdefault(site, []).append(record)
            report[n] |= {"result": "new_site", "label": "Not a location of the research project", "message": f"{site} is not a location of the research project: the visit is held until the location is added or the file corrected."}
            continue
        again = (str(record["session"]).upper(), record["location_id"].lower())
        # two visits are the same when they are of the same revision and the same site, whatever the day: the day is not part of it. Only a row with no revision —
        # it gets the next of its site, so there is nothing to compare — is told by the day and the time it says.
        by_time = (record["location_id"].lower(), record["date"], record["time"]) in already
        if ("session" in row and again in same_visit) or ("session" not in row and by_time):
            skipped += 1
            closed = visit_rules.is_closed_revision(record["session"], kept, locations)
            report[n] |= {"result": "already_kept", "label": "Already kept", "message": (f"A visit to {record['location_id']} on {record['date']} at {record['time']} is already kept: it is not imported again." if "session" not in row
                                                              else f"The {record['session']} visit of {record['location_id']} is already kept: it is not imported again."
                                                                 + (f" {record['session']} is closed — every location has its visit — so nothing new can be imported in it." if closed else ""))}
            continue
        if visit_rules.is_closed_revision(record["session"], kept, locations):
            problem(n, f"{record['session']} is closed: every location has its visit in it, so nothing new can be imported in it.", "revision_closed")
            continue
        # the key of a visit is its site and its revision: a site is visited once in a revision, whatever the day
        if "session" in row and again in in_file:
            problem(n, f"{record['location_id']} has already a visit in {record['session']} in row {in_file[again]} of the file: a revision is one visit to each location.", "visit_repeated")
            continue
        if "session" in row:
            in_file[again] = n
        already.add((record["location_id"].lower(), record["date"], record["time"]))
        parsed.append((n, record | {"_given": "session" in row}))
        if made["locations"]:
            new_locations[site.lower()] = made["locations"][0]
        made_by_row[n] = made

    row_of = {id(r): n for n, r in parsed}
    count: dict[str, int] = {}
    for loc in {r["location_id"].lower() for _, r in parsed}:
        count[loc] = sum(1 for v in kept if str(v.get("location_id", "")).lower() == loc)
    visits = []
    for _, record in sorted(parsed, key=lambda p: (p[1]["date"], p[1]["time"])):
        given = record.pop("_given")
        loc = record["location_id"].lower()
        # a visit that does not put a camera up is of the one at the site: an inspection or a removal does not say which — and it is not told here: it is in the visit before
        if not given:
            record["session"] = f"R{count[loc] + 1:04d}"
        count[loc] += 1
        visits.append(record)
    # The first camera put up at a pending site starts it.
    seen_sites = {str(v.get("location_id", "")).lower() for v in kept}
    by_site = {str(l.get("location_id", "")).lower(): l for l in [*locations, *new_locations.values()]}
    for record in sorted(visits, key=visit_rules._stamp):
        site = record["location_id"].lower()
        if site not in seen_sites:
            record["actions"] = visit_rules.with_site_start(record, [], by_site.get(site))["actions"]
            report[row_of[id(record)]]["actions"] = " + ".join(record["actions"])
            seen_sites.add(site)
    # every visit of a revision is after those of the revisions before it and before those of the revisions after it, whichever the site
    disordered = visit_rules.revision_order_conflicts(visits, kept)
    for visit, why in disordered:
        problem(row_of[id(visit)], why, "revision_order")
    out_of_order = {id(r) for r, _ in disordered}
    visits = [v for v in visits if id(v) not in out_of_order]
    # a visit of a file follows the rules of a visit by hand (see visit_rules.refusals): the visits are taken in the order of their instants, each against the ones kept and
    # the ones of the file before it that were kept, and the one that breaks them is refused with the row it comes from. What cannot be checked is not: the revisions a site
    # lacks before its first visit are unknown (nothing is known of them — no day, no camera, no card), so a first visit to a site after R0001 may be any.
    # A revision is imported only when the one before it is known — it has a visit, kept or in the file — and closed: only R0001 has none before it. So an import
    # makes no unknown visit: what a revision lacks is a visit to be made, marked as not visited when the revision is closed.
    unknown_kept = options.get("unknown") or []
    unknown: list[dict] = []
    all_locations = [*locations, *new_locations.values()]
    floor = 1
    close_after = options.get("close_after") or None
    close_notes: list[str] = []
    accepted, gate, closing = visit_rules.History(kept), {}, []
    unknown_kept_keys = {(str(u["location_id"]).lower(), str(u["session"]).upper()) for u in unknown_kept}

    def fills_unknown(v: dict) -> bool:
        """Whether the visit takes the place of an unknown one of the visits kept: its site has none in its revision, that is unknown."""
        return (v["location_id"].lower(), str(v["session"]).upper()) in unknown_kept_keys

    # the visits that fill an unknown one come last: each is checked with the visits after it that it touches, and those need the other visits of its revision to be there
    # at the same instant, a visit that takes a camera away is taken first: the camera it takes can be put up at another site at that same minute
    for visit in sorted(visits, key=lambda v: (fills_unknown(v), *visit_rules.by_time_takings_first(v))):
        number = visit_rules._session_number(visit.get("session"))
        fills = fills_unknown(visit)
        if number is not None and number not in gate and not fills:
            # a revision starts when the one before it is finished — said once for the revision, with the visits that were kept before it
            day = min(str(v["date"]) for v in visits if visit_rules._session_number(v.get("session")) == number)
            # a site given up by a visit taken so far (an Archive) is out of use from then on, as if the revisions had come in one file each: archiving is only kept when saving
            in_use = rules.archived_by(all_locations, accepted)
            before = [v for v in accepted if visit_rules._session_number(v.get("session")) == number - 1]
            if number > 1 and not before:
                gate[number] = visit_rules._reason("revision_without_previous", f"R{number:04d} cannot start: R{number - 1:04d} has no visit. Import the visits of R{number - 1:04d} first.")
            closes = None
            # the day to close on matters only to a revision that has locations still to be visited: one that is finished is left as it is
            if number > 1 and before and options.get("close_revisions") and close_after and visit_rules.revision_missing(number - 1, accepted, in_use, day, [*unknown_kept, *unknown], visits):
                # the day it is closed on: so long after its last visit, or so long before the first visit of the revision after it
                last = max(str(v["date"]) for v in before)
                amount, unit = int(close_after["amount"]), str(close_after["unit"])
                if close_after.get("anchor") == "before_next":
                    close_day, lasted = visit_rules.shifted(day, -amount, unit), f"{amount} {unit} before the first visit of R{number:04d} ({day})"
                else:
                    close_day, lasted = visit_rules.shifted(last, amount, unit), f"{amount} {unit} after its last visit ({last})"
                # it cannot end before its last visit, nor after the revision after it starts: the day is taken to the nearest one it can be
                if close_day < last:
                    close_notes.append(f"R{number - 1:04d} would be closed on {close_day}, {lasted}, before its last visit: it is closed on {last}, the day of its last visit.")
                    close_day = last
                elif close_day >= day:
                    # it reaches the revision after it: the day before the first visit of that one — never before its own last visit
                    before_next = max(last, visit_rules.shifted(day, -1, "days"))
                    close_notes.append(f"R{number - 1:04d} would be closed on {close_day}, {lasted}, when R{number:04d} has started ({day}): it is closed on {before_next}, the day before.")
                    close_day = before_next
                # on the day of the first visit after it, just before that visit
                earliest = min(str(v.get("time") or "00:00:00") for v in visits if visit_rules._session_number(v.get("session")) == number and str(v["date"]) == day) if close_day == day else None
                closes = (close_day, rules.minute_before(earliest) if earliest else "23:59:00")
            if number not in gate and options.get("close_revisions"):
                # the revision before is closed as the form does when asked: its locations still planned are marked as not visited
                marks = visit_rules.not_visited_records(number - 1, [*accepted, *(v for v in visits if visit_rules.SITE_START in (v.get('actions') or []))], in_use, [*unknown_kept, *unknown], closes=closes)
                for mark in marks:
                    location = next((l for l in all_locations if str(l.get("location_id", "")).lower() == mark["location_id"].lower()), None)
                    mark["when"] = visit_time.to_when(mark["date"], mark["time"], location)
                    mark["comments"] = "Marked as not visited when the revision after it was added from a file."
                accepted.extend(marks)
                closing.extend(marks)
            if number not in gate:
                gate[number] = visit_rules.unfinished_revision(number, accepted, in_use, floor, day, [*unknown_kept, *unknown], visits)
        n = row_of[id(visit)]
        reasons = [gate[number]] if number is not None and not fills and gate.get(number) else []
        # a visit that takes the place of an unknown one is put where its instant says, among the visits kept (as in the form)
        if fills:
            reasons += visit_rules.edit_errors(None, visit, accepted, all_locations, options.get("cards"), [*unknown_kept, *unknown])
        else:
            reasons += visit_rules.refusals(visit, accepted, all_locations, options.get("cards"), [*unknown_kept, *unknown], gate=False, first_may_be_any=True, photos_optional=bool(options.get("photos_not_counted")))
        # what the visit says that is not an entity (a camera, a card, a trapper) is refused, as in the form, unless the import creates it
        camera, card = str(visit.get("camera_id") or ""), str(visit.get("sd") or "")
        check = options.get("check_entities", True)
        if check and camera and options.get("cameras") is not None and camera not in cameras_known and not create.get("cameras"):
            reasons.append(visit_rules._reason("camera_unknown", f"The camera {visit['camera_id']} is not one of the cameras of the research project."))
        if check and card and options.get("cards") is not None and card not in cards_known and not create.get("sd_cards"):
            reasons.append(visit_rules._reason("card_unknown", f"The SD card {visit['sd']} is not one of the SD cards of the research project."))
        if check and options.get("trappers") is not None and not create.get("trappers"):
            known_trappers = {str(t) for t in options["trappers"]}   # as written: two people that differ only in case are two
            reasons += [visit_rules._reason("trapper_unknown", f"{t} is not one of the trappers.") for t in (x.strip() for x in str(visit.get("trappers") or "").split(",")) if t and t not in known_trappers]
        if reasons:
            # the kind of error is that of the first rule it breaks; every reason is told
            own = [r for r in reasons if getattr(r, "code", None) not in rules.WAITING]
            problem(n, " ".join(dict.fromkeys(reasons)), getattr((own or reasons)[0], "code", "visit_refused"), waits=not own)
        else:
            accepted.append(visit)
    refused_ids = {id(v) for v in visits} - {id(v) for v in accepted}
    visits = [v for v in visits if id(v) not in refused_ids]
    new_sites = [visit_rules.new_site(site, records, locations) for site, records in sorted(held.items())]
    # what is odd and still kept, said once and told in the rows it is about: the visits that make it odd are rows of the file
    said: list[tuple[str, list[int]]] = [(message, [n]) for n, message in [*row_warnings, *camera_warnings]]
    for message, about in [*visit_rules.session_jump_items(visits, kept), *visit_rules.history_warning_items(visits, kept, options.get("cards"), [*unknown_kept, *unknown], bool(options.get("photos_not_counted")))]:
        said.append((message, sorted({row_of[id(v)] for v in about if id(v) in row_of})))
    warnings = list(dict.fromkeys(message for message, _ in said))
    notes = visit_rules.history_notes(visits, kept)
    if options.get("photos_not_counted"):
        uncounted = [v for v in visits if {"Revision", "Desinstallation"} & set(v["actions"]) and v.get("num_photos") is None and v.get("card_status") != "CardFull" and str(v.get("camera_status") or "").lower() not in visit_rules.NOT_REVISED]
        if uncounted:
            notes.append(f"{len(uncounted)} {'visit has' if len(uncounted) == 1 else 'visits have'} no count of the images on the card, kept as the file says: the images of their deployments are not checked against a count.")
    took = sorted(n for n in took_location_coordinates if n in row_of.values() and any(row_of.get(id(v)) == n for v in visits))
    if took:
        shown = ", ".join(str(n) for n in took[:8]) + (f" and {len(took) - 8} more" if len(took) > 8 else "")
        notes.append(f"{len(took)} {'row has' if len(took) == 1 else 'rows have'} no coordinates of the visit (row {shown}): the coordinates of their location are used.")
    made_here = {l["location_id"].lower() for l in create_out_locations(new_locations, visits)}
    for location in by_new_site:
        if location["location_id"].lower() in made_here:
            notes.append(f"The location {location['location_id']} is made because its visit says New site: its place is the one of the visit and its timezone is {location['timezone']} — "
                         f"change it in the settings if it is not that one.")
    notes += close_notes
    closed = [m for m in closing if any(visit_rules._session_number(v.get("session")) == visit_rules._session_number(m["session"]) + 1 for v in visits)]
    for session in sorted({m["session"] for m in closed}):
        notes.append(f"{session} is closed to start the revision after it: {', '.join(m['location_id'] for m in closed if m['session'] == session)} still planned in it, marked as not visited.")
    # a site that has no visit in a revision the file gives was not there: the revision after it has to put its camera up
    upwards = visit_rules.unknown_installation_warnings(visits, kept, [*unknown_kept, *unknown])
    warnings += [m for m in upwards if m not in warnings]
    if unknown:
        by_revision: dict[str, list[str]] = {}
        for u in unknown:
            by_revision.setdefault(u["session"], []).append(u["location_id"])
        # the revisions in a row that have the same sites are told once: R0005–R0009
        groups: list[tuple[list[str], list[str]]] = []
        for session, sites in sorted(by_revision.items()):
            number, wanted = visit_rules._session_number(session), sorted(sites)
            if groups and groups[-1][1] == wanted and visit_rules._session_number(groups[-1][0][-1]) == (number or 0) - 1:
                groups[-1][0].append(session)
            else:
                groups.append(([session], wanted))
        for sessions, sites in groups:
            name = sessions[0] if len(sessions) == 1 else f"{sessions[0]}–{sessions[-1]}"
            notes.append(f"The {'revision' if len(sessions) == 1 else 'revisions'} {name} {'is' if len(sessions) == 1 else 'are'} created, but there is no data of {'its' if len(sessions) == 1 else 'their'} visits to {', '.join(sites)}: "
                         f"they are created as unknown visits, and the visits after them cannot be checked against them.")
    # what is created is what the visits that are kept need: a location, a camera or an SD card that only a refused visit named is not
    kept_rows = {row_of[id(v)] for v in visits}
    sites = {v["location_id"].lower() for v in visits}
    create_out: dict[str, list[dict]] = {"locations": [l for site, l in new_locations.items() if site in sites], "cameras": [], "sd_cards": [], "trappers": [],
                                         "complete_cameras": [{"label": label, **fields} for label, fields in completed.items()]}
    # the people the visits that are kept say went, who are not trappers yet: made as they are called, when the import is asked to
    trapper_rows: dict[int, list[str]] = {}
    if create.get("trappers") and options.get("trappers") is not None:
        have = {str(t) for t in options["trappers"]}
        taken = {str(u).lower() for u in options.get("trapper_usernames") or []}
        for visit in visits:
            for who in (x.strip() for x in str(visit.get("trappers") or "").split(",")):
                if who and who not in have:
                    username = rules.username_of(who, taken)
                    taken.add(username.lower()); have.add(who)
                    create_out["trappers"].append({"username": username, "name": who, "status": "active"})
                if who and who in {t["name"] for t in create_out["trappers"]}:
                    trapper_rows.setdefault(row_of[id(visit)], []).append(who)
        if create_out["trappers"]:
            notes.append(f"The trappers {', '.join(t['name'] for t in create_out['trappers'])} {'is' if len(create_out['trappers']) == 1 else 'are'} created as the visits say {'it' if len(create_out['trappers']) == 1 else 'them'}: "
                         f"their username is worked out from the name ({', '.join(t['username'] for t in create_out['trappers'])}); complete them in Settings › Trappers.")
    for n in sorted(kept_rows):
        for kind in ("cameras", "sd_cards"):
            for entity in made_by_row.get(n, {}).get(kind, []):
                key = str(entity.get("camera_id") or entity.get("label"))
                if key not in {str(e.get("camera_id") or e.get("label")) for e in create_out[kind]}:
                    create_out[kind].append(entity)
    # a warning goes to the rows that are added; one about no row, or only about rows that are not added, is said apart
    loose: list[str] = []
    for message, rows_about in said:
        added = [n for n in rows_about if n in kept_rows]
        if not added:
            loose.append(message)
        for n in added:
            if message not in report[n].setdefault("warnings", []):
                report[n]["warnings"].append(message)
    loose += upwards
    for n in sorted(kept_rows):
        names = [f"the location {l['location_id']}" for l in made_by_row.get(n, {}).get("locations", [])]
        names += [f"the camera {c['camera_id']}" for c in made_by_row.get(n, {}).get("cameras", [])]
        names += [f"the SD card {c['label']}" for c in made_by_row.get(n, {}).get("sd_cards", [])]
        names += [f"the trapper {w}" for w in dict.fromkeys(trapper_rows.get(n, []))]
        if names and n in report and report[n]["result"] == "ok":
            report[n]["message"] = f"The visit is added, and creates {', '.join(names)}."
    # what stops the file from being added, said once (#206): the rows with an error of their own, and how many rows only wait for them — the revisions
    # after one a refused row left unfinished
    waiting = [p for p in problems if p.get("waits")]
    sessions = sorted({report[p["row"]].get("session") for p in waiting if report.get(p["row"], {}).get("session")})
    blocking = {"errors": [{"row": p["row"], "site": report.get(p["row"], {}).get("site", ""), "session": report.get(p["row"], {}).get("session", ""), "message": p["message"]}
                           for p in problems if not p.get("waits")],
                "waiting": {"rows": len(waiting), "from": sessions[0] if sessions else None, "to": sessions[-1] if sessions else None}}
    return {"visits": visits, "problems": problems, "rows": [report[n] for n in sorted(report)], "skipped": skipped, "new_sites": new_sites,
            "create": create_out, "warnings": warnings, "loose_warnings": list(dict.fromkeys(loose)), "notes": notes, "unknown": unknown, "closed": closed,
            "blocking": blocking}


def create_out_locations(new_locations: dict[str, dict], visits: list[dict]) -> list[dict]:
    """The locations a file makes that a visit kept needs."""
    sites = {v["location_id"].lower() for v in visits}
    return [l for site, l in new_locations.items() if site in sites]


def _complete_camera(record: dict, cells: dict, completed: dict[str, dict], warnings: list[tuple[int, str]], n: int) -> None:
    """What a row says of a camera that has a record (#231): it completes what the record lacks — its serial number, make and model — and never overwrites it;
    when it says otherwise, a warning says so."""
    label = str(record.get("label") or record.get("camera_id"))
    for given, field, name in ((cells.get("camera_serial"), "camera_id", "serial number"), (cells.get("camera_make"), "camera_make", "make"),
                               (cells.get("camera_model"), "camera_model", "model")):
        given = (given or "").strip()
        if not given:
            continue
        kept = str(record.get(field) or completed.get(label, {}).get(field) or "").strip()
        if not kept:
            completed.setdefault(label, {})[field] = given
        elif " ".join(kept.split()).casefold() != " ".join(given.split()).casefold() and field != "camera_model":
            warnings.append((n, f"Row {n}: the camera {label} has the {name} {kept} in its record, and the row says {given}: the record is kept as it is."))
