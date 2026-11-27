"""What logging the app does shares with every module."""
from __future__ import annotations

import logging


def debugging() -> bool:
    """Whether to log full tracebacks — logger.warning(..., exc_info=debugging())."""
    return logging.getLogger().isEnabledFor(logging.DEBUG)
