"""Moving the catalog to where the user asks — the web API and the command line do it the same way: the two repositories are made as wiring makes
them, the catalog is copied (modules.catalog.application.migration), and only then the settings say the new place — through their module."""
from __future__ import annotations

from pathlib import Path

from wildintel_uploader.entrypoints import wiring
from wildintel_uploader.modules.catalog.application.migration import CopiedCatalog, copy_catalog
from wildintel_uploader.modules.catalog.domain.models import CatalogError
from wildintel_uploader.modules.settings.domain.ports import SettingsService


def move_catalog(settings: SettingsService, to: str, *, database: Path | None = None, replace: bool = False) -> CopiedCatalog:
    """Copies the catalog to `to` ("json" or "sqlite", in `database` or the one the settings say) and makes it the one in use. CatalogError: it is
    there already, or what was copied does not read back as it was; TargetNotEmpty: the place holds a catalog, and `replace` is off."""
    places = settings.places()
    target_database = database.expanduser() if database else places.catalog_database
    if to == places.catalog_storage and (to == "json" or target_database == places.catalog_database):
        raise CatalogError("catalog_storage", f"The catalog is kept in {to} already.")
    source = wiring.catalog_repository(places.collections, settings)
    target = wiring.catalog_repository(places.collections, settings, kind=to, database=target_database)
    copied = copy_catalog(source, target, replace=replace)
    settings.save_section("DATA", {"catalog_storage": to, **({"catalog_database": str(target_database)} if database else {})})
    return copied
