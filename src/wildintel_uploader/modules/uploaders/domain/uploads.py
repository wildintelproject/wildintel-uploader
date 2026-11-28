"""Where the deployments kept were uploaded, and how their upload to each uploader goes — plain Python. An upload is "planned" from the start
for each uploader in use, then "done" or "failed"; a failure is written down with why, and an upload that works takes it away."""
from __future__ import annotations

UPLOADERS = ("trapper", "agouti")   # where a deployment can be sent: only the uploaders in use have an upload planned


def upload_of(upload: object, synced: bool, site: str | None) -> list[dict]:
    """One upload for each platform a deployment was sent to (only "trapper" for now): "uploaded" with the day and what it did — as its upload.json
    says —, or "synced" when it came from TRAPPER; with the page of it there, or of the site."""
    if isinstance(upload, dict) and upload.get("uploaded_at"):
        return [{"destination": "trapper", "kind": "uploaded", "uploaded_at": upload.get("uploaded_at"), "parts": upload.get("parts"),
                 "location_created": bool(upload.get("location_created")), "deployment_created": bool(upload.get("deployment_created")),
                 "url": upload.get("deployment_url") or upload.get("collection_url") or site}]
    if synced:
        return [{"destination": "trapper", "kind": "synced", "uploaded_at": None, "parts": None, "location_created": None, "deployment_created": None,
                 "url": site}]
    return []


def states(in_use: dict[str, bool], done: dict[str, dict], failed: dict[str, dict]) -> list[dict]:
    """The upload to each uploader in use — or done — : {"destination", "state": "planned" | "done" | "failed", "kind", "uploaded_at", "note"}."""
    out = []
    for destination in UPLOADERS:
        if not in_use.get(destination) and destination not in done:
            continue
        if destination in done:
            out.append({"destination": destination, "state": "done", "kind": done[destination]["kind"], "uploaded_at": done[destination].get("uploaded_at"),
                        "note": None})
        elif destination in failed:
            out.append({"destination": destination, "state": "failed", "kind": None, "uploaded_at": None, "note": failed[destination].get("note")})
        else:
            out.append({"destination": destination, "state": "planned", "kind": None, "uploaded_at": None, "note": None})
    return out


def failures_after(failures: list[dict], deployment_id: str, destination: str, note: str | None, at: str) -> list[dict]:
    """The failures with how the upload of a deployment to a destination went: a failure, with why — or, with no note, none: it worked."""
    kept = [f for f in failures if not (f.get("deployment_id") == deployment_id and f.get("destination") == destination)]
    if note is not None:
        kept.append({"deployment_id": deployment_id, "destination": destination, "note": note.strip() or None, "at": at})
    return kept
