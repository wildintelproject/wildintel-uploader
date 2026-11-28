"""FastAPI router — what the settings page reads and saves all at once (GET and PUT /api/settings).

What is a setting, it leaves to the module `modules.settings` (its contract, SettingsService, given by Dishka): which secrets are saved, the folders by
default, the log and the CPUs to show; and saving them — a secret left blank keeps the saved one, a blank address or user is none, the folders follow
the data folder, the storage has to exist, the level of the log applies at once. The field work of the page — the people, and the cameras, SD cards
and roles of the research projects — it leaves to the module `modules.catalog` (CatalogService). What is left here is putting the two together as the
page has them. The rest of the settings is `entrypoints/api/settings.py`, and the rest of the catalog `entrypoints/api/catalog.py`."""
from __future__ import annotations

from dishka.integrations.fastapi import DishkaSyncRoute, FromDishka
from fastapi import APIRouter, HTTPException

from wildintel_uploader.entrypoints import config
from wildintel_uploader.shared import audit
from wildintel_uploader.modules.settings.domain import folders
from wildintel_uploader.modules.settings.domain import models as domain
from wildintel_uploader.modules.settings.domain.ports import SettingsService
from wildintel_uploader.entrypoints import wiring
from wildintel_uploader.modules.catalog.domain.models import CatalogError
from wildintel_uploader.modules.catalog.domain.ports import CatalogService, Fieldwork
from wildintel_uploader.modules.catalog.infrastructure.api_schemas import fieldwork_saved, fieldwork_shown
from wildintel_uploader.modules.settings.infrastructure.api_schemas import settings_of
from wildintel_uploader.shared.storage import StorageError

router = APIRouter(prefix="/api/settings", tags=["settings"], route_class=DishkaSyncRoute)


# what the settings page reads for each secret: whether it is saved
_HAS = {"user_password": "has_password", "client_secret": "has_secret", "api_key": "has_api_key"}


def _public(settings: config.Settings, service: SettingsService) -> dict:
    data = settings.model_dump(mode="json")
    # no secret goes to the frontend: only whether it is saved, with the name the page reads
    for section, field in domain.secret_fields():
        data[section][_HAS.get(field, f"has_{field}")] = bool(data[section].pop(field))
    data["FIELDWORK"]["roles"] = audit.alive(data["FIELDWORK"]["roles"])
    # the folders by default, the log and the CPUs: what the General section of the module shows
    general = service.general()
    data["DATA"]["dir"] = data["DATA"]["dir"] or str(general.folders.default_dir)
    for key in ("collections", "reports", "packages"):
        data["DATA"][f"default_{key}_dir"] = str(getattr(general.folders, f"default_{key}_dir"))
    data["GENERAL"]["log_file"] = str(general.system.log_file)
    data["GENERAL"]["log_level_override"] = general.system.log_level_override
    data["GENERAL"]["cpu_count"] = general.system.cpu_count
    return data


def _root(settings: config.Settings):
    return config.collections_dir(settings)


def _shown(settings: config.Settings, service: SettingsService, fieldwork: Fieldwork) -> dict:
    """The settings as the page has them, and the field work of the catalog: the people, and the cameras, SD cards and roles of the research projects
    — with those versions before left in the settings, which wait there for their research project."""
    data = _public(settings, service)
    data["FIELDWORK"].update(fieldwork_shown(fieldwork))
    return data


def _follow_data_dir(old: config.Settings, new: config.Settings) -> None:
    """When the data folder changes, the collections, reports and packages folders that were inside the old one go inside the new one — the rule of
    the domain of the settings (modules.settings.domain.folders.follow_data_dir), on the file's settings this router still works with."""
    followed = folders.follow_data_dir(domain.DataSettings(**old.DATA.model_dump()), domain.DataSettings(**new.DATA.model_dump()), config.default_data_dir())
    for key in ("collections_dir", "reports_dir", "packages_dir"):
        setattr(new.DATA, key, getattr(followed, key))


@router.get("")
def get_settings(service: FromDishka[SettingsService], catalog: FromDishka[CatalogService]) -> dict:
    fieldwork = catalog.fieldwork()   # what versions before left in the settings goes to its research project first
    return _shown(config.load_settings(), service, fieldwork)


@router.put("")
def save_settings(new: config.Settings, service: FromDishka[SettingsService]) -> dict:
    """Replaces every setting by the rules of the module of the settings (SettingsService.save_settings), and the field work of the page goes to the
    research projects by the rules of the catalog (CatalogService.save_fieldwork) — in the collections folder the settings are saved with."""
    current = config.load_settings()
    # the page does not show where the records and the catalog are kept: they are not its to change
    for name in ("storage", "catalog_storage", "catalog_database"):
        if name not in new.DATA.model_fields_set:
            setattr(new.DATA, name, getattr(current.DATA, name))
    try:
        service.check_settings(settings_of(new))      # before anything is written to the research projects
    except domain.SettingsError as exc:
        raise HTTPException(422, f"{exc.message[:1].upper()}{exc.message[1:]}.") from exc
    _follow_data_dir(current, new)   # where the research projects are, for their field work
    catalog = wiring.build_catalog(_root(new), service)
    _save_together(catalog, service, new)
    return _shown(config.load_settings(), service, catalog.fieldwork())


def _save_together(catalog: CatalogService, service: SettingsService, new: config.Settings) -> None:
    """The field work the page sends goes to the catalog — the people, and the cameras, SD cards and roles of each research project kept —, and the
    rest of the page to the settings: two modules, two writes, whole or not at all. The settings were checked before; if the catalog refuses what
    the page says (an archived camera changed…) or writing the settings fails, what the catalog wrote is put back as it was — the checkpoint of each
    research project, with the people — and the error is told."""
    put_back = [catalog.checkpoint(p.acronym) for p in catalog.projects()]
    fieldwork = new.FIELDWORK
    try:
        try:
            catalog.save_fieldwork(*fieldwork_saved(fieldwork))
        except (CatalogError, StorageError) as exc:
            raise HTTPException(422, getattr(exc, "message", str(exc))) from exc
        # what is of a research project that is not kept stays in the settings, to wait for it
        known = {p.acronym for p in catalog.projects()}
        fieldwork.trappers = []
        fieldwork.cameras = [i for i in fieldwork.cameras if i.research_project not in known]
        fieldwork.sd_cards = [i for i in fieldwork.sd_cards if i.research_project not in known]
        fieldwork.roles = [r for r in fieldwork.roles if r.research_project not in known]
        try:
            service.save_settings(settings_of(new))
        except domain.SettingsError as exc:
            raise HTTPException(422, f"{exc.message[:1].upper()}{exc.message[1:]}.") from exc
    except BaseException as exc:
        for undo in reversed(put_back):
            try:
                undo()
            except Exception as failed:  # noqa: BLE001 — the first error is the one told
                exc.add_note(f"What the catalog wrote could not all be put back: {failed}")
        raise

