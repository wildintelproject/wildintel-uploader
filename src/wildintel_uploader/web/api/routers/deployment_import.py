"""FastAPI router — importing a deployment: scan a local folder for a
starting point (dates, camera model), then organize it and register the
deployment in Trapper, both as one streamed operation (see
services.deployment_import_service)."""
from __future__ import annotations

import json
import logging
from collections.abc import Iterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from wildintel_uploader.core import config
from wildintel_uploader.core.logging_setup import debugging
from wildintel_uploader.core.schemas.requests import (
    ImportDeploymentRequest,
)
from wildintel_uploader.core.services import deployment_import_service, local_folder_service
from wildintel_uploader.web.api.routers.trapper import http_exc, resolve

router = APIRouter(prefix="/api/deployment-import", tags=["deployment-import"])
logger = logging.getLogger(__name__)


def _location_time(research_project_id: str | None, location_id: str | None) -> dict:
    """The kept location's timezone and summer-time setting — the only source of them, whatever the request carries."""
    if not research_project_id:
        return {}
    try:
        return local_folder_service.location_time(config.collections_dir(), research_project_id, location_id)
    except local_folder_service.LocalFolderError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/import")
def import_deployment(req: ImportDeploymentRequest) -> StreamingResponse:
    """The import's events, as NDJSON:
      - {"type": "copy", "index", "total", "name"}: one file organized.
      - {"type": "registering"}: local copy done, registering with Trapper.
      - {"type": "done", "dest_dir"}: the deployment is in Trapper.
      - {"type": "error", "detail"}: something failed midway (the 200 is
        already sent by then — files already copied are left in place).

    Bad source/destination paths are a plain 400, checked before any file
    is touched."""
    url, username, password = resolve(req)
    time = _location_time(req.research_project_id, req.deployment.location_id)
    try:
        events = deployment_import_service.import_stream(
            url, username, password, req.research_project_pk, req.classification_project_pk,
            req.source_dir, req.deployment, time.get("timezone"),
            research_project_id=req.research_project_id, ignore_dst=time.get("ignore_dst", False), register=req.register_deployment,
        )
    except deployment_import_service.DeploymentImportError as exc:
        raise HTTPException(400, str(exc)) from exc

    def lines() -> Iterator[str]:
        try:
            for event in events:
                yield json.dumps(event) + "\n"
        except Exception as exc:
            logger.warning("Deployment import failed: %s", exc, exc_info=debugging())
            yield json.dumps({"type": "error", "detail": http_exc(exc).detail}) + "\n"
            return

    return StreamingResponse(lines(), media_type="application/x-ndjson")


