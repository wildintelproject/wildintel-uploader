"""The rules every section of the settings follows, whatever module it belongs to: the error that names the setting, ranges, choices, the names of
EXIF fields, secrets and the levels a check starts at. Plain Python."""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import field
from typing import Any, Literal


class SettingsError(ValueError):
    """A setting that cannot be: `setting` names it as settings.toml does — GENERAL.workers —, and the message says why."""

    def __init__(self, setting: str, message: str) -> None:
        super().__init__(f"{setting}: {message}")
        self.setting, self.message = setting, message


# ── the rules shared by the sections ──

def tidy_field(obj: object, name: str, value: object) -> None:
    """Tidies a field of a frozen dataclass while it is being made — what the sections of the settings of each module are made with, as the
    others below."""
    object.__setattr__(obj, name, value)


def blank_is_none(value: str | None) -> str | None:
    return (value or "").strip() or None


def in_range(setting: str, value: float, low: float, high: float, *, low_open: bool = False) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SettingsError(setting, "must be a number")
    if (value <= low if low_open else value < low) or value > high:
        raise SettingsError(setting, f"must be {'more than' if low_open else 'at least'} {low:g} and at most {high:g}")


def one_of(setting: str, value: object, choices: tuple[str, ...]) -> None:
    if value not in choices:
        raise SettingsError(setting, f"must be one of {', '.join(choices)}")


# The name of an EXIF field, as ExifTool gives it: Model, SerialNumber, GPS:GPSLatitude…
_EXIF_FIELD = re.compile(r"[A-Za-z][A-Za-z0-9_-]*(:[A-Za-z][A-Za-z0-9_-]*)?")


def exif_name(setting: str, name: object) -> str:
    name = str(name).strip()
    if not _EXIF_FIELD.fullmatch(name):
        raise SettingsError(setting, f"'{name}' is not the name of an EXIF field")
    return name


def secret(**kwargs: Any):
    """A setting that is a secret: never shown, never sent to the frontend, never put in a backup (see secret_fields)."""
    return field(metadata={"secret": True}, **kwargs)


# How a check starts in an import, when it is on: it has to pass (required), it only warns (warn), or it is offered unticked (skip).
CHECK_LEVELS = ("required", "warn", "skip")
CheckLevel = Literal["required", "warn", "skip"]


def check_levels(setting: str, given: Mapping[str, str], checks: tuple[str, ...], start: Mapping[str, str]) -> dict[str, str]:
    """The level each check starts at: the ones given, and the default of the rest. A name that is not a check, or a level that is not one, is refused."""
    unknown = sorted(set(given) - set(checks))
    if unknown:
        raise SettingsError(setting, f"not checks: {', '.join(unknown)}")
    for check, level in given.items():
        one_of(f"{setting}.{check}", level, CHECK_LEVELS)
    return {**start, **given}


def check_defaults(value: object, checks: tuple[str, ...], start: Mapping[str, str]) -> dict[str, str]:
    """The same, as the format of the file reads it — a name that is not a check refused, the level left to the schema."""
    given = dict(value or {}) if isinstance(value, dict) else {}
    unknown = sorted(set(given) - set(checks))
    if unknown:
        raise ValueError(f"not checks: {', '.join(unknown)}")
    return {**start, **given}
