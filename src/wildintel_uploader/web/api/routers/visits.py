"""FastAPI router — the visits to the camera traps of a research project, kept in its folder of the collections folder
(see local_folder_service.list_visits and write_visit)."""
from __future__ import annotations

import base64

from fastapi import APIRouter, HTTPException

from wildintel_uploader.core import config
from wildintel_uploader.core.schemas.requests import FieldLogsRequest, ImportVisitsCsvRequest, LinkVisitRequest, ListVisitsRequest, MarkNotVisitedRequest, SaveVisitRequest, VisitRecord, VisitsCsvColumnsRequest
from wildintel_uploader.core.services import epicollect_service, local_folder_service, report_service, trapper_upload_service, visit_deployments, visit_rules, visit_time, visits_csv, visits_xlsx

router = APIRouter(prefix="/api/visits", tags=["visits"])


def _trapper_state(root, research_project_id: str, deployment_id: str | None) -> tuple[str | None, bool]:
    """Whether the deployment a visit gave is on Trapper — it was uploaded from here (its upload.json says when) or it was synced from there — and when it was uploaded."""
    if not deployment_id:
        return None, False
    folder = root / research_project_id / deployment_id.split("-", 1)[0] / deployment_id
    upload = local_folder_service._read_json(folder / trapper_upload_service.UPLOAD_LOG_FILE)
    uploaded_at = upload.get("uploaded_at") if isinstance(upload, dict) else None
    return uploaded_at, bool(uploaded_at) or local_folder_service.is_synced(folder)


def _uploads_of(folder) -> list[dict]:
    """What was done with a deployment's folder: one upload for each platform it was sent to (only "trapper" for now) — `kind` "uploaded" with the day and what it did, or "synced"
    when the deployment came from Trapper and was not sent from here. None when it was not sent anywhere."""
    upload = local_folder_service._read_json(folder / trapper_upload_service.UPLOAD_LOG_FILE)
    # the page of the deployment in Trapper — or of its revision —, as it was when it was sent; an upload made before that was kept goes to the site
    site = (config.load_settings().TRAPPER.base_url or "").rstrip("/") or None
    if isinstance(upload, dict) and upload.get("uploaded_at"):
        return [{"destination": "trapper", "kind": "uploaded", "uploaded_at": upload.get("uploaded_at"), "parts": upload.get("parts"),
                 "location_created": bool(upload.get("location_created")), "deployment_created": bool(upload.get("deployment_created")),
                 "url": upload.get("deployment_url") or upload.get("collection_url") or site}]
    if local_folder_service.is_synced(folder):
        return [{"destination": "trapper", "kind": "synced", "uploaded_at": None, "parts": None, "location_created": None, "deployment_created": None, "url": site}]
    return []


# Where a deployment can be sent, and the settings that say whether each is used: only the uploaders that are in use have an upload planned.
UPLOADERS = {"trapper": lambda settings: settings.TRAPPER.enabled, "agouti": lambda settings: settings.AGOUTI.enabled}


def _upload_states(root, research_project_id: str, imported: str | None, deployment_id: str, failures: list[dict]) -> list[dict]:
    """The upload of a deployment to each uploader in use: "planned" from the start, then "done" (it was sent from here, or it was synced from the destination) or "failed" (it was
    tried and did not work: it can be tried again) — {"destination", "state", "kind", "uploaded_at", "note"}."""
    settings = config.load_settings()
    # what was done is told by the folder of the deployment, once it is created (`imported`); what failed, by the failures kept
    done = {u["destination"]: u for u in (_uploads_of(root / research_project_id / imported.split("-", 1)[0] / imported) if imported else [])}
    failed = {f["destination"]: f for f in failures if f.get("deployment_id") == deployment_id}
    out = []
    for destination, used in UPLOADERS.items():
        if not used(settings) and destination not in done:
            continue
        if destination in done:
            out.append({"destination": destination, "state": "done", "kind": done[destination]["kind"], "uploaded_at": done[destination].get("uploaded_at"), "note": None})
        elif destination in failed:
            out.append({"destination": destination, "state": "failed", "kind": None, "uploaded_at": None, "note": failed[destination].get("note")})
        else:
            out.append({"destination": destination, "state": "planned", "kind": None, "uploaded_at": None, "note": None})
    return out


def _write_logs(root, research_project_id: str, new: list[dict]) -> dict:
    """The folders of the collections the new visits change, and their FileTimestampLog and FieldworkLog — made when a visit is registered, not when its
    deployment is imported. {"collections": [...], "warnings": [...]}; nothing is written when no deployment is said by the visits yet."""
    if not new:
        return {"collections": [], "warnings": []}
    visits = local_folder_service.list_visits(root, research_project_id)
    keep = config.load_settings().FIELDLOG.keep_seconds
    return visit_deployments.write_collection_logs(root, research_project_id, visit_deployments.collections_of(visits, new, keep), keep)


