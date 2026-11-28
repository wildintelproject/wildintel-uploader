"""What the visits offer the fixing of the time of the images (#248) — its one door into the module of the visits, narrow and kept stable: which
visit closes a deployment, so the period a camera was out is the one between the visit that left it and the one that collected its card.

    >>> closes_collection({"actions": ["Revision"], "card_status": "OK"})
    True
"""
from __future__ import annotations

from wildintel_uploader.modules.visits.domain import rules
from wildintel_uploader.modules.visits.domain.shapes import Visit

__all__ = ["closes_collection"]


def closes_collection(visit: Visit) -> bool:
    """Whether a visit collects the card of the camera that a visit before it left — so a deployment ends with it."""
    return rules.closes_collection(visit)
