"""FastAPI router — syncing the local collections folder with Trapper (see services.sync_service)."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from wildintel_uploader.core import config
from wildintel_uploader.core.logging_setup import debugging
from wildintel_uploader.core.schemas.requests import SyncCollectionsRequest
from wildintel_uploader.core.services import deployment_import_service, local_folder_service, sync_service
from wildintel_uploader.web.api.routers.trapper import http_exc, resolve

router = APIRouter(prefix="/api/sync", tags=["sync"])
logger = logging.getLogger(__name__)


@router.post("/collections")
def sync_collections(req: SyncCollectionsRequest) -> dict:
    """Creates in the collections folder what Trapper has for the classification project and it lacks — the research
    project, its locations, the collections starting with R and, in each, its timestamp log and its deployments.
    What is already there is kept as it is. Returns what was created and what was kept."""
    credentials = resolve(req)
    project = {"pk": req.research_project_pk, "name": req.research_project_name, "acronym": req.research_project_acronym}
    try:
        return sync_service.sync(credentials, config.collections_dir(), project, req.classification_project_pk)
    except (local_folder_service.LocalFolderError, deployment_import_service.DeploymentImportError) as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        logger.warning("Syncing the local collections failed: %s", exc, exc_info=debugging())
        raise http_exc(exc) from exc
