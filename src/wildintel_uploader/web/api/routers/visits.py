"""FastAPI router — the visits to the camera traps of a research project, kept in its folder of the collections folder
(see local_folder_service.list_visits and write_visit)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from wildintel_uploader.core import config
from wildintel_uploader.core.schemas.requests import ImportVisitsCsvRequest, LinkVisitRequest, ListVisitsRequest, SaveVisitRequest, VisitsCsvColumnsRequest
from wildintel_uploader.core.services import local_folder_service, visits_csv

router = APIRouter(prefix="/api/visits", tags=["visits"])


@router.post("/list")
def list_visits(req: ListVisitsRequest) -> dict:
    """The visits kept for a research project, those to one location only when it is given."""
    try:
        return {"results": local_folder_service.list_visits(config.collections_dir(), req.research_project_id, req.location_id)}
    except local_folder_service.LocalFolderError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/save")
def save_visit(req: SaveVisitRequest) -> dict:
    """Registers a visit to a research project already kept in the collections folder."""
    try:
        return local_folder_service.write_visit(config.collections_dir(), req.research_project_id, req.visit.model_dump(mode="json"))
    except local_folder_service.LocalFolderError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/import-csv")
def import_visits_csv(req: ImportVisitsCsvRequest) -> dict:
    """Reads the visits of a CSV file for a research project: what can be kept and what is wrong with the rest — kept when `save` is set."""
    root = config.collections_dir()
    try:
        result = visits_csv.parse_visits(
            req.csv, local_folder_service.list_locations(root, req.research_project_id), local_folder_service.list_visits(root, req.research_project_id), f"{req.research_project_id}_", req.format, req.mapping,
        )
        saved = local_folder_service.write_visits(root, req.research_project_id, result["visits"]) if req.save else None
    except (local_folder_service.LocalFolderError, visits_csv.VisitsCsvError) as exc:
        raise HTTPException(400, str(exc)) from exc
    return {**result, "saved": saved}


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
        return {"results": local_folder_service.closed_visits(config.collections_dir(), req.research_project_id)}
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
