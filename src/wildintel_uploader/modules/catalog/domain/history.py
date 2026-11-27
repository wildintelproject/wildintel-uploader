"""Why the states of the locations, the cameras and the SD cards change — said by whoever knows it, for what it writes:

    with because("the visit R0013 to DONA_01", day="2026-10-19"): …

What is written with no reason said is a change by hand. Plain Python: a context variable, read where the history is written."""
from __future__ import annotations

import contextlib
import contextvars
from typing import Iterator

KINDS = ("locations", "cameras", "sd_cards")
BY_HAND = "Changed by hand in the settings."
# The status of one before the first visit that changed it, in a history rebuilt from the visits: it is not known.
UNKNOWN = "unknown"


_why: contextvars.ContextVar[tuple[str, str | None, dict]] = contextvars.ContextVar("status_history_why", default=(BY_HAND, None, {}))


@contextlib.contextmanager
def because(reason: str, day: str | None = None, each: dict[tuple[str, str], tuple[str, str | None]] | None = None) -> Iterator[None]:
    """What is written inside is a change that has this reason — and is of this day, when it is given. `each` has a reason and a day of its own, for the ones it names: `{(kind, name in lower case): (reason, day)}`."""
    token = _why.set((reason, day, each or {}))
    try:
        yield
    finally:
        _why.reset(token)
