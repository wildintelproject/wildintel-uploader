"""What the factories share: a section of the settings, the account of TRAPPER kept, the log of the app, the words of an error, and the collections folder of a request."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from wildintel_uploader.entrypoints import config
from wildintel_uploader.modules.settings.infrastructure.system import AppActivityLog


def section(name: str) -> Callable[[], Any]:
    """A section of the settings as settings.toml keeps them (VALIDATION, TRAPPER…) — what an adapter is given of them, asked each time."""
    return lambda: getattr(config.load_settings(), name)


def keep_trapper_account(credentials) -> None:
    """The account of TRAPPER kept in the settings: its address, its user and its password."""
    settings = config.load_settings()
    settings.TRAPPER.base_url, settings.TRAPPER.user_name, settings.TRAPPER.user_password = credentials
    config.save_settings(settings)


def app_log() -> AppActivityLog:
    """The log of the app, in the log folder and at the level the settings say — what the entry points set up when they start."""
    return AppActivityLog(lambda: config.get_logs_dir(), lambda: config.legacy_logs_dir(), lambda: config.load_settings().GENERAL.log_level)


def error_words(exc: Exception) -> str:
    """What an error says to a person, as the web API tells it: TRAPPER's, the network's, or the words of what the modules refuse."""
    from wildintel_uploader.modules.uploaders.infrastructure.trapper import as_uploader_error
    return as_uploader_error(exc).message


def catalog_collections_dir() -> Path:
    """The collections folder the catalog of a request or a command is kept in: the one the settings say."""
    return config.collections_dir()
