"""The clock of the catalog: the one of the app (shared.audit), and the day here."""
from __future__ import annotations

from datetime import datetime

from wildintel_uploader.modules.catalog.domain.ports import Clock
from wildintel_uploader.shared import audit


class SystemClock(Clock):
    """The clock of the app — shared.audit.now, the one every record of before is dated by."""

    def now(self) -> str:
        return audit.now()

    def today(self) -> str:
        """The day here — as the day a location is put into production always was."""
        return datetime.now().date().isoformat()
