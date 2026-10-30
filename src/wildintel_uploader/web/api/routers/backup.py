"""FastAPI router — backups of the settings and of the data of the research projects, and their restoration (see services.backup_service)."""
from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from wildintel_uploader.core import config
from wildintel_uploader.core.logging_setup import debugging
from wildintel_uploader.core.services import backup_service, folder_picker
from wildintel_uploader.core.version import current_version

router = APIRouter(prefix="/api/backup", tags=["backup"])
logger = logging.getLogger(__name__)


class ProjectInfoRequest(BaseModel):
    research_project_id: str


class CreateBackupRequest(BaseModel):
    dest_dir: str
    settings: bool = False
    research_project_id: str | None = None
    project_files: bool = False
    visits: bool = False
    deployments: list[str] = Field(default_factory=list)
    images: bool = False


class ReadBackupRequest(BaseModel):
    path: str


class RestoreRequest(BaseModel):
    path: str
    settings: bool = False
    project_files: bool = False
    visits: bool = False
    deployments: list[str] = Field(default_factory=list)
    images: bool = False
    replace: bool = False


@router.post("/pick-file")
def pick_file() -> dict:
    """Opens the OS's native file dialog on the machine running the backend, for a backup (.zip): {"path": ...}, or {"path": None} if cancelled."""
    try:
        return {"path": folder_picker.pick_file("Select the backup", "zip")}
    except folder_picker.FolderPickerUnavailable as exc:
        raise HTTPException(501, str(exc)) from exc


@router.post("/project-info")
def project_info(req: ProjectInfoRequest) -> dict:
    """What a research project has that can be put in a backup: its counts, and its deployments by collection, with their files and bytes."""
    try:
        return backup_service.describe_project(config.collections_dir(), req.research_project_id)
    except backup_service.BackupError as exc:
        raise HTTPException(400, str(exc)) from exc


def _stream(events: Iterator[dict], what: str) -> StreamingResponse:
    def lines() -> Iterator[str]:
        try:
            for event in events:
                yield json.dumps(event) + "\n"
        except backup_service.BackupError as exc:
            yield json.dumps({"type": "error", "detail": str(exc)}) + "\n"
        except Exception as exc:
            logger.warning("%s failed: %s", what, exc, exc_info=debugging())
            yield json.dumps({"type": "error", "detail": f"{what} failed: {exc}"}) + "\n"

    return StreamingResponse(lines(), media_type="application/x-ndjson")


@router.post("/create")
def create(req: CreateBackupRequest) -> StreamingResponse:
    """Makes a backup in a folder. Answers NDJSON: a {"type": "step"} or {"type": "file"} per step, then {"type": "done", "path", "bytes", "manifest"}; a failure
    midway is an {"type": "error", "detail"} line. What cannot be made at all (nothing chosen, a folder that is not there) is a plain 400, before anything is written."""
    try:
        events = backup_service.create_backup(
            config.collections_dir(), Path(req.dest_dir).expanduser(), settings=req.settings, research_project_id=req.research_project_id, project_files=req.project_files,
            visits=req.visits, deployments=req.deployments, images=req.images, app_version=current_version(),
        )
        first = next(events)
    except backup_service.BackupError as exc:
        raise HTTPException(400, str(exc)) from exc

    def chained() -> Iterator[dict]:
        yield first
        yield from events

    return _stream(chained(), "The backup")


@router.post("/read")
def read(req: ReadBackupRequest) -> dict:
    """What a backup holds — its manifest — and what of it is already here, to choose what to restore."""
    try:
        return backup_service.read_backup(config.collections_dir(), Path(req.path).expanduser())
    except backup_service.BackupError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/restore")
def restore(req: RestoreRequest) -> StreamingResponse:
    """Restores what is picked of a backup. Answers NDJSON like /create: steps, files, and last {"type": "done", "summary"}; what cannot be restored at all is a
    plain 400, before anything is touched."""
    try:
        events = backup_service.restore_backup(
            config.collections_dir(), Path(req.path).expanduser(), settings=req.settings, project_files=req.project_files, visits=req.visits,
            deployments=req.deployments, images=req.images, replace=req.replace,
        )
        first = next(events)
    except backup_service.BackupError as exc:
        raise HTTPException(400, str(exc)) from exc
    except StopIteration:
        first = {"type": "done", "summary": {}}

    def chained() -> Iterator[dict]:
        yield first
        yield from events

    return _stream(chained(), "The restoration")
