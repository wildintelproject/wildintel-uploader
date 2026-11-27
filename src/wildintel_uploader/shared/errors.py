"""The errors the shared kernel tells of — plain Python, so the use cases can catch them without leaning on how the records are kept."""
from __future__ import annotations


class StorageError(Exception):
    """The records cannot be read or kept — the message says why, for the person."""
