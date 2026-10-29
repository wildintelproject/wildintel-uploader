"""FastAPI router — the app's own settings.toml (see config.py), edited on
the settings page. The password never goes back to the frontend: TRAPPER
says whether one is saved instead, and saving a blank one keeps it."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from wildintel_uploader.core import config
from wildintel_uploader.core import logging_setup
from wildintel_uploader.core.services import file_manager, local_folder_service

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _public(settings: config.Settings) -> dict:
    data = settings.model_dump(mode="json")
    data["TRAPPER"]["has_password"] = bool(data["TRAPPER"].pop("user_password"))
    data["EPICOLLECT5"]["has_secret"] = bool(data["EPICOLLECT5"].pop("client_secret"))
    data["DATA"]["dir"] = data["DATA"]["dir"] or str(config.default_data_dir())
    # What the collections folder is when no folder of its own is set — shown as the default.
    for key in ("collections", "reports", "packages"):
        data["DATA"][f"default_{key}_dir"] = str(config.data_dir(settings) / key)
    # Read-only: where the log goes, and whether the environment overrides
    # the level set here.
    data["GENERAL"]["log_file"] = str(logging_setup.log_file())
    data["GENERAL"]["log_level_override"] = logging_setup.env_override()
    data["GENERAL"]["cpu_count"] = os.cpu_count() or 1
    return data


def _root(settings: config.Settings):
    return config.collections_dir(settings)


def _shown(settings: config.Settings) -> dict:
    """The settings as the page has them: the cameras and the SD cards are those of the research projects, in their folders of the collections folder."""
    root = _root(settings)
    data = _public(settings)
    for kind in ("cameras", "sd_cards"):
        # what is still in the settings file belongs to a research project that is not in the collections folder (yet)
        data["FIELDWORK"][kind] = [i.model_dump(mode="json") if hasattr(i, "model_dump") else i for i in local_folder_service.list_all_field_items(root, kind)] + data["FIELDWORK"][kind]
    return data


def _move_to_the_projects(settings: config.Settings) -> config.Settings:
    """Cameras and SD cards kept in settings.toml (as they were before) go to the folder of their research project, as a file of its own: the ones that are a
    research project's, to it. What can't be moved stays: the ones whose project isn't in the collections folder yet, and the ones that belong to none — a camera
    or an SD card belongs to one research project, so those wait to be assigned to one in the settings. Does nothing once there is nothing left to move."""
    fieldwork = settings.FIELDWORK
    if not fieldwork.cameras and not fieldwork.sd_cards:
        return settings
    root = _root(settings)
    projects = [p["acronym"] for p in local_folder_service.list_research_projects(root)]
    leftovers: dict[str, list] = {"cameras": [], "sd_cards": []}
    for kind in ("cameras", "sd_cards"):
        label = {"cameras": "label", "sd_cards": "label"}[kind]
        for project in projects:
            mine = [i for i in getattr(fieldwork, kind) if (i.research_project or "").lower() == project.lower()]
            if not mine:
                continue
            kept = local_folder_service.list_field_items(root, project, kind)
            have = {str(i.get(label, "")).lower() for i in kept}
            added = [i.model_dump(mode="json") for i in mine if i.label.lower() not in have]
            local_folder_service.write_field_items(root, project, kind, [*kept, *added])
        leftovers[kind] = [i for i in getattr(fieldwork, kind) if (i.research_project or "").lower() not in {p.lower() for p in projects}]
    if (leftovers["cameras"], leftovers["sd_cards"]) != (fieldwork.cameras, fieldwork.sd_cards):
        fieldwork.cameras, fieldwork.sd_cards = leftovers["cameras"], leftovers["sd_cards"]
        config.save_settings(settings)
    return settings


@router.get("")
def get_settings() -> dict:
    return _shown(_move_to_the_projects(config.load_settings()))


@router.put("")
def save_settings(new: config.Settings) -> dict:
    """Replaces every setting — except a password left blank, which keeps
    the saved one. Blank URL/username are cleared."""
    current = config.load_settings()
    if not new.TRAPPER.user_password:
        new.TRAPPER.user_password = current.TRAPPER.user_password
    if not new.EPICOLLECT5.client_secret:
        new.EPICOLLECT5.client_secret = current.EPICOLLECT5.client_secret
    for section, fields in ((new.TRAPPER, ("base_url", "user_name")), (new.EPICOLLECT5, ("project_slug", "client_id"))):
        for field in fields:
            if not getattr(section, field):
                setattr(section, field, None)
    root = _root(new)
    for kind in ("cameras", "sd_cards"):
        items = getattr(new.FIELDWORK, kind)
        free = [i for i in items if not i.research_project]
        if free:
            raise HTTPException(422, f"{'A camera' if kind == 'cameras' else 'An SD card'} belongs to a research project: choose one for {free[0].label}.")
        by_project: dict[str, list] = {}
        for item in items:
            by_project.setdefault(item.research_project, []).append(item.model_dump(mode="json"))
        known = {p["acronym"] for p in local_folder_service.list_research_projects(root)}
        # the list of each research project is replaced by what the page has — the ones it no longer lists are gone; a project that is not kept here keeps them in the settings
        for project in known:
            local_folder_service.write_field_items(root, project, kind, by_project.get(project, []))
        setattr(new.FIELDWORK, kind, [i for i in items if i.research_project not in known])
    config.save_settings(new)
    logging_setup.apply_level(logging_setup.effective_level())
    return _shown(new)


@router.get("/log")
def download_log() -> FileResponse:
    """The current log file — to attach to a bug report."""
    path = logging_setup.log_file()
    if not path.is_file():
        raise HTTPException(404, "There's no log file yet.")
    return FileResponse(path, media_type="text/plain", filename=path.name)


@router.delete("/log")
def delete_log() -> dict:
    """Deletes the log file and its rotated copies — logging goes on, into a
    new one."""
    return {"deleted": logging_setup.clear_log()}


class NewConfigRequest(BaseModel):
    name: str


@router.get("/configs")
def get_configs() -> list[dict]:
    """Every settings file the user can switch to, the one in use flagged."""
    return [c.model_dump() for c in config.list_configs()]


@router.post("/configs")
def add_config(req: NewConfigRequest) -> list[dict]:
    """Writes a new settings file with the default values (it doesn't become
    the active one) and returns the updated list."""
    try:
        config.create_config(req.name)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return get_configs()


@router.post("/configs/{config_id}/activate")
def activate_config(config_id: str) -> list[dict]:
    """Makes `config_id` the settings file the whole app reads and saves."""
    try:
        config.set_active_config(config_id)
    except KeyError:
        raise HTTPException(404, f"There's no config {config_id!r}.") from None
    return get_configs()


def _existing_config_file(config_id: str) -> Path:
    try:
        path = config.config_file_for(config_id)
    except KeyError:
        raise HTTPException(404, f"There's no config {config_id!r}.") from None
    if not path.is_file():
        raise HTTPException(404, "There's no settings file yet.")
    return path


@router.get("/configs/{config_id}/download")
def download_config(config_id: str) -> FileResponse:
    """The settings file itself, as saved — passwords included, since it's a
    backup of the file; it's the user's own file, on their own machine."""
    path = _existing_config_file(config_id)
    return FileResponse(path, media_type="application/toml", filename=path.name)


@router.post("/configs/{config_id}/open-folder")
def open_config_folder(config_id: str) -> dict:
    """Opens the directory holding that settings file in the OS's file manager."""
    path = _existing_config_file(config_id)
    try:
        file_manager.open_folder(path.parent)
    except OSError as exc:
        raise HTTPException(500, f"Could not open the folder: {exc}") from exc
    return {"ok": True}
