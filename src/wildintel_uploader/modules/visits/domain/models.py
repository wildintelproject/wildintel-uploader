"""What the use cases of the visits are asked, and what they refuse — each refusal saying how the entry points tell it: a visit that breaks the
rules (refused), one that can't be changed (locked), one that is not there (missing), a revision that can't be planned, a save already running, and
what the records or a file can't give (failed)."""
from __future__ import annotations

from dataclasses import dataclass, field


class VisitsError(Exception):
    """What the visits refuse, with its words."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class VisitRefused(VisitsError):
    """A visit, or an edit, that breaks the rules of a visit."""


class VisitLocked(VisitsError):
    """A visit, or a revision, that can't be changed now."""


class VisitMissing(VisitsError):
    """There is no such visit."""


class VisitsFailed(VisitsError):
    """What the records, a source or a file can't give: a research project that is not there, a file that can't be read."""


@dataclass(frozen=True)
class ImportOptions:
    """How a file of visits is read, and whether what can be kept is: see the import of the visits."""
    research_project_id: str
    csv: str = ""
    save: bool = False
    format: str = "mapped"                      # mapped, epicollect-api, epicollect-csv
    mapping: dict[str, str] | None = None
    create: dict[str, bool] | None = None
    close_revisions: bool = False
    close_after: dict | None = None
    coordinates_from_location: bool = True
    photos_not_counted: bool = False
    defaults: dict[str, str] | None = field(default=None)
