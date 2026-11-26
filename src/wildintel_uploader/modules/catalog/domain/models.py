"""The records of the catalog as the app understands them — dataclasses and the rules each one follows on its own, in plain Python (#248).

Each record is frozen and checks itself when it is made: a value it cannot have raises CatalogError, naming the field; what is only tidied (spaces, a
blank that means none) is tidied. What it says about itself — its id and its dates — is its `Audit`, written by the app, never typed; what it says that
this version of the app does not know — written by another one, or by a sync — is its `extra`, kept as it is."""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


class CatalogError(ValueError):
    """A record of the catalog that cannot be: `field` names what is wrong (`username`, or `trappers` for the list), and the message says why."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(f"{field}: {message}")
        self.field, self.message = field, message


def _set(obj: object, name: str, value: object) -> None:
    object.__setattr__(obj, name, value)


def _tidy(value: str | None) -> str | None:
    """Spaces collapsed; blank is none."""
    return (" ".join(value.split()) if value else "") or None


@dataclass(frozen=True)
class Audit:
    """What a record says about itself, written by the app: its internal id — a UUID, never typed, never changed, what the other records point to it
    by —, when it was kept, when it was last changed, and when it was removed, if it was (it is then not listed, but kept: nothing is deleted)."""
    id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    deleted_at: str | None = None

    @property
    def deleted(self) -> bool:
        return bool(self.deleted_at)


# ── the people ──

TRAPPER_STATUSES = ("active", "inactive", "archived")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True)
class Trapper:
    """One of the people who go to the field. The people belong to no research project — what each is in one is its role, the project's. Its username
    is what it is called in the app: required, with no spaces, and no two have it, whatever its case."""
    username: str
    name: str                              # the full name, as it should be on a visit
    affiliation: str | None = None         # where the trapper works, free text
    email: str | None = None
    status: str = "active"                 # inactive: no longer suggested; archived: out of use for good, it never goes back
    trapper_pk: int | None = None          # its id in TRAPPER, when it was taken from there
    audit: Audit = field(default_factory=Audit)
    extra: Mapping[str, Any] = field(default_factory=dict)   # what the record says that this version does not know: kept as it is

    def __post_init__(self) -> None:
        username = (self.username or "").strip()
        if not username or re.search(r"\s", username):
            raise CatalogError("username", "can't be blank or have spaces")
        _set(self, "username", username)
        name = " ".join((self.name or "").split())
        if not name:
            raise CatalogError("name", "can't be blank")
        _set(self, "name", name)
        _set(self, "affiliation", (self.affiliation or "").strip() or None)
        email = (self.email or "").strip()
        if email and not _EMAIL.match(email):
            raise CatalogError("email", "is not an email address")
        _set(self, "email", email or None)
        if self.status not in TRAPPER_STATUSES:
            raise CatalogError("status", f"must be one of {', '.join(TRAPPER_STATUSES)}")

    @property
    def deleted(self) -> bool:
        return self.audit.deleted


# ── the research projects ──

PROJECT_STATUSES = ("planned", "active", "finished", "archived")
_ACRONYM = re.compile(r"^[0-9A-Za-z][0-9A-Za-z_.-]*$")


def _whole(field_name: str, value: object, low: int, high: int | None = None) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < low or (high is not None and value > high):
        raise CatalogError(field_name, f"must be a whole number from {low}" + (f" to {high}" if high is not None else " up"))


@dataclass(frozen=True)
class ResearchProject:
    """A research project, as TRAPPER's own "Add research project" form has it — its choice fields hold TRAPPER's option numbers. Its acronym names it
    and its folder in the collections folder: it never changes."""
    acronym: str
    name: str
    sampling_design: int = 1
    sensor_method: int = 1
    animal_types: int = 1
    bait_use: int = 1
    event_interval: int = 0
    status: str = "active"        # planned: being prepared; active: being worked on; finished: no more field work; archived: out of use for good
    keywords: str = ""
    abstract: str = ""
    methods: str = ""
    description: str = ""
    trapper_pk: int | None = None  # set when it was filled in from TRAPPER, to find its locations there later
    audit: Audit = field(default_factory=Audit)
    extra: Mapping[str, Any] = field(default_factory=dict)   # what the record says that this version does not know: kept as it is

    def __post_init__(self) -> None:
        if not (3 <= len(self.acronym or "") <= 10) or not _ACRONYM.match(self.acronym):
            raise CatalogError("acronym", "must be 3 to 10 letters, digits, dots, hyphens or underscores, starting with a letter or a digit")
        if not (1 <= len(self.name or "") <= 255):
            raise CatalogError("name", "must have 1 to 255 characters")
        _whole("sampling_design", self.sampling_design, 1, 6)
        _whole("sensor_method", self.sensor_method, 1, 3)
        _whole("animal_types", self.animal_types, 1, 3)
        _whole("bait_use", self.bait_use, 1, 6)
        _whole("event_interval", self.event_interval, 0)
        if self.status not in PROJECT_STATUSES:
            raise CatalogError("status", f"must be one of {', '.join(PROJECT_STATUSES)}")
        for name in ("abstract", "methods", "description"):
            if len(getattr(self, name) or "") > 2000:
                raise CatalogError(name, "must have at most 2000 characters")

    @property
    def deleted(self) -> bool:
        return self.audit.deleted


class UnknownProject(LookupError):
    """The research project is not kept — or it was removed."""

    def __init__(self, acronym: str) -> None:
        super().__init__(f"The research project '{acronym}' isn't in the collections folder.")
        self.acronym = acronym


class ProjectExists(CatalogError):
    def __init__(self, acronym: str) -> None:
        super().__init__("acronym", f"The research project '{acronym}' already exists.")


class ProjectArchived(CatalogError):
    """An archived research project can't be modified — nor its locations, cameras, SD cards, roles or visits — and never goes back."""

    def __init__(self, acronym: str) -> None:
        super().__init__("status", f"The research project '{acronym}' is archived: it can't be modified.")


class ProjectHasVisits(CatalogError):
    def __init__(self, acronym: str) -> None:
        super().__init__("status", f"The research project '{acronym}' has visits: it can't go back to planned.")


class ProjectNotEmpty(CatalogError):
    """A research project whose folder holds collections, deployments or images is not removed: they would be left with no project to be seen in."""

    def __init__(self, acronym: str, held: list[str]) -> None:
        names = ", ".join(held[:5]) + (" and more" if len(held) > 5 else "")
        super().__init__("acronym", f"The research project '{acronym}' still holds {names}: it can't be deleted until those are removed "
                                    "(they hold collections, deployments or images).")


class ProjectNotActive(CatalogError):
    """New visits are only kept to a research project that is being worked on."""

    def __init__(self, acronym: str, status: str) -> None:
        super().__init__("status", f"The research project '{acronym}' is {status}: new visits are only kept to an active one (change its status in Settings).")
