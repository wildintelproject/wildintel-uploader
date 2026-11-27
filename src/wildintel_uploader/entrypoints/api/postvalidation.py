"""FastAPI router — the postvalidation (module `modules.postvalidation`): the checks of a deployment against its images, wildintel-tools' names,
its visit and the previous revisions of its location, at the addresses the pages have always used (/api/deployment-import/validate-deployment, and
/stream to follow them as they run). What it refuses is a 400."""
from __future__ import annotations

from pathlib import Path

from dishka.integrations.fastapi import DishkaSyncRoute, FromDishka
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from wildintel_uploader.entrypoints.api import streaming
from wildintel_uploader.modules.postvalidation.domain.models import Deployment, DeploymentContext, PostvalidationError
from wildintel_uploader.modules.postvalidation.domain.ports import PostvalidationService
from wildintel_uploader.modules.postvalidation.infrastructure.api_schemas import ValidateDeploymentRequest

router = APIRouter(prefix="/api/deployment-import", tags=["postvalidation"], route_class=DishkaSyncRoute)
Postvalidation = FromDishka[PostvalidationService]


def _context(req: ValidateDeploymentRequest) -> DeploymentContext:
    d = req.deployment
    return DeploymentContext(
        deployment=Deployment(deployment_id=d.deployment_id, start_date=d.start_date, end_date=d.end_date, camera_model=d.camera_model, camera_id=d.camera_id),
        collection=req.collection_name, expected_location_id=req.expected_location_id, tolerance_hours=req.tolerance_hours,
        visit=req.visit.model_dump() if req.visit else None, research_project_id=req.research_project_id, statistics=req.statistics.model_dump())


def _checks(req: ValidateDeploymentRequest) -> frozenset[str] | None:
    return frozenset(req.checks) if req.checks is not None else None


@router.post("/validate-deployment")
def validate_deployment(req: ValidateDeploymentRequest, postvalidation: Postvalidation) -> dict:
    """The checks of a deployment asked for, the statistical ones last, with the id of their report."""
    try:
        return postvalidation.check_deployment(Path(req.path).expanduser(), _context(req), _checks(req))
    except PostvalidationError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/validate-deployment/stream", response_model=None)
def validate_deployment_stream(req: ValidateDeploymentRequest, postvalidation: Postvalidation) -> StreamingResponse:
    """The same checks as /validate-deployment, told as NDJSON while they run: {"type": "check", "check", "state"} when each starts ("running") and
    ends ("done") and, at the end, {"type": "done", "result": <what /validate-deployment answers>}. A failure is {"type": "error", "detail"}."""
    source = Path(req.path).expanduser()
    if not source.is_dir():
        raise HTTPException(400, f"Not a folder: {source}")
    return streaming.from_work(lambda tell: postvalidation.check_deployment(source, _context(req), _checks(req), on_check=streaming.checks_told(tell)),
                               "Checking the deployment failed")
