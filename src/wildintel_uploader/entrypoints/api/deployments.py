"""FastAPI router — the deployments (module `modules.deployments`): a memory card, a folder of images, the collections, importing a deployment
into one and its photos, at the addresses the pages have always used (/api/deployment-import/…). What can't be done is a 400, what is not there a 404."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from dishka.integrations.fastapi import DishkaSyncRoute, FromDishka
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import StreamingResponse

from wildintel_uploader.entrypoints.api import streaming
from wildintel_uploader.modules.deployments.domain.models import DeploymentMissing, DeploymentsError
from wildintel_uploader.modules.deployments.domain.ports import DeploymentsService
from wildintel_uploader.modules.deployments.infrastructure.api_schemas import (
    CardRequest, CheckCollectionRequest, CollectionPathRequest, ExistingDeploymentsRequest, ImportLocalRequest, NextRevisionRequest,
    PreviousDeploymentsRequest, RepairRequest, SaveDetailsRequest, SaveScanRequest, SaveSelectionRequest, ScanFolderRequest, StatisticsRequest,
    UploadCollectionsRequest,
)

router = APIRouter(prefix="/api/deployment-import", tags=["deployments"], route_class=DishkaSyncRoute)
repair_router = APIRouter(prefix="/api/repair", tags=["deployments"], route_class=DishkaSyncRoute)
statistics_router = APIRouter(prefix="/api/statistics", tags=["deployments"], route_class=DishkaSyncRoute)
sessions_router = APIRouter(prefix="/api/sessions", tags=["deployments"], route_class=DishkaSyncRoute)
Deployments = FromDishka[DeploymentsService]
T = TypeVar("T")


def _http(call: Callable[[], T]) -> T:
    try:
        return call()
    except DeploymentsError as exc:
        raise HTTPException(404 if isinstance(exc, DeploymentMissing) else 400, exc.message) from exc


# ── the memory card ──

@router.post("/copy-card", response_model=None)
def copy_card(req: CardRequest, deployments: Deployments) -> StreamingResponse:
    """Copies a camera's memory card — read only — to a temporary folder of this computer, so that its images are processed as any local folder.
    Streamed: "start", "progress" after each file and "done" with the `path` of the copy; removed with /discard-card-copy when the import is over."""
    return streaming.from_events(deployments.copy_card(req.path), "The SD card could not be copied")


@router.post("/eject-card")
def eject_card(req: CardRequest, deployments: Deployments) -> dict:
    """Ejects the removable drive a memory card was copied from, so it can be taken out: {"ejected": bool, "message"}."""
    return deployments.eject_card(req.path)


@router.post("/discard-card-copy")
def discard_card_copy(req: CardRequest, deployments: Deployments) -> dict:
    """Removes the temporary copy of a memory card — only one made by /copy-card. {"removed": bool}"""
    return {"removed": deployments.discard_card_copy(req.path)}


# ── a folder of images ──

@router.post("/scan-folder")
def scan_folder(req: ScanFolderRequest, deployments: Deployments) -> dict:
    """What a folder holds — and, behind the answer, its images' EXIF starts being read."""
    return _http(lambda: deployments.scan_folder(Path(req.path).expanduser()))


@router.post("/guess-details")
def guess_details(req: ScanFolderRequest, deployments: Deployments) -> dict:
    """The date range and the camera of a folder's images, read from their metadata — what the deployment form starts from."""
    return _http(lambda: deployments.guess_details(Path(req.path).expanduser()))


@router.post("/scan-session")
def scan_session(req: ScanFolderRequest, deployments: Deployments) -> dict:
    """A session folder — one subfolder per deployment — and the scan of each subfolder."""
    return _http(lambda: deployments.scan_session(Path(req.path).expanduser()))


# ── the collections ──

@router.post("/check-collection")
def check_collection(req: CheckCollectionRequest, deployments: Deployments) -> dict:
    """Whether a local collection folder already exists, and its recorded name if it does."""
    return deployments.check_collection(Path(req.path).expanduser())


@router.get("/log-entry")
def log_entry(research_project_id: str, deployment_id: str, deployments: Deployments) -> dict:
    """What the collection's FileTimestampLog and FieldworkLog say of a deployment, if they have its row."""
    return _http(lambda: deployments.log_entry(research_project_id, deployment_id))


@router.post("/seal")
def seal_status(req: CollectionPathRequest, deployments: Deployments) -> dict:
    """Whether the deployment kept in the collections folder is still what its seal.json says:
    {"status": "none" | "valid" | "broken", "changed", "missing", "added", "deployment_changed", "seal_changed"}."""
    return _http(lambda: deployments.seal_status(req.research_project_id, req.deployment_id))


@router.post("/collection-path")
def collection_path(req: CollectionPathRequest, deployments: Deployments) -> dict:
    """Where the deployment's collection is kept locally by default — <collections folder>/<research project id>/<R0003> — and whether it already
    exists (and its recorded name)."""
    return _http(lambda: deployments.collection_path(req.research_project_id, req.deployment_id))


@router.post("/existing-deployments")
def existing_deployments(req: ExistingDeploymentsRequest, deployments: Deployments) -> dict:
    """For each deployment id, the folder where it is already kept in the collections folder — or null."""
    return {"results": deployments.existing(req.research_project_id, req.deployment_ids)}


@router.post("/list-local-deployments")
def list_local_deployments(req: CheckCollectionRequest, deployments: Deployments) -> dict:
    """Deployments already organized in a local collection folder."""
    return {"results": deployments.local_deployments(Path(req.path).expanduser())}


@router.post("/previous-deployments")
def previous_deployments(req: PreviousDeploymentsRequest, deployments: Deployments) -> dict:
    """For each deployment id, the details kept for the closest earlier revision of the same location — or null."""
    return {"results": deployments.previous(req.research_project_id, req.deployment_ids)}


