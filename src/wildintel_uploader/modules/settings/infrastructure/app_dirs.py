"""Where the system puts the files of the app — platformdirs: the config folder (the settings), the documents folder (the data folder, by default),
the log and state folders (the log, the sessions of the import). None of them is a setting."""
from __future__ import annotations

from pathlib import Path

import platformdirs

APP_NAME = "wildintel-uploader"


def config_dir() -> Path:
    """The folder of the settings files: ~/.config/wildintel-uploader on Linux."""
    return Path(platformdirs.user_config_dir(APP_NAME))


def documents_dir() -> Path:
    """<documents>/wildintel-uploader."""
    return Path(platformdirs.user_documents_dir()) / APP_NAME


def default_data_dir() -> Path:
    """The data folder unless DATA.dir says another: <documents>/wildintel-uploader."""
    return documents_dir()


def logs_dir() -> Path:
    """Where the log files go — the log folder of the system, which is state: ~/.local/state/wildintel-uploader/log on Linux (see logging_setup)."""
    return Path(platformdirs.user_log_dir(APP_NAME))


def sessions_dir() -> Path:
    """Where in-progress and interrupted wizard runs persist — they are state: ~/.local/state/wildintel-uploader/sessions on Linux (the XDG state
    folder), the app's folder in Windows and macOS (see modules.deployments, domain.sessions)."""
    return Path(platformdirs.user_state_dir(APP_NAME)) / "sessions"


def legacy_sessions_dir() -> Path:
    """Where the sessions were kept before they moved to the state folder: <documents>/wildintel-uploader/sessions."""
    return documents_dir() / "sessions"
