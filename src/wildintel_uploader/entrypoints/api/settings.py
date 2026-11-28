"""FastAPI router — the settings themselves (module `modules.settings`): the configs the user can switch to (the Config section of the settings page),
the General section — its settings, the folders, what the system says, the log —, each section of settings.toml on its own (TRAPPER, AGOUTI,
EPICOLLECT5, VALIDATION…), the welcome page and the data folder.

It only translates: a request into a call to the contract of the module (`domain.ports.SettingsService`), and its answer or its error into HTTP. What the settings
page reads and saves all at once (GET and PUT /api/settings) is `entrypoints/api/settings_page.py`: it also moves the cameras, the SD cards and the
trappers to the research projects, and goes with them."""
from __future__ import annotations

from pathlib import Path
from typing import Any
from dishka.integrations.fastapi import DishkaSyncRoute, FromDishka
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from wildintel_uploader.shared.desktop import file_manager
from wildintel_uploader.modules.settings.domain.models import DataSettings, GeneralSettings, SettingsError
from wildintel_uploader.modules.settings.infrastructure.api_schemas import (
    ConfigShown, DataDirRequest, FoldersRequest, GeneralRequest, GeneralShown, LogDeleted, NewConfigRequest, SectionShown, ShowWelcomeRequest,
)
from wildintel_uploader.modules.settings.domain.ports import NoLogFile, NoSettingsFile, SettingsService, UnknownConfig, UnknownSetting

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

@router.get("/configs", response_model=list[ConfigShown])
def get_configs(service: Service) -> list[ConfigShown]:
    """Every settings file the user can switch to, the one in use flagged."""
    return [ConfigShown.of(c) for c in service.list_configs()]


@router.post("/configs", response_model=list[ConfigShown])
def add_config(req: NewConfigRequest, service: Service) -> list[ConfigShown]:
    """A new settings file with the default values (it doesn't become the active one), and the list of them."""
    try:
        return [ConfigShown.of(c) for c in service.create_config(req.name)]
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/configs/{config_id}/activate", response_model=list[ConfigShown])
def activate_config(config_id: str, service: Service) -> list[ConfigShown]:
    """Makes `config_id` the settings file the whole app reads and saves."""
    try:
        return [ConfigShown.of(c) for c in service.activate_config(config_id)]
    except UnknownConfig:
        raise HTTPException(404, f"There's no config {config_id!r}.") from None


@router.get("/configs/{config_id}/download", response_model=None)
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

@router.put("/show-welcome")
def set_show_welcome(req: ShowWelcomeRequest, service: Service) -> dict:
    """Changes only whether the welcome page is shown when the app opens — what its tick does."""
    return {"show_welcome": service.set_show_welcome(req.show).general.show_welcome}


@router.put("/data-dir")
def set_data_dir(req: DataDirRequest, service: Service) -> dict:
    """Changes only the data folder — what the initial setup asks for. Blank is the default one. What is kept in the old one is not moved, and the
    folders that were inside it go inside the new one."""
    try:
        return {"dir": str(service.set_data_dir(req.dir))}
    except SettingsError:
        raise HTTPException(422, "The data folder must be an absolute path (or one starting with ~).") from None


# ── the General section ──

@router.get("/general", response_model=GeneralShown)
def get_general(service: Service) -> GeneralShown:
    """The General section: {"general": its settings, "folders": the folders and the default of each, "system": the CPUs, the log file and a level
    the environment forces}."""
    return GeneralShown.of(service.general())


@router.put("/general", response_model=GeneralShown)
def save_general(req: GeneralRequest, service: Service) -> GeneralShown:
    """Saves the General section, and the level of the log applies at once. A setting that cannot be is a 422 that names it."""
    folders = req.folders.model_dump() if req.folders else {k: getattr(service.general().folders, k) for k in FoldersRequest.model_fields}
    try:
        general = GeneralSettings(log_level=req.log_level, workers=req.workers, default_research_project=req.default_research_project,
                                  show_welcome=req.show_welcome)
        return GeneralShown.of(service.save_general(general, DataSettings(**folders)))
    except SettingsError as exc:
        raise HTTPException(422, {"setting": exc.setting, "message": exc.message}) from exc


@router.get("/log", response_model=None)
def download_log(service: Service) -> FileResponse:
    """The current log file — to attach to a bug report."""
    try:
        path = service.log_file()
    except NoLogFile:
        raise HTTPException(404, "There's no log file yet.") from None
    return FileResponse(path, media_type="text/plain", filename=path.name)


@router.delete("/log", response_model=LogDeleted)
def delete_log(service: Service) -> LogDeleted:
    """Deletes the log file and its rotated copies — logging goes on, into a new one."""
    return LogDeleted(deleted=service.clear_log())


# ── each section ──

@router.get("/sections/{section}", response_model=SectionShown)
def get_section(section: str, service: Service) -> SectionShown:
    """One section of the settings — TRAPPER, AGOUTI, EPICOLLECT5, VALIDATION… —: {"section", "values" (the secrets left out), "secrets" (whether each
    is saved)}."""
    try:
        return SectionShown.of(service.section(section))
    except UnknownSetting:
        raise HTTPException(404, f"There's no section {section!r}.") from None


@router.put("/sections/{section}", response_model=SectionShown)
def save_section(section: str, values: dict[str, Any], service: Service) -> SectionShown:
    """Changes the settings of one section that the body names — the rest stays. A secret left blank keeps the saved one. A setting that is not one
    is a 404; a value it does not take, a 422 that names it."""
    try:
        return SectionShown.of(service.save_section(section, values))
    except UnknownSetting as exc:
        raise HTTPException(404, f"There's no setting {exc.args[0]!r}.") from None
    except SettingsError as exc:
        raise HTTPException(422, {"setting": exc.setting, "message": exc.message}) from exc
