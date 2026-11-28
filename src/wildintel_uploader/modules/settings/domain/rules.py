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


class Secret:
    """A secret of the settings — a password, a key — as a value of its own: whatever prints it, logs it or puts it in a text shows ********, and
    what it is is said only when asked for (`reveal`), where it is used. Two are equal when they hold the same; one is true when it holds something.

        >>> password = Secret("hunter2")
        >>> password, str(password), f"{password}"
        (Secret('********'), '********', '********')
        >>> password.reveal()
        'hunter2'
    """

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        self._value = value

    def reveal(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return "Secret('********')"

    def __str__(self) -> str:
        return "********"

    def __bool__(self) -> bool:
        return bool(self._value)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Secret) and other._value == self._value

    def __hash__(self) -> int:
        return hash((Secret, self._value))


def as_secret(value: Secret | str | None) -> Secret | None:
    """What a secret setting keeps: the Secret of a text — blank is none."""
    if isinstance(value, Secret):
        return value if value.reveal() else None
    return Secret(value) if value else None


def revealed(value: Secret | None) -> str | None:
    """What a secret holds, where it is used — none when there is none."""
    return value.reveal() if value is not None else None


def secret(**kwargs: Any):
    """A setting that is a secret: a Secret (the dataclass turns a text into one with as_secret), left out of what the settings print, never shown,
    never sent to the frontend, never put in a backup (see secret_fields)."""
    return field(metadata={"secret": True}, repr=False, **kwargs)


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
