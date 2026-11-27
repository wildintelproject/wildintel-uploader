"""FastAPI router — the prevalidation (module `modules.prevalidation`): the checks of the images of a folder, at the addresses the pages have always
used (/api/deployment-import/validate-images, and /stream to follow them as they run). What it refuses is a 400."""
from __future__ import annotations

from pathlib import Path

from dishka.integrations.fastapi import DishkaSyncRoute, FromDishka
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from wildintel_uploader.entrypoints.api import streaming
from wildintel_uploader.modules.prevalidation.domain.models import PrevalidationError
from wildintel_uploader.modules.prevalidation.domain.ports import PrevalidationService
from wildintel_uploader.modules.prevalidation.infrastructure.api_schemas import ValidateImagesRequest

router = APIRouter(prefix="/api/deployment-import", tags=["prevalidation"], route_class=DishkaSyncRoute)
Prevalidation = FromDishka[PrevalidationService]


def _checks(req: ValidateImagesRequest) -> frozenset[str] | None:
    return frozenset(req.checks) if req.checks is not None else None


@router.post("/validate-images")
def validate_images(req: ValidateImagesRequest, prevalidation: Prevalidation) -> dict:
    """The checks of the images of a folder asked for — corrupted files, the order of the shots, subfolders, one camera, the EXIF fields,
    duplicates — with the id of their report."""
    try:
        return prevalidation.check_folder(Path(req.path).expanduser(), _checks(req), research_project_id=req.research_project_id,
                                          deployment_id=req.deployment_id)
    except PrevalidationError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/validate-images/stream")
def validate_images_stream(req: ValidateImagesRequest, prevalidation: Prevalidation) -> StreamingResponse:
    """The same checks as /validate-images, told as NDJSON while they run: {"type": "check", "check", "state"} when each starts ("running") and
    ends ("done"), {"type": "progress", "step", "done", "total"} (at most a few a second, and the last of each step) and, at the end,
    {"type": "done", "result": <what /validate-images answers>}. A failure is {"type": "error", "detail"}."""
    source = Path(req.path).expanduser()
    if not source.is_dir():
        raise HTTPException(400, f"Not a folder: {source}")
    return streaming.from_work(lambda tell: prevalidation.check_folder(
        source, _checks(req), research_project_id=req.research_project_id, deployment_id=req.deployment_id,
        progress=streaming.throttled(tell), on_check=streaming.checks_told(tell)), "Validating the images failed")