def _refresh_states(root, research_project_id: str) -> None:
    """Keeps the state of the visits — a visit that left a camera is collected once a later one took its card, and the one just added has its own."""
    visit_deployments.refresh_states(root, research_project_id, config.load_settings().FIELDLOG.keep_seconds)


def _archive_locations(root, research_project_id: str, new: list[dict]) -> list[str]:
    """The locations that the visits with an Archive action give up: archived from the day of the visit, with a note that says which visit did it."""
    done = []
    for v in new:
        if "Archive" not in (v.get("actions") or []):
            continue
        note = f"Archived in the visit {v.get('session')}" + (f": {v['comments']}" if v.get("comments") else "")
        try:
            local_folder_service.update_location(root, research_project_id, v["location_id"], {"status": "archived", "status_date": v["date"], "status_note": note})
            done.append(v["location_id"])
        except local_folder_service.LocalFolderError:
            continue
    return done


@router.post("/list")
def list_visits(req: ListVisitsRequest) -> dict:
    """The visits kept for a research project, those to one location only when it is given."""
    try:
        return {"results": local_folder_service.list_visits(config.collections_dir(), req.research_project_id, req.location_id)}
    except local_folder_service.LocalFolderError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/save")
def save_visit(req: SaveVisitRequest) -> dict:
    """Registers a visit to a research project already kept in the collections folder — if it follows the rules of a visit (see services.visit_rules): its
    site is a location of the project, it is not kept already, it has what its actions ask and its camera and card are where it says."""
    root = config.collections_dir()
    try:
        local_folder_service.require_research_project(root, req.research_project_id)
        visit = req.visit.model_dump(mode="json")
        locations = local_folder_service.list_locations(root, req.research_project_id)
        # the rules compare instants: the day and the time are the wall clock of the location
        location = next((l for l in locations if str(l.get("location_id", "")).lower() == visit["location_id"].lower()), None)
        visit["when"] = visit_time.to_when(visit["date"], visit["time"], location)
        reasons = visit_rules.refusals(visit, local_folder_service.list_visits(root, req.research_project_id), locations,
                                       local_folder_service.list_field_items(root, req.research_project_id, "sd_cards"))
        if reasons:
            raise HTTPException(422, " ".join(reasons))
        kept = local_folder_service.write_visit(root, req.research_project_id, visit)
        _archive_locations(root, req.research_project_id, [kept])
        _refresh_states(root, req.research_project_id)
        return {**kept, "field_logs": _write_logs(root, req.research_project_id, [kept])}
    except local_folder_service.LocalFolderError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/mark-not-visited")
def mark_not_visited(req: MarkNotVisitedRequest) -> dict:
    """Finishes a revision whose locations were not all visited: each of them that has no visit in it gets one with the status "Not revised" — the visit
    that could not be made. {"session", "marked": [location ids]}."""
    root = config.collections_dir()
    try:
        local_folder_service.require_research_project(root, req.research_project_id)
        locations = local_folder_service.list_locations(root, req.research_project_id)
        kept = local_folder_service.list_visits(root, req.research_project_id)
        records = visit_rules.not_visited_records(int(req.session[1:]), kept, locations)
        for record in records:
            location = next((l for l in locations if str(l.get("location_id", "")).lower() == record["location_id"].lower()), None)
            record["when"] = visit_time.to_when(record["date"], record["time"], location)
        local_folder_service.write_visits(root, req.research_project_id, [VisitRecord.model_validate(r).model_dump(mode="json") for r in records])
        _refresh_states(root, req.research_project_id)
        return {"session": req.session, "marked": [r["location_id"] for r in records]}
    except local_folder_service.LocalFolderError as exc:
        raise HTTPException(400, str(exc)) from exc


def _save_report(research_project_id: str, result: dict, saved: int) -> str | None:
    """The report of an import, kept with the other reports (see report_service) — its id; None when it could not be written."""
    try:
        return report_service.save(report_service.visits_import_report(research_project_id, result, saved))
    except OSError:
        return None


