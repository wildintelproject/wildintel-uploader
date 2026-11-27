"""FastAPI router — what the app asks of the computer it runs on: its folder picker, its file explorer, whether ExifTool is installed. No module of
its own: these are the adapters of the system, used as they are, at the addresses the pages have always used (/api/deployment-import/…)."""
from __future__ import annotations

from pathlib import Path

from dishka.integrations.fastapi import DishkaSyncRoute, FromDishka
from fastapi import APIRouter, HTTPException

from wildintel_uploader.core import config
from wildintel_uploader.shared.desktop import file_manager
from wildintel_uploader.shared.desktop import folder_picker
from wildintel_uploader.modules.deployments.infrastructure.api_schemas import BrowseFolderRequest, OpenFolderRequest
from wildintel_uploader.modules.fileinfo.domain.ports import FileInfoService

router = APIRouter(prefix="/api/deployment-import", tags=["desktop"], route_class=DishkaSyncRoute)


@router.post("/browse-folder")
def browse_folder(req: BrowseFolderRequest = BrowseFolderRequest()) -> dict:
    """Opens the OS's native folder picker on the machine running the backend (always the user's own) and returns {"path": ...}, or
    {"path": None} if cancelled."""
    try:
        path = folder_picker.pick_folder(req.title or "Select the deployment's images folder")
    except folder_picker.FolderPickerUnavailable as exc:
        raise HTTPException(501, str(exc)) from exc
    return {"path": path}


@router.get("/exiftool")
def exiftool(files: FromDishka[FileInfoService]) -> dict:
    """Whether ExifTool is installed — the preprocessing's metadata needs it (what is known of the files says where it is)."""
    path = files.exiftool_path()
    return {"available": path is not None, "path": path}


def _open_in_file_manager(path: Path) -> None:
    """Opens a folder in the system's file explorer (a seam the tests replace)."""
    file_manager.open_folder(path)


@router.post("/open-folder")
def open_folder(req: OpenFolderRequest) -> dict:
    """Opens a folder kept by the app (inside its data folder, or its collections, reports or packages folder — nothing else) in the file explorer."""
    target = Path(req.path).expanduser().resolve()
    roots = [d.resolve() for d in (config.data_dir(), config.collections_dir(), config.reports_dir(), config.packages_dir())]
    if not any(root == target or root in target.parents for root in roots):
        raise HTTPException(400, "Only folders inside the app's data folder, or its collections, reports or packages folder, can be opened.")
    if not target.is_dir():
        raise HTTPException(404, "That folder does not exist.")
    try:
        _open_in_file_manager(target)
    except OSError as exc:
        raise HTTPException(500, f"Could not open the file explorer: {exc}") from exc
    return {"opened": str(target)}
