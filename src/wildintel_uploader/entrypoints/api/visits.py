"""FastAPI router — the visits to the camera traps of a research project (module `modules.visits`), at the addresses the pages have always used
(/api/visits/…). It asks only for the contract, VisitsService, and turns what it refuses into HTTP: a visit that breaks the rules 422, one that can't
be changed now 409, one that is not there 404, what the records or a file can't give 400."""
from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from dishka.integrations.fastapi import DishkaSyncRoute, FromDishka
from fastapi import APIRouter, HTTPException

from wildintel_uploader.modules.visits.domain.models import ImportOptions, VisitLocked, VisitMissing, VisitRefused, VisitsError
from wildintel_uploader.modules.visits.domain.ports import VisitsService
from wildintel_uploader.modules.visits.infrastructure.api_schemas import (
    CreateRevisionRequest, ImportVisitsCsvRequest, LinkVisitRequest, ListVisitsRequest, MarkNotVisitedRequest, SaveVisitRequest, UpdateVisitRequest,
    VisitsCsvColumnsRequest,
)
from wildintel_uploader.modules.visits.infrastructure.api_schemas import (  # what its routes answer
    ClosedVisitsAnswer, CreateRevisionAnswer, CsvColumnsAnswer, DeploymentsAnswer, EpicollectDownloadAnswer, ImportVisitsCsvAnswer, LinkVisitAnswer, ListVisitsAnswer, MarkNotVisitedAnswer, SaveVisitAnswer, UpdateVisitAnswer, VisitBookAnswer, VisitsExported,
)

router = APIRouter(prefix="/api/visits", tags=["visits"], route_class=DishkaSyncRoute)
Visits = FromDishka[VisitsService]
T = TypeVar("T")
_STATUS = ((VisitRefused, 422), (VisitLocked, 409), (VisitMissing, 404))


def _http(call: Callable[[], T]) -> T:
    try:
        return call()
    except VisitsError as exc:
        raise HTTPException(next((code for kind, code in _STATUS if isinstance(exc, kind)), 400), exc.message) from exc


@router.post("/list", response_model=ListVisitsAnswer, response_model_exclude_unset=True)
def list_visits(req: ListVisitsRequest, visits: Visits) -> dict:
    """The visits kept for a research project, those to one location only when it is given."""
    return {"results": _http(lambda: visits.visits(req.research_project_id, req.location_id))}


@router.post("/save", response_model=SaveVisitAnswer, response_model_exclude_unset=True)
def save_visit(req: SaveVisitRequest, visits: Visits) -> dict:
    """Registers a visit to a research project — if it follows the rules of a visit (modules.visits.domain.rules)."""
    return _http(lambda: visits.save(req.research_project_id, req.visit.model_dump(mode="json")))


@router.post("/update", response_model=UpdateVisitAnswer, response_model_exclude_unset=True)
def update_visit(req: UpdateVisitRequest, visits: Visits) -> dict:
    """Edits a visit kept — its key, the site and the revision, does not change. One that starts or closes an imported deployment can't be (409);
    what the edit would make wrong is told, and nothing is changed (422)."""
    return _http(lambda: visits.update(req.research_project_id, req.location_id, req.session, req.visit.model_dump(mode="json")))


@router.post("/create-revision", response_model=CreateRevisionAnswer, response_model_exclude_unset=True)
def create_revision(req: CreateRevisionRequest, visits: Visits) -> dict:
    """Plans the next revision: {"session", "planned": [location ids], "previous": {"session", "missing"} | None}."""
    return _http(lambda: visits.create_revision(req.research_project_id))


@router.post("/mark-not-visited", response_model=MarkNotVisitedAnswer, response_model_exclude_unset=True)
def mark_not_visited(req: MarkNotVisitedRequest, visits: Visits) -> dict:
    """Finishes a revision whose locations were not all visited: {"session", "marked": [location ids]}."""
    return _http(lambda: visits.mark_not_visited(req.research_project_id, req.session))


@router.post("/import-csv", response_model=ImportVisitsCsvAnswer, response_model_exclude_unset=True)
def import_visits_csv(req: ImportVisitsCsvRequest, visits: Visits) -> dict:
    """Reads the visits of a CSV file — or of a source — and, when `save` is set, keeps them; only one save at a time for a research project (409)."""
    options = ImportOptions(research_project_id=req.research_project_id, csv=req.csv, save=req.save, format=req.format, mapping=req.mapping,
                            create=req.create, close_revisions=req.close_revisions, close_after=req.close_after.model_dump() if req.close_after else None,
                            coordinates_from_location=req.coordinates_from_location, photos_not_counted=req.photos_not_counted, defaults=req.defaults)
    return _http(lambda: visits.import_file(options))


@router.post("/export-csv", response_model=VisitsExported, response_model_exclude_unset=True)
def export_visits_csv(req: ListVisitsRequest, visits: Visits) -> dict:
    """The visits kept as a CSV that /import-csv reads back: {"csv", "filename", "count"}."""
    return _http(lambda: visits.export_file(req.research_project_id, req.location_id))


@router.post("/epicollect-download", response_model=EpicollectDownloadAnswer, response_model_exclude_unset=True)
def epicollect_download(visits: Visits) -> dict:
    """The entries of the Epicollect5 project of the settings as a CSV with a row per visit: {"csv", "count"}."""
    return _http(visits.epicollect_download)


@router.post("/csv-columns", response_model=CsvColumnsAnswer, response_model_exclude_unset=True)
def csv_columns(req: VisitsCsvColumnsRequest, visits: Visits) -> dict:
    """The columns of a CSV, whether it is the download of the WildINTEL form, a few rows, and the fields of a visit it can give."""
    return _http(lambda: visits.file_columns(req.csv))


@router.post("/closed", response_model=ClosedVisitsAnswer, response_model_exclude_unset=True)
def closed_visits(req: ListVisitsRequest, visits: Visits) -> dict:
    """The visits that closed a deployment and have none yet — the ones a deployment is imported for."""
    return {"results": _http(lambda: visits.closed(req.research_project_id))}


@router.post("/link", response_model=LinkVisitAnswer, response_model_exclude_unset=True)
def link_visit(req: LinkVisitRequest, visits: Visits) -> dict:
    """Records which deployment a visit closed, once it is imported."""
    return _http(lambda: visits.link(req.research_project_id, req.location_id, req.date.isoformat(), req.time.isoformat(), req.deployment_id))


@router.post("/deployments", response_model=DeploymentsAnswer, response_model_exclude_unset=True)
def deployments(req: ListVisitsRequest, visits: Visits) -> dict:
    """The deployments the visits say — closed and open — with where they were uploaded."""
    return {"results": _http(lambda: visits.deployments(req.research_project_id, req.location_id))}


@router.post("/book", response_model=VisitBookAnswer, response_model_exclude_unset=True)
def visit_book(req: ListVisitsRequest, visits: Visits) -> dict:
    """The visit book: the visits, each with its deployment, and a row for each location not visited in a session (`not_done`)."""
    return {"results": _http(lambda: visits.book(req.research_project_id, req.location_id))}