@router.post("/import-csv")
def import_visits_csv(req: ImportVisitsCsvRequest) -> dict:
    """Reads the visits of a CSV file for a research project: what can be kept and what is wrong with the rest — kept when `save` is set.

    With a history of visits (the fieldwork datasheet, an .xlsx) the history comes first: it completes the visits kept, and then the file's are applied on top of
    both — their sessions, what is already kept and what is odd are told with all of it in front. The visits of the history come first in "visits" ("history"
    says how many), and what is wrong with them is told beside the file's, from the history ("history": true). When the visits are kept, the folders of the
    collections they change get their FileTimestampLog and FieldworkLog."""
    root = config.collections_dir()
    try:
        locations = local_folder_service.list_locations(root, req.research_project_id)
        kept = local_folder_service.list_visits(root, req.research_project_id)
        cards = local_folder_service.list_field_items(root, req.research_project_id, "sd_cards")
        cameras = local_folder_service.list_field_items(root, req.research_project_id, "cameras")
        prefix = f"{req.research_project_id}_"
        history = None
        if req.history_xlsx:
            try:
                text = visits_xlsx.to_csv(base64.b64decode(req.history_xlsx, validate=False))
            except (visits_xlsx.VisitsXlsxError, ValueError) as exc:
                raise HTTPException(400, f"The history of visits: {exc}") from exc
            try:
                history = visits_csv.parse_visits(text, locations, kept, prefix, "epicollect", None, {"cards": cards})
            except visits_csv.VisitsCsvError as exc:
                raise HTTPException(400, f"The history of visits: {exc}") from exc
        field_options = config.load_settings().FIELDLOG
        text, fmt, mapping, time_source = req.csv, req.format, req.mapping, field_options.time_source
        if fmt == "epicollect-api":
            # the entries come from Epicollect5 as rows of a visit's columns; the day and the hour typed in the form are the time of the visit
            try:
                text = epicollect_service.visits_csv(config.load_settings())
            except epicollect_service.EpicollectError as exc:
                raise HTTPException(400, str(exc)) from exc
            fmt, mapping, time_source = "mapped", {c: c for c in epicollect_service.VISIT_COLUMNS}, "hour"
        result = visits_csv.parse_visits(text, locations, kept + (history["visits"] if history else []), prefix, fmt, mapping, {"time_source": time_source, "cards": cards, "cameras": cameras, "create": req.create, "defaults": req.defaults})
        if history:
            seen = {s["site"].lower() for s in result["new_sites"]}
            result = {
                **result, "visits": history["visits"] + result["visits"], "history": len(history["visits"]),
                "problems": [{**p, "history": True} for p in history["problems"]] + result["problems"],
                "new_sites": result["new_sites"] + [s for s in history["new_sites"] if s["site"].lower() not in seen],
                "warnings": list(dict.fromkeys([*history["warnings"], *result["warnings"]])), "notes": list(dict.fromkeys([*history["notes"], *result["notes"]])),
                "skipped": result["skipped"] + history["skipped"],
            }
        saved = field_logs = report = None
        if req.save:
            # what the visits need is created first: their locations, cameras and SD cards
            for location in result["create"]["locations"]:
                local_folder_service.write_location(root, req.research_project_id, location)
            for kind, kept_items in (("cameras", cameras), ("sd_cards", cards)):
                if result["create"][kind]:
                    local_folder_service.write_field_items(root, req.research_project_id, kind, [*kept_items, *result["create"][kind]])
            saved = local_folder_service.write_visits(root, req.research_project_id, result["visits"])
            _archive_locations(root, req.research_project_id, result["visits"])
            _refresh_states(root, req.research_project_id)
            field_logs = _write_logs(root, req.research_project_id, result["visits"])
            report = _save_report(req.research_project_id, result, saved)
    except (local_folder_service.LocalFolderError, visits_csv.VisitsCsvError) as exc:
        raise HTTPException(400, str(exc)) from exc
    return {**result, "saved": saved, "field_logs": field_logs, "report": report}


@router.post("/export-csv")
def export_visits_csv(req: ListVisitsRequest) -> dict:
    """The visits kept to a research project as a CSV that /import-csv reads back (every visit, or those to one location when it is given): {"csv", "filename", "count"}."""
    try:
        visits = local_folder_service.list_visits(config.collections_dir(), req.research_project_id)
    except local_folder_service.LocalFolderError as exc:
        raise HTTPException(400, str(exc)) from exc
    if req.location_id:
        visits = [v for v in visits if str(v.get("location_id", "")).lower() == req.location_id.lower()]
    return {"csv": visits_csv.export_visits(visits), "filename": f"{req.research_project_id}_visits.csv", "count": len(visits)}


