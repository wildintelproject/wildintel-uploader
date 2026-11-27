"""FastAPI routers — the uploaders (module `modules.uploaders`): the account and what TRAPPER has (/api/trapper), the uploads of the deployments
kept (/api/upload), bringing back what TRAPPER has (/api/sync), and importing a deployment into TRAPPER from the wizard
(/api/deployment-import/import), at the addresses the pages have always used. What they refuse is told with the status its kind says."""
from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from dishka.integrations.fastapi import DishkaSyncRoute, FromDishka
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from wildintel_uploader.entrypoints.api import streaming
from wildintel_uploader.modules.uploaders.domain.models import Account, UploaderError
from wildintel_uploader.modules.uploaders.domain.ports import UploadersService
from wildintel_uploader.modules.uploaders.infrastructure.api_schemas import (
    AccessCheckRequest, ClassificationProjectsRequest, DeploymentsRequest, ImportDeploymentRequest, LocationsRequest, SyncCollectionNamesRequest,
    SyncCollectionsRequest, TrapperCredentials, UploadClassificationProjectsRequest, UploadCollectionsRequest, UploadDeploymentRequest, UploadReportRequest,
)

trapper_router = APIRouter(prefix="/api/trapper", tags=["uploaders"], route_class=DishkaSyncRoute)
upload_router = APIRouter(prefix="/api/upload", tags=["uploaders"], route_class=DishkaSyncRoute)
sync_router = APIRouter(prefix="/api/sync", tags=["uploaders"], route_class=DishkaSyncRoute)
import_router = APIRouter(prefix="/api/deployment-import", tags=["uploaders"], route_class=DishkaSyncRoute)
Uploaders = FromDishka[UploadersService]
T = TypeVar("T")


def _account(req: TrapperCredentials) -> Account:
    return Account(req.url, req.username, req.password)


def _http(call: Callable[[], T]) -> T:
    try:
        return call()
    except UploaderError as exc:
        raise HTTPException(exc.status, exc.message) from exc


# ── the account and what TRAPPER has ──

@trapper_router.get("/config")
def get_config(uploaders: Uploaders) -> dict:
    """Saved TRAPPER connection defaults — never the password itself."""
    return uploaders.account_defaults()


@trapper_router.post("/test-connection")
def test_connection(req: TrapperCredentials, uploaders: Uploaders) -> dict:
    """Checks the credentials, and saves them to settings.toml once they work — so they needn't be retyped."""
    return _http(lambda: uploaders.test_connection(_account(req)))


@trapper_router.post("/research-projects")
def research_projects(req: TrapperCredentials, uploaders: Uploaders) -> dict:
    return {"results": _http(lambda: uploaders.research_projects(_account(req)))}


@trapper_router.post("/classification-projects")
def classification_projects(req: ClassificationProjectsRequest, uploaders: Uploaders) -> dict:
    return {"results": _http(lambda: uploaders.classification_projects(_account(req), req.research_project_pk))}


@trapper_router.post("/locations")
def locations(req: LocationsRequest, uploaders: Uploaders) -> dict:
    return {"results": _http(lambda: uploaders.locations(_account(req), req.research_project_pk))}


@trapper_router.post("/deployments")
def deployments(req: DeploymentsRequest, uploaders: Uploaders) -> dict:
    """Existing deployments of a research project — for the "use an existing deployment" wizard branch."""
    return {"results": _http(lambda: uploaders.deployments(_account(req), req.research_project_pk))}


# ── importing a deployment into TRAPPER from the wizard ──

@import_router.post("/import", response_model=None)
def import_deployment(req: ImportDeploymentRequest, uploaders: Uploaders) -> StreamingResponse:
    """The import's events, as NDJSON: {"type": "copy", "index", "total", "name"}, {"type": "registering"}, {"type": "done", "dest_dir"}, and
    {"type": "error", "detail"} when something fails midway. Bad paths are a plain 400, checked before any file is touched."""
    events = _http(lambda: uploaders.import_deployment(_account(req), req.research_project_pk, req.classification_project_pk, req.source_dir, req.deployment,
                                                       req.research_project_id, req.register_deployment))
    return streaming.from_events(events, "Deployment import failed")


# ── uploading the deployments kept ──

@upload_router.post("/collections")
def collections(req: UploadCollectionsRequest, uploaders: Uploaders) -> dict:
    """The collections kept for a research project, and the deployments in each — what can be uploaded."""
    return {"results": _http(lambda: uploaders.collections(req.research_project_id))}


@upload_router.post("/classification-projects")
def upload_classification_projects(req: UploadClassificationProjectsRequest, uploaders: Uploaders) -> dict:
    """The classification projects TRAPPER has for a research project kept locally — the collection goes to one of them."""
    return {"results": _http(lambda: uploaders.project_classification_projects(_account(req), req.research_project_id))}


@upload_router.post("/check-selection")
def check_selection(req: AccessCheckRequest, uploaders: Uploaders) -> dict:
    """Whether the account has access to the research project — and to the collection, when one is chosen — {"checks": [...]}."""
    return {"checks": _http(lambda: uploaders.check_selection(_account(req), req.research_project_id, req.collection))}


@upload_router.post("/check-access")
def check_access(req: AccessCheckRequest, uploaders: Uploaders) -> dict:
    """Whether the account can reach what an upload needs, changing nothing: one {"check", "ok", "message"} per check."""
    return {"checks": _http(lambda: uploaders.check_access(_account(req), req.research_project_id, req.collection, req.deployment_ids,
                                                           req.classification_project_pk))}


@upload_router.post("/deployment", response_model=None)
def upload_deployment(req: UploadDeploymentRequest, uploaders: Uploaders) -> StreamingResponse:
    """Uploads one deployment, as NDJSON events — a failure midway is an {"type": "error", "detail"} line. What can be checked first is a plain 4xx."""
    events = _http(lambda: uploaders.upload(_account(req), req.research_project_id, req.collection, req.deployment_id, req.mode,
                                            req.classification_project_pk, req.delete_files))
    return streaming.from_events(events, f"Uploading {req.deployment_id} failed")


@upload_router.post("/report")
def save_upload_report(req: UploadReportRequest, uploaders: Uploaders) -> dict:
    """Keeps the report of an upload that has ended — what went up, what failed and why."""
    return {"report_id": uploaders.upload_report(req.collection, req.research_project_id, req.items, req.started_at, req.finished_at)}


# ── bringing back what TRAPPER has ──

@sync_router.post("/collection-names")
def collection_names(req: SyncCollectionNamesRequest, uploaders: Uploaders) -> dict:
    """The collections starting with R of a classification project and their deployments, to choose what to sync."""
    return {"results": _http(lambda: uploaders.collection_names(_account(req), req.research_project_pk, req.classification_project_pk))}


@sync_router.post("/collections", response_model=None)
def sync_collections(req: SyncCollectionsRequest, uploaders: Uploaders) -> StreamingResponse:
    """Creates in the collections folder what TRAPPER has for the classification project and it lacks, as NDJSON."""
    project = {"pk": req.research_project_pk, "name": req.research_project_name, "acronym": req.research_project_acronym}
    events = _http(lambda: uploaders.sync(_account(req), project, req.classification_project_pk, req.collections, req.deployments, req.download_images))
    return streaming.from_events(events, "Syncing the local collections failed")
