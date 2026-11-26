"""The folders the app keeps what it makes in, as the settings say them: the data folder, and the collections, reports and packages folders — each one
its own when DATA says one, else a folder of that name inside the data folder. Pure: the folder to fall back on is given (the documents folder of the
system, see infrastructure.app_dirs), and so is the data folder once it is resolved. They need only the DATA section."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from wildintel_uploader.modules.settings.domain.models import DataSettings


def data_dir(data_settings: DataSettings, default: Path) -> Path:
    """DATA.dir if set, else `default`."""
    return Path(data_settings.dir).expanduser() if data_settings.dir else default


def _own_or_inside(custom: str | None, data: Path, name: str) -> Path:
    return Path(custom).expanduser() if custom else data / name


def collections_dir(data_settings: DataSettings, data: Path) -> Path:
    """Where every collection is kept before anything is uploaded — <research project id>/<collection, e.g. R0003>/<deployment id>/ inside it:
    DATA.collections_dir if set, else <data folder>/collections."""
    return _own_or_inside(data_settings.collections_dir, data, "collections")


def reports_dir(data_settings: DataSettings, data: Path) -> Path:
    """Where the reports of the checks and of the preprocessing are kept: DATA.reports_dir if set, else <data folder>/reports."""
    return _own_or_inside(data_settings.reports_dir, data, "reports")


def packages_dir(data_settings: DataSettings, data: Path) -> Path:
    """Where the packages made to upload to TRAPPER are written — <research project id>/<collection> inside it: DATA.packages_dir if set, else
    <data folder>/packages."""
    return _own_or_inside(data_settings.packages_dir, data, "packages")


def follow_data_dir(before: DataSettings, after: DataSettings, default: Path) -> DataSettings:
    """When the data folder changes, the collections, reports and packages folders that were inside the old one go inside the new one: a folder kept
    elsewhere stays where it is, and one that was just <old data folder>/<its name> goes back to being the default one (None)."""
    old_dir, new_dir = data_dir(before, default), data_dir(after, default)
    if old_dir == new_dir:
        return after
    moved = {}
    for key in ("collections", "reports", "packages"):
        value = getattr(after, f"{key}_dir")
        if not value:
            continue
        try:
            inside = Path(value).expanduser().relative_to(old_dir)
        except ValueError:
            continue
        moved[f"{key}_dir"] = None if str(inside) == key else str(new_dir / inside)
    return replace(after, **moved)
