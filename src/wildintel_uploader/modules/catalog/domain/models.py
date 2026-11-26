"""The records of the catalog as the app understands them — dataclasses and the rules each one follows on its own, in plain Python (#248).

Each record is frozen and checks itself when it is made: a value it cannot have raises CatalogError, naming the field; what is only tidied (spaces, a
blank that means none) is tidied. What it says about itself — its id and its dates — is its `Audit`, written by the app, never typed."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


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
