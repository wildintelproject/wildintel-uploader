"""The internal id of a record — what the records of the app point to each other by.

Every record that others refer to (a research project, a location, a camera, an SD card, a trapper, a role, a visit) has an `id`, generated when it is kept: a UUID, opaque,
that never changes and is never typed. What a person calls it — a location's id (`DONA_01`), a card's label, a trapper's username — is another thing, and can be corrected: the
records that refer to it point to its `id`, so nothing else has to be rewritten. A visit does not say "camera BR5071050724, card A12, Ana Pérez": it says the camera, the card
and the trapper by their ids, and the app tells it with their names. (`local_folder_service` does the telling, as it does with the instant of a visit.)

What was kept before the ids existed gets one the first time it is read: made from what called it (`legacy_id`), so it is the same whenever and wherever it is read, and kept from
then on — which is what makes a backup of an earlier version restore with its visits still pointing to the same things.
"""
from __future__ import annotations

import uuid

_NAMESPACE = uuid.UUID("6f1d9a0e-7c3b-4b8e-9d52-2a1f5c0b7e41")


def new_id() -> str:
    """The id of a record that is new."""
    return str(uuid.uuid4())


def legacy_id(kind: str, key: str, research_project: str | None = None) -> str:
    """The id of a record that was kept before the ids existed — always the same for the same thing: its kind, what called it (case aside) and, if it belongs to one, its research project."""
    return str(uuid.uuid5(_NAMESPACE, f"{kind}:{(research_project or '').lower()}:{str(key).strip().lower()}"))
