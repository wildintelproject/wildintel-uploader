"""FastAPI router — the settings themselves (module `modules.settings`): the configs the user can switch to, the welcome page and the data folder.

It only translates: a request into a call to the contract of the module (`domain.ports.SettingsService`), and its answer or its error into HTTP. What the settings
page reads and saves all at once (GET and PUT /api/settings) is still `web/api/routers/app_settings.py`: it also moves the cameras, the SD cards and the
trappers to the research projects, and goes with them."""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from dishka.integrations.fastapi import DishkaSyncRoute, FromDishka
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from wildintel_uploader.core.services import file_manager
from wildintel_uploader.modules.settings.domain.models import SettingsError
from wildintel_uploader.modules.settings.domain.ports import NoSettingsFile, SettingsService, UnknownConfig

# Each endpoint is given what it asks for as FromDishka[...] by the container of entrypoints.wiring, in a scope of its own for each request.
router = APIRouter(prefix="/api/settings", tags=["settings"], route_class=DishkaSyncRoute)

Service = FromDishka[SettingsService]


def _config_file(service: SettingsService, config_id: str) -> Path:
    try:
        return service.config_file(config_id)
    except UnknownConfig:
        raise HTTPException(404, f"There's no config {config_id!r}.") from None
    except NoSettingsFile:
        raise HTTPException(404, "There's no settings file yet.") from None


# ── the configs ──

class NewConfigRequest(BaseModel):
    name: str


@router.get("/configs")
def get_configs(service: Service) -> list[dict]:
    """Every settings file the user can switch to, the one in use flagged."""
    return [asdict(c) for c in service.list_configs()]


@router.post("/configs")
def add_config(req: NewConfigRequest, service: Service) -> list[dict]:
    """A new settings file with the default values (it doesn't become the active one), and the list of them."""
    try:
        return [asdict(c) for c in service.create_config(req.name)]
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/configs/{config_id}/activate")
def activate_config(config_id: str, service: Service) -> list[dict]:
    """Makes `config_id` the settings file the whole app reads and saves."""
    try:
        return [asdict(c) for c in service.activate_config(config_id)]
    except UnknownConfig:
        raise HTTPException(404, f"There's no config {config_id!r}.") from None


@router.get("/configs/{config_id}/download")
def download_config(config_id: str, service: Service) -> FileResponse:
    """The settings file itself, as saved — passwords included, since it's a backup of the file; it's the user's own file, on their own machine."""
    path = _config_file(service, config_id)
    return FileResponse(path, media_type="application/toml", filename=path.name)


@router.post("/configs/{config_id}/open-folder")
def open_config_folder(config_id: str, service: Service) -> dict:
    """Opens the folder of that settings file in the OS's file manager."""
    path = _config_file(service, config_id)
    try:
        file_manager.open_folder(path.parent)
    except OSError as exc:
        raise HTTPException(500, f"Could not open the folder: {exc}") from exc
    return {"ok": True}


# ── what the app changes on its own ──

class ShowWelcomeRequest(BaseModel):
    show: bool


@router.put("/show-welcome")
def set_show_welcome(req: ShowWelcomeRequest, service: Service) -> dict:
    """Changes only whether the welcome page is shown when the app opens — what its tick does."""
    return {"show_welcome": service.set_show_welcome(req.show).general.show_welcome}


class DataDirRequest(BaseModel):
    dir: str | None = None


@router.put("/data-dir")
def set_data_dir(req: DataDirRequest, service: Service) -> dict:
    """Changes only the data folder — what the initial setup asks for. Blank is the default one. What is kept in the old one is not moved, and the
    folders that were inside it go inside the new one."""
    try:
        return {"dir": str(service.set_data_dir(req.dir))}
    except SettingsError:
        raise HTTPException(422, "The data folder must be an absolute path (or one starting with ~).") from None