@router.post("/csv-columns")
def csv_columns(req: VisitsCsvColumnsRequest) -> dict:
    """The columns of a CSV file, a few of its rows, the fields of a visit it can give and the column that most likely gives each."""
    try:
        needed_by = {f: [e for e, spec in visits_csv.CREATABLE.items() if f in spec["required"]] for f, _, _ in visits_csv.FIELDS}
        return {**visits_csv.suggest_mapping(req.csv), "fields": [
            {"field": f, "label": label, "required": required, "entity": visits_csv.ENTITY_ONLY.get(f), "required_with": needed_by[f]} for f, label, required in visits_csv.FIELDS]}
    except visits_csv.VisitsCsvError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/closed")
def closed_visits(req: ListVisitsRequest) -> dict:
    """The visits of a research project that closed a deployment and have none yet — the ones a deployment is imported for."""
    try:
        closed = local_folder_service.closed_visits(config.collections_dir(), req.research_project_id)
        # with what the two visits say of the deployment, mixed as the FieldworkLog mixes them: what the form of the deployment starts from
        return {"results": [{**c, "details": visit_deployments.merged_details(c["visit"], c["end"])} for c in closed]}
    except local_folder_service.LocalFolderError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/link")
def link_visit(req: LinkVisitRequest) -> dict:
    """Records which deployment a visit closed, once it is imported."""
    try:
        root = config.collections_dir()
        linked = local_folder_service.link_visit(root, req.research_project_id, req.location_id, req.date.isoformat(), req.time.isoformat(), req.deployment_id)
        _refresh_states(root, req.research_project_id)
        return linked
    except local_folder_service.LocalFolderError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/deployments")
def deployments(req: ListVisitsRequest) -> dict:
    """The deployments the visits of a research project say — closed ones (a visit left the camera and a later one collected its card) and open ones (the camera is
    still out) — by collection, with their fields as Camtrap DP names them."""
    try:
        root = config.collections_dir()
        local_folder_service.require_research_project(root, req.research_project_id)
        found = visit_deployments.deployments(local_folder_service.list_visits(root, req.research_project_id, req.location_id), config.load_settings().FIELDLOG.keep_seconds)
    except local_folder_service.LocalFolderError as exc:
        raise HTTPException(400, str(exc)) from exc
    results = []
    failures = local_folder_service.list_upload_failures(root, req.research_project_id)
    for d in found:
        imported = d["start_visit"].get("deployment_id")
        uploaded_at, on_trapper = _trapper_state(root, req.research_project_id, imported)
        results.append({k: v for k, v in d.items() if k not in ("start_visit", "end_visit")} | {
            "start_session": d["start_visit"].get("session"), "end_session": (d["end_visit"] or {}).get("session"),
            # whether the deployment was created and its images imported (its visit says which deployment it gave), and whether it is on Trapper
            "images_stored": bool(imported), "uploaded_at": uploaded_at, "on_trapper": on_trapper,
            "uploads": _uploads_of(root / req.research_project_id / imported.split("-", 1)[0] / imported) if imported else [],
            # the upload to each uploader in use is its own: planned, done or failed — apart from the deployment's own state; a deployment that will not be made has none
            "upload_states": [] if d["no_images"] else _upload_states(root, req.research_project_id, imported, d["deployment_id"], failures),
        })
    return {"results": results}


@router.post("/field-logs")
def field_logs(req: FieldLogsRequest) -> dict:
    """Writes, in the folder of each collection the visits give deployments to, its FileTimestampLog (the closed deployments' start and end) and its FieldworkLog
    (every deployment, closed or open, with its fields as Camtrap DP names them)."""
    try:
        return visit_deployments.write_collection_logs(config.collections_dir(), req.research_project_id, req.collections, config.load_settings().FIELDLOG.keep_seconds)
    except local_folder_service.LocalFolderError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/book")
def visit_book(req: ListVisitsRequest) -> dict:
    """The visit book of a research project: its visits, each with the deployment it started and whether that is closed (a later visit collected its card) or
    open (the camera is still out) — and a row for each location that was not visited in a session the visits have (`not_done`)."""
    try:
        root = config.collections_dir()
        local_folder_service.require_research_project(root, req.research_project_id)
        _refresh_states(root, req.research_project_id)  # what was kept before the states were is given its own
        visits = local_folder_service.list_visits(root, req.research_project_id, req.location_id)
        locations = local_folder_service.list_locations(root, req.research_project_id) if req.location_id is None else None
        book = visit_deployments.visit_book(visits, config.load_settings().FIELDLOG.keep_seconds, locations)
        for visit in book:
            visit["uploaded_at"], visit["on_trapper"] = _trapper_state(root, req.research_project_id, visit.get("deployment_id"))
        return {"results": book}
    except local_folder_service.LocalFolderError as exc:
        raise HTTPException(400, str(exc)) from exc
