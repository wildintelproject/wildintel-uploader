"""Where the deployments kept were uploaded, as their folders say: upload.json when one was sent from here, images.json when it was synced from
TRAPPER; and the upload of each to each uploader in use — planned, done or failed —, with the failures written down."""
from __future__ import annotations

from typing import Any
import json
from collections.abc import Callable
from pathlib import Path

from wildintel_uploader.modules.uploaders.domain.ports import DeploymentUploads
from wildintel_uploader.modules.deployments.domain.ports import CollectionLayout
from wildintel_uploader.modules.uploaders.domain import uploads as rules
from wildintel_uploader.modules.uploaders.infrastructure.failures import UploadFailures


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


class FolderUploads(DeploymentUploads):
    """Where a deployment was uploaded, as its folder says: its upload.json, or images.json when it was synced from TRAPPER."""

    def __init__(self, root: Path, trapper: Callable[[], Any], agouti: Callable[[], Any], layout: Callable[[], CollectionLayout], failures: UploadFailures) -> None:
        """`trapper` and `agouti` give the sections of the uploaders in the settings, asked each time."""
        self.root, self._trapper, self._agouti, self._layout, self._failures = root, trapper, agouti, layout, failures

    def _folder(self, project: str, deployment_id: str) -> Path:
        return self.root / project / deployment_id.split("-", 1)[0] / deployment_id

    @staticmethod
    def _upload(folder: Path):
        from wildintel_uploader.modules.uploaders.infrastructure.packages import UPLOAD_LOG_FILE
        return _read_json(folder / UPLOAD_LOG_FILE)

    def trapper_state(self, project: str, deployment_id: str | None) -> tuple[str | None, bool]:
        """Whether the deployment a visit gave is on Trapper — uploaded from here, or synced from there — and when it was uploaded."""
        if not deployment_id:
            return None, False
        folder = self._folder(project, deployment_id)
        upload = self._upload(folder)
        uploaded_at = upload.get("uploaded_at") if isinstance(upload, dict) else None
        return uploaded_at, bool(uploaded_at) or self._layout().is_synced(folder)

    def uploads_of(self, project: str, deployment_id: str) -> list[dict]:
        """One upload for each platform it was sent to — "uploaded" with the day and what it did, or "synced" —, with the page of it in TRAPPER as it
        was when it was sent; an upload made before that was kept goes to the site."""
        folder = self._folder(project, deployment_id)
        site = (self._trapper().base_url or "").rstrip("/") or None
        return rules.upload_of(self._upload(folder), self._layout().is_synced(folder), site)

    def upload_states(self, project: str, imported: str | None, deployment_id: str) -> list[dict]:
        """The upload to each uploader in use: "planned" from the start, then "done" or "failed"."""
        in_use = {"trapper": self._trapper().enabled, "agouti": self._agouti().enabled}
        done = {u["destination"]: u for u in (self.uploads_of(project, imported) if imported else [])}
        failed = {f["destination"]: f for f in self._failures.of(project) if f.get("deployment_id") == deployment_id}
        return rules.states(in_use, done, failed)