@router.post("/next-revision")
def next_revision(req: NextRevisionRequest, deployments: Deployments) -> dict:
    """The revision a new deployment at this location is expected to have: {"last", "next"}."""
    return deployments.next_revision(req.research_project_id, req.location_id)


# ── importing one into a local collection ──

def _import_local(req: ImportLocalRequest, deployments: DeploymentsService, consolidate: bool) -> StreamingResponse:
    preprocessing = req.preprocessing.model_dump() if req.preprocessing is not None else None
    events = _http(lambda: deployments.import_local(req.source_dir, req.collection_dir, req.collection_name, req.deployment, preprocessing, consolidate))
    return streaming.from_events(events, "Local import failed")


@router.post("/import-local", response_model=None)
def import_local(req: ImportLocalRequest, deployments: Deployments) -> StreamingResponse:
    """The images of a folder into a local collection — preprocessed, or copied as they are — and sealed, as NDJSON events."""
    return _import_local(req, deployments, consolidate=True)


@router.post("/preprocess", response_model=None)
def preprocess(req: ImportLocalRequest, deployments: Deployments) -> StreamingResponse:
    """Preprocesses the images into the collection, leaving the deployment pending — not sealed, so it can be done again — until /consolidate
    freezes it. The same NDJSON events as /import-local, less the sealing."""
    if req.preprocessing is None:
        raise HTTPException(400, "Say what to preprocess.")
    return _import_local(req, deployments, consolidate=False)


@router.post("/consolidate", response_model=None)
def consolidate(req: ImportLocalRequest, deployments: Deployments) -> StreamingResponse:
    """Freezes the preprocessed deployment: its metadata is written and it is sealed. Events: "sealing" and "done"."""
    events = _http(lambda: deployments.consolidate(req.source_dir, req.collection_dir, req.deployment))
    return streaming.from_events(events, "Consolidating failed")


# ── its photos ──

@router.get("/photos")
def deployment_photos_list(research_project_id: str, collection: str, deployment_id: str, deployments: Deployments) -> dict:
    """The photos of a created deployment, to look at them: {"photos": [{"name", "taken"}]}."""
    return {"photos": _http(lambda: deployments.photos(research_project_id, collection, deployment_id))}


@router.get("/photo", response_model=None)
def deployment_photo(research_project_id: str, collection: str, deployment_id: str, name: str, deployments: Deployments, size: str = "thumb") -> Response:
    """A photo of a created deployment, as a JPEG: a thumbnail, or (size=large) one to look at closely."""
    body = _http(lambda: deployments.photo(research_project_id, collection, deployment_id, name, size == "large"))
    return Response(body, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})


# ── checking and repairing those kept (/api/repair), and the statistics of a revision (/api/statistics) ──

@repair_router.post("/collections")
def repair_collections(req: UploadCollectionsRequest, deployments: Deployments) -> dict:
    """The collections kept for a research project and the deployment folders in each, whatever state they are in."""
    return {"results": _http(lambda: deployments.repair_collections(req.research_project_id))}


@repair_router.post("/inspect")
def inspect(req: RepairRequest, deployments: Deployments) -> dict:
    """The state of a deployment — valid, or not, as its seal.json says — and what is wrong with it."""
    return _http(lambda: deployments.inspect(req.research_project_id, req.collection, req.deployment_id))


@repair_router.post("/deployment", response_model=None)
def repair(req: RepairRequest, deployments: Deployments) -> StreamingResponse:
    """Repairs a deployment: its metadata files are written again from what its folder holds. NDJSON: a {"type": "step"} per step and, last,
    {"type": "done", ...}; a failure midway is an {"type": "error", "detail"} line. One that isn't there or was synced from Trapper is a plain 4xx."""
    events = _http(lambda: deployments.repair(req.research_project_id, req.collection, req.deployment_id))
    return streaming.from_events(events, f"Repairing {req.deployment_id} failed")


@statistics_router.post("/revision")
def revision(req: StatisticsRequest, deployments: Deployments) -> dict:
    """One row per deployment of the revision: its metrics, what each check of POSTVALIDATION says of it, its status and the metrics of the
    previous revisions of its location."""
    return {"results": _http(lambda: deployments.revision_statistics(req.research_project_id, req.collection))}


# ── the sessions of the wizard (/api/sessions) ──

@sessions_router.get("")
def list_sessions(deployments: Deployments) -> list[dict]:
    """Unfinished runs, newest first — offered on startup to resume."""
    return deployments.sessions().list()


@sessions_router.post("/scan")
def save_scan(req: SaveScanRequest, deployments: Deployments) -> dict:
    """Saves the source folder and its scan result — the wizard's first step, so this creates the session on the first call."""
    return _http(lambda: deployments.sessions().save_scan(req.task_id, req.source_dir, req.scan.model_dump()))


@sessions_router.post("/selection")
def save_selection(req: SaveSelectionRequest, deployments: Deployments) -> dict:
    """Saves the chosen research project/classification project/location into an existing session."""
    return _http(lambda: deployments.sessions().save_selection(req.task_id, req.selection.model_dump()))


@sessions_router.post("/details")
def save_details(req: SaveDetailsRequest, deployments: Deployments) -> dict:
    """Saves the deployment's own fields into an existing session — the run is then ready to import."""
    return _http(lambda: deployments.sessions().save_details(req.task_id, req.deployment.model_dump()))


@sessions_router.delete("/{task_id}")
def discard(task_id: str, deployments: Deployments) -> dict:
    _http(lambda: deployments.sessions().discard(task_id))
    return {"status": "discarded"}
