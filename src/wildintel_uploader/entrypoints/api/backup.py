"""FastAPI router — backups of the settings and of the data of the research projects, and their restoration (module `modules.backup`), at
/api/backup as always. What can't be done at all is a 400, before anything is written; a backup that is not there, a 404."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from dishka.integrations.fastapi import DishkaSyncRoute, FromDishka
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from wildintel_uploader.shared.desktop import folder_picker
from wildintel_uploader.entrypoints.api import streaming
from wildintel_uploader.modules.backup.domain.ports import BackupError, BackupGone, BackupService, Choice
from wildintel_uploader.modules.backup.infrastructure.api_schemas import CreateBackupRequest, ProjectInfoRequest, ReadBackupRequest, RestoreRequest

router = APIRouter(prefix="/api/backup", tags=["backup"], route_class=DishkaSyncRoute)
Backups = FromDishka[BackupService]
T = TypeVar("T")


def _http(call: Callable[[], T]) -> T:
    try:
        return call()
    except BackupError as exc:
        raise HTTPException(404 if isinstance(exc, BackupGone) else 400, str(exc)) from exc


@router.post("/pick-file")
def pick_file() -> dict:
    """Opens the OS's native file dialog on the machine running the backend, for a backup (.zip): {"path": ...}, or {"path": None} if cancelled."""
    try:
        return {"path": folder_picker.pick_file("Select the backup", "zip")}
    except folder_picker.FolderPickerUnavailable as exc:
        raise HTTPException(501, str(exc)) from exc


@router.post("/project-info")
def project_info(req: ProjectInfoRequest, backups: Backups) -> dict:
    """What a research project has that can be put in a backup: its counts, and its deployments by collection, with their files and bytes."""
    return _http(lambda: backups.describe(req.research_project_id))


@router.post("/create")
def create(req: CreateBackupRequest, backups: Backups) -> StreamingResponse:
    """Makes a backup in a folder — or to be downloaded. NDJSON: a {"type": "step"} or {"type": "file"} per step, then {"type": "done", "path",
    "bytes", "manifest"}; a failure midway is an {"type": "error", "detail"} line."""
    choice = Choice(settings=req.settings, project_files=req.project_files, visits=req.visits, deployments=req.deployments, images=req.images)
    dest = Path(req.dest_dir).expanduser() if req.dest_dir is not None else None
    return streaming.from_events(_http(lambda: backups.create(dest, req.research_project_id, choice)), "The backup")


@router.get("/download/{name}")
def download(name: str, backups: Backups) -> FileResponse:
    """A backup made to be downloaded: the browser gets it as a file to save. Only the backups made there are served."""
    path = _http(lambda: backups.download(name))
    return FileResponse(path, media_type="application/zip", filename=name)


@router.post("/read")
def read(req: ReadBackupRequest, backups: Backups) -> dict:
    """What a backup holds — its manifest — and what of it is already here, to choose what to restore."""
    return _http(lambda: backups.read(Path(req.path).expanduser()))


@router.post("/restore")
def restore(req: RestoreRequest, backups: Backups) -> StreamingResponse:
    """Restores what is picked of a backup. NDJSON like /create: steps, files, and last {"type": "done", "summary"}."""
    choice = Choice(settings=req.settings, project_files=req.project_files, visits=req.visits, deployments=req.deployments, images=req.images)
    return streaming.from_events(_http(lambda: backups.restore(Path(req.path).expanduser(), choice, req.replace)), "The restoration")
