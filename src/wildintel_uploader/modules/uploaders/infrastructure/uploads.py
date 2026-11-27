"""Where the deployments kept were uploaded, as their folders say: upload.json when one was sent from here, images.json when it was synced from
TRAPPER; and the upload of each to each uploader in use — planned, done or failed —, with the failures written down."""
from __future__ import annotations

import json
from pathlib import Path

from wildintel_uploader.modules.uploaders.domain.ports import DeploymentUploads
from wildintel_uploader.modules.uploaders.infrastructure import failures


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _layout():
    """How a collection holds its deployments — the contract of the deployments —, from where the app is put together."""
    from wildintel_uploader.entrypoints import wiring
    return wiring.build_deployments().layout()


# Where a deployment can be sent, and the settings that say whether each is used: only the uploaders in use have an upload planned.
UPLOADERS = {"trapper": lambda settings: settings.TRAPPER.enabled, "agouti": lambda settings: settings.AGOUTI.enabled}


class FolderUploads(DeploymentUploads):
    """Where a deployment was uploaded, as its folder says: its upload.json, or images.json when it was synced from TRAPPER."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def _folder(self, project: str, deployment_id: str) -> Path:
        return self.root / project / deployment_id.split("-", 1)[0] / deployment_id

    @staticmethod
    def _upload(folder: Path):
        from wildintel_uploader.modules.uploaders.infrastructure import trapper_upload_service
        return _read_json(folder / trapper_upload_service.UPLOAD_LOG_FILE)

    def trapper_state(self, project: str, deployment_id: str | None) -> tuple[str | None, bool]:
        """Whether the deployment a visit gave is on Trapper — uploaded from here, or synced from there — and when it was uploaded."""
        if not deployment_id:
            return None, False
        folder = self._folder(project, deployment_id)
        upload = self._upload(folder)
        uploaded_at = upload.get("uploaded_at") if isinstance(upload, dict) else None
        return uploaded_at, bool(uploaded_at) or _layout().is_synced(folder)

    def uploads_of(self, project: str, deployment_id: str) -> list[dict]:
        """One upload for each platform it was sent to (only "trapper" for now) — "uploaded" with the day and what it did, or "synced"."""
        from wildintel_uploader.core import config
        folder = self._folder(project, deployment_id)
        upload = self._upload(folder)
        # the page of the deployment in Trapper — or of its revision —, as it was when it was sent; an upload made before that was kept goes to the site
        site = (config.load_settings().TRAPPER.base_url or "").rstrip("/") or None
        if isinstance(upload, dict) and upload.get("uploaded_at"):
            return [{"destination": "trapper", "kind": "uploaded", "uploaded_at": upload.get("uploaded_at"), "parts": upload.get("parts"),
                     "location_created": bool(upload.get("location_created")), "deployment_created": bool(upload.get("deployment_created")),
                     "url": upload.get("deployment_url") or upload.get("collection_url") or site}]
        if _layout().is_synced(folder):
            return [{"destination": "trapper", "kind": "synced", "uploaded_at": None, "parts": None, "location_created": None, "deployment_created": None,
                     "url": site}]
        return []

    def upload_states(self, project: str, imported: str | None, deployment_id: str) -> list[dict]:
        """The upload to each uploader in use: "planned" from the start, then "done" or "failed" — {"destination", "state", "kind", "uploaded_at", "note"}."""
        from wildintel_uploader.core import config
        settings = config.load_settings()
        done = {u["destination"]: u for u in (self.uploads_of(project, imported) if imported else [])}
        failed = {f["destination"]: f for f in failures.list_upload_failures(self.root, project) if f.get("deployment_id") == deployment_id}
        out = []
        for destination, used in UPLOADERS.items():
            if not used(settings) and destination not in done:
                continue
            if destination in done:
                out.append({"destination": destination, "state": "done", "kind": done[destination]["kind"], "uploaded_at": done[destination].get("uploaded_at"),
                            "note": None})
            elif destination in failed:
                out.append({"destination": destination, "state": "failed", "kind": None, "uploaded_at": None, "note": failed[destination].get("note")})
            else:
                out.append({"destination": destination, "state": "planned", "kind": None, "uploaded_at": None, "note": None})
        return out
