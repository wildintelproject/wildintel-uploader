"""FastAPI router — the visits to the camera traps of a research project, kept in its folder of the collections folder
(see local_folder_service.list_visits and write_visit)."""
from __future__ import annotations

import base64

from fastapi import APIRouter, HTTPException

from wildintel_uploader.core import config
from wildintel_uploader.core.schemas.requests import FieldLogsRequest, ImportVisitsCsvRequest, LinkVisitRequest, ListVisitsRequest, SaveVisitRequest, VisitsCsvColumnsRequest
from wildintel_uploader.core.services import local_folder_service, visit_deployments, visit_rules, visit_time, visits_csv, visits_xlsx

router = APIRouter(prefix="/api/visits", tags=["visits"])


def _write_logs(root, research_project_id: str, new: list[dict]) -> dict:
    """The folders of the collections the new visits change, and their FileTimestampLog and FieldworkLog — made when a visit is registered, not when its
    deployment is imported. {"collections": [...], "warnings": [...]}; nothing is written when no deployment is said by the visits yet."""
    if not new:
        return {"collections": [], "warnings": []}
    visits = local_folder_service.list_visits(root, research_project_id)
    return visit_deployments.write_collection_logs(root, research_project_id, visit_deployments.collections_of(visits, new))


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
        reasons = visit_rules.refusals(visit, local_folder_service.list_visits(root, req.research_project_id), locations)
        if reasons:
            raise HTTPException(422, " ".join(reasons))
        kept = local_folder_service.write_visit(root, req.research_project_id, visit)
        return {**kept, "field_logs": _write_logs(root, req.research_project_id, [kept])}
    except local_folder_service.LocalFolderError as exc:
        raise HTTPException(400, str(exc)) from exc


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
        prefix = f"{req.research_project_id}_"
        history = None
        if req.history_xlsx:
            try:
                text = visits_xlsx.to_csv(base64.b64decode(req.history_xlsx, validate=False))
            except (visits_xlsx.VisitsXlsxError, ValueError) as exc:
                raise HTTPException(400, f"The history of visits: {exc}") from exc
            try:
                history = visits_csv.parse_visits(text, locations, kept, prefix, "epicollect", None)
            except visits_csv.VisitsCsvError as exc:
                raise HTTPException(400, f"The history of visits: {exc}") from exc
        result = visits_csv.parse_visits(req.csv, locations, kept + (history["visits"] if history else []), prefix, req.format, req.mapping)
        if history:
            seen = {s["site"].lower() for s in result["new_sites"]}
            result = {
                **result, "visits": history["visits"] + result["visits"], "history": len(history["visits"]),
                "problems": [{**p, "history": True} for p in history["problems"]] + result["problems"],
                "new_sites": result["new_sites"] + [s for s in history["new_sites"] if s["site"].lower() not in seen],
                "warnings": list(dict.fromkeys([*history["warnings"], *result["warnings"]])), "skipped": result["skipped"] + history["skipped"],
            }
        saved = field_logs = None
        if req.save:
            saved = local_folder_service.write_visits(root, req.research_project_id, result["visits"])
            field_logs = _write_logs(root, req.research_project_id, result["visits"])
    except (local_folder_service.LocalFolderError, visits_csv.VisitsCsvError) as exc:
        raise HTTPException(400, str(exc)) from exc
    return {**result, "saved": saved, "field_logs": field_logs}


@router.post("/csv-columns")
def csv_columns(req: VisitsCsvColumnsRequest) -> dict:
    """The columns of a CSV file, a few of its rows, the fields of a visit it can give and the column that most likely gives each."""
    try:
        return {**visits_csv.suggest_mapping(req.csv), "fields": [{"field": f, "label": label, "required": required} for f, label, required in visits_csv.FIELDS]}
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
        return local_folder_service.link_visit(
            config.collections_dir(), req.research_project_id, req.location_id, req.date.isoformat(), req.time.isoformat(), req.deployment_id,
        )
    except local_folder_service.LocalFolderError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/deployments")
def deployments(req: ListVisitsRequest) -> dict:
    """The deployments the visits of a research project say — closed ones (a visit left the camera and a later one collected its card) and open ones (the camera is
    still out) — by collection, with their fields as Camtrap DP names them."""
    try:
        root = config.collections_dir()
        local_folder_service.require_research_project(root, req.research_project_id)
        found = visit_deployments.deployments(local_folder_service.list_visits(root, req.research_project_id, req.location_id))
    except local_folder_service.LocalFolderError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"results": [{k: v for k, v in d.items() if k not in ("start_visit", "end_visit")} | {"start_session": d["start_visit"].get("session"), "end_session": (d["end_visit"] or {}).get("session")} for d in found]}


@router.post("/field-logs")
def field_logs(req: FieldLogsRequest) -> dict:
    """Writes, in the folder of each collection the visits give deployments to, its FileTimestampLog (the closed deployments' start and end) and its FieldworkLog
    (every deployment, closed or open, with its fields as Camtrap DP names them)."""
    try:
        return visit_deployments.write_collection_logs(config.collections_dir(), req.research_project_id, req.collections)
    except local_folder_service.LocalFolderError as exc:
        raise HTTPException(400, str(exc)) from exc
