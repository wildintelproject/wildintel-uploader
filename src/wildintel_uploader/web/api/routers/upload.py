"""FastAPI router — uploading the deployments kept in the collections folder to Trapper
(see services.trapper_upload_service)."""
from __future__ import annotations

import json
import logging
from collections.abc import Iterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from wildintel_uploader.core import config
from wildintel_uploader.core.logging_setup import debugging
from wildintel_uploader.core.schemas.requests import UploadCollectionsRequest, UploadDeploymentRequest
from wildintel_uploader.core.services import local_folder_service, trapper_service, trapper_upload_service
from wildintel_uploader.web.api.routers.trapper import http_exc, resolve

router = APIRouter(prefix="/api/upload", tags=["upload"])
logger = logging.getLogger(__name__)


@router.post("/collections")
def collections(req: UploadCollectionsRequest) -> dict:
    """The collections kept for a research project, and the deployments in each — what can be uploaded."""
    try:
        return {"results": trapper_upload_service.list_collections(config.collections_dir(), req.research_project_id)}
    except local_folder_service.LocalFolderError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/deployment")
def upload_deployment(req: UploadDeploymentRequest) -> StreamingResponse:
    """Uploads one deployment, as NDJSON events (see trapper_upload_service.upload_stream) — creating
    its location and the deployment in Trapper if they aren't there, packing its images and sending the
    package. A failure midway is an {"type": "error", "detail"} line: the 200 is already sent by then.

    What can be checked first (the credentials, the research project and the collection being kept
    locally) is a plain 4xx, before anything is touched."""
    # Generating the files needs no account when the research project's pk in Trapper is already known.
    credentials = None
    if req.mode == "generate":
        try:
            credentials = trapper_service.resolve_credentials(req.url, req.username, req.password)
        except ValueError:
            credentials = None
    else:
        credentials = resolve(req)
    try:
        records = {p["acronym"]: p for p in local_folder_service.list_research_projects(config.collections_dir())}
        record = records.get(req.research_project_id)
        if record is None:
            raise HTTPException(404, f"The research project '{req.research_project_id}' isn't in the collections folder.")
        collection_dir = local_folder_service.project_dir(config.collections_dir(), req.research_project_id) / req.collection
    except local_folder_service.LocalFolderError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not (collection_dir / req.deployment_id).is_dir():
        raise HTTPException(404, f"{req.deployment_id} isn't in the collection {req.collection}.")

    events = trapper_upload_service.upload_stream(
        credentials, record, collection_dir, req.deployment_id, config.data_dir() / "packages" / req.research_project_id,
        mode=req.mode, max_zip_bytes=req.max_zip_mb * 1024 * 1024,
    )

    def lines() -> Iterator[str]:
        try:
            for event in events:
                yield json.dumps(event) + "\n"
        except Exception as exc:
            logger.warning("Uploading %s failed: %s", req.deployment_id, exc, exc_info=debugging())
            detail = str(exc) if isinstance(exc, trapper_upload_service.TrapperUploadError) else http_exc(exc).detail
            yield json.dumps({"type": "error", "detail": detail}) + "\n"

    return StreamingResponse(lines(), media_type="application/x-ndjson")
