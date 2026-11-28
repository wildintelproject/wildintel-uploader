"""The runs of the wizard that imports a deployment, kept step by step — plain Python. The same design wildintel-zooniverse's web backend uses.

A session is one run, kept by its task id (the canonical form of a UUID, made by the app: the name of one folder and nothing else) as a
manifest. Each step merges its own section into what is kept, so no step ever erases another's; "phase" says how far the run got, and the run is
offered back on the "resume?" screen until it finishes and is discarded. The steps, in the order the wizard asks for them:

- "scanned": the source folder is chosen and scanned. It starts the session; everything else is added to it.
- "selected": the research project, the classification project and the location — or the local destination — are chosen too.
- "ready": the deployment's own fields are filled in too: everything the import needs. If the import fails or is interrupted, the session
  stays here so it can be retried.

A session never holds credentials: resuming always asks for them again."""
from __future__ import annotations

import uuid
from typing import Any

from wildintel_uploader.modules.deployments.domain.models import DeploymentMissing, DeploymentsFailed

MANIFEST = "session.json"


class InvalidTaskId(DeploymentsFailed):
    """A task id that is not one the app makes: it names no session."""


def new_task_id() -> str:
    return str(uuid.uuid4())


def valid_task_id(task_id: object) -> bool:
    try:
        return isinstance(task_id, str) and str(uuid.UUID(task_id)) == task_id
    except ValueError:
        return False


def check_task_id(task_id: str) -> str:
    if not valid_task_id(task_id):
        raise InvalidTaskId(f"{task_id!r} is not the id of a session.")
    return task_id


def scanned(existing: dict | None, task_id: str, source_dir: str, scan: dict, now: str) -> dict[str, Any]:
    existing = existing or {}
    return {**existing, "task_id": task_id, "created_at": existing.get("created_at") or now, "updated_at": now, "phase": "scanned",
            "task": "deployment", "source_dir": source_dir, "scan": scan}


def _existing(existing: dict | None, task_id: str) -> dict:
    if existing is None:
        raise DeploymentMissing(f"Session {task_id} not found.")
    return existing


def selected(existing: dict | None, task_id: str, selection: dict, now: str) -> dict[str, Any]:
    """`selection` already without secrets. DeploymentMissing when there is no such session."""
    return {**_existing(existing, task_id), "updated_at": now, "phase": "selected", "selection": selection}


def ready(existing: dict | None, task_id: str, deployment: dict, now: str) -> dict[str, Any]:
    """DeploymentMissing when there is no such session."""
    return {**_existing(existing, task_id), "updated_at": now, "phase": "ready", "deployment": deployment}


def newest_first(sessions: list[dict]) -> list[dict]:
    return sorted(sessions, key=lambda m: m.get("updated_at") or m.get("created_at") or "", reverse=True)
