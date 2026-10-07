"""FastAPI router — checking and repairing the deployments kept in the collections folder (see services.repair_service)."""
from __future__ import annotations

import json
import logging
from collections.abc import Iterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from wildintel_uploader.core import config
from wildintel_uploader.core.logging_setup import debugging
from wildintel_uploader.core.schemas.requests import RepairRequest, UploadCollectionsRequest
from wildintel_uploader.core.services import deployment_import_service, local_folder_service, repair_service

router = APIRouter(prefix="/api/repair", tags=["repair"])
logger = logging.getLogger(__name__)


@router.post("/collections")
def collections(req: UploadCollectionsRequest) -> dict:
    """The collections kept for a research project and the deployment folders in each, whatever state they are in."""
    try:
        return {"results": repair_service.list_collections(config.collections_dir(), req.research_project_id)}
    except repair_service.RepairError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/inspect")
def inspect(req: RepairRequest) -> dict:
    """The state of a deployment — valid, or not, as its seal.json says — and what is wrong with it (see repair_service.inspect)."""
    try:
        return repair_service.inspect(config.collections_dir(), req.research_project_id, req.collection, req.deployment_id)
    except repair_service.RepairError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/deployment")
def repair(req: RepairRequest) -> StreamingResponse:
    """Repairs a deployment: its metadata files are written again from what its folder holds. Answers NDJSON: a {"type": "step"} per
    step and, last, {"type": "done", ...}; a failure midway is an {"type": "error", "detail"} line, as the 200 is already sent by
    then. A deployment that isn't there or was synced from Trapper is a plain 4xx, before anything is touched."""
    try:
        events = repair_service.repair_stream(config.collections_dir(), req.research_project_id, req.collection, req.deployment_id)
    except repair_service.RepairError as exc:
        raise HTTPException(400, str(exc)) from exc

    def lines() -> Iterator[str]:
        try:
            for event in events:
                yield json.dumps(event) + "\n"
        except (repair_service.RepairError, local_folder_service.LocalFolderError, deployment_import_service.DeploymentImportError) as exc:
            yield json.dumps({"type": "error", "detail": str(exc)}) + "\n"
        except Exception as exc:
            logger.warning("Repairing %s failed: %s", req.deployment_id, exc, exc_info=debugging())
            yield json.dumps({"type": "error", "detail": f"The repair failed: {exc}"}) + "\n"

    return StreamingResponse(lines(), media_type="application/x-ndjson")
