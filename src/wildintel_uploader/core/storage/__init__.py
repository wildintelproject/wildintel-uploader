"""Where the app keeps its records — and the one place that says which backend it is.

    from wildintel_uploader.core import storage
    store = storage.open_store(collections_dir)        # a ProjectStore: see storage.base
    store.read_records("DONA", "visits")

The services (`local_folder_service` and those that use it) only ever go through a `ProjectStore`, so **keeping the records in a database is adding a backend, not changing
the app**: subclass `ProjectStore`, make a function that gives one for the collections folder, and `register` it under a name —

    storage.register("sqlite", lambda root: SqliteStore(root))

— then say it in the settings (`DATA.storage = "sqlite"`). Nothing else has to know. The JSON files are the backend called `json`, and the default.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from wildintel_uploader.core.storage.base import GLOBAL_KINDS, RECORD_KINDS, ProjectStore, StorageError, valid_project_id
from wildintel_uploader.core.storage.json_files import JsonFolderStore

__all__ = ["GLOBAL_KINDS", "JsonFolderStore", "RECORD_KINDS", "ProjectStore", "StorageError", "available", "configure", "open_store", "register", "selected", "valid_project_id"]

DEFAULT_BACKEND = "json"
_FACTORIES: dict[str, Callable[[Path], ProjectStore]] = {DEFAULT_BACKEND: JsonFolderStore}
_selected: str | None = None


def register(name: str, factory: Callable[[Path], ProjectStore]) -> None:
    """Makes a backend available under `name`: `factory(collections folder)` gives its store."""
    _FACTORIES[name] = factory


def available() -> list[str]:
    """The names of the backends that can be chosen."""
    return sorted(_FACTORIES)


def configure(name: str | None = None) -> str:
    """Chooses the backend: `name`, or — with none — the one the settings say (`DATA.storage`). Returns it.

    Raises:
        StorageError: there is no backend with that name."""
    global _selected
    if name is None:
        from wildintel_uploader.core import config  # here: config does not need the storage
        name = config.load_settings().DATA.storage
    name = (name or DEFAULT_BACKEND).strip().lower()
    if name not in _FACTORIES:
        raise StorageError(f"There is no storage called '{name}': {', '.join(available())}.")
    _selected = name
    return name


def selected() -> str:
    """The backend in use — the one the settings say, read the first time it is needed."""
    return _selected or configure()


def open_store(root: Path) -> ProjectStore:
    """The store of the records of the collections folder `root`, in the backend in use."""
    return _FACTORIES[selected()](root)
