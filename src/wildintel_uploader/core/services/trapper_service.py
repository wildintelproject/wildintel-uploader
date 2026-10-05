"""Trapper integration — thin wrapper around wildintel-trapper-sdk (module
trapper_client), the same SDK wildintel-zooniverse and wildintel-publisher's
web app use.

No server-side session: every call builds its own TrapperClient from fresh
credentials, falling back to settings.toml's TRAPPER section for whatever
the request left blank (the password is never sent back to the frontend).

Registering a deployment goes through deployments.import_deployments() —
the SDK's simulation of Trapper's classic geomap/deployment/import/ form
(cookie/session auth, not the token-authenticated REST API, which is
read-only for deployments). See services.deployment_import_service for the
CSV this builds from a DeploymentFields."""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from trapper_client import TrapperClient

from wildintel_uploader.core import config
from wildintel_uploader.core.schemas.requests import DeploymentFields

logger = logging.getLogger(__name__)

LIST_PAGE_SIZE = 200

# DeploymentFields' own attribute -> the CSV column name Trapper's import
# form expects — the same Camtrap DP-style names DeploymentFields itself
# uses (see core.schemas.requests.DeploymentFields), so this is a 1:1 map.
_CSV_COLUMNS: list[tuple[str, str]] = [
    ("deployment_id", "deploymentID"),
    ("location_id", "locationID"),
    ("location_name", "locationName"),
    ("latitude", "latitude"),
    ("longitude", "longitude"),
    ("coordinate_uncertainty", "coordinateUncertainty"),
    ("start_date", "deploymentStart"),
    ("end_date", "deploymentEnd"),
    ("setup_by", "setupBy"),
    ("camera_id", "cameraID"),
    ("camera_model", "cameraModel"),
    ("camera_interval", "cameraDelay"),
    ("camera_height", "cameraHeight"),
    ("camera_depth", "cameraDepth"),
    ("camera_tilt", "cameraTilt"),
    ("camera_heading", "cameraHeading"),
    ("detection_distance", "detectionDistance"),
    ("bait_use", "baitUse"),
    ("timestamp_issues", "timestampIssues"),
    ("feature_type", "featureType"),
    ("habitat", "habitat"),
    ("deployment_groups", "deploymentGroups"),
    ("comments", "deploymentComments"),
    ("tags", "tags"),
]


def _client(url: str, username: str, password: str) -> TrapperClient:
    logger.debug("Trapper client for %s as %s", url, username)
    return TrapperClient(base_url=url.rstrip("/"), user_name=username, user_password=password)


def client(url: str, username: str, password: str) -> TrapperClient:
    """A Trapper client, for services doing more than listing."""
    return _client(url, username, password)


def get_connection_defaults() -> dict:
    settings = config.load_settings()
    return {
        "base_url": settings.TRAPPER.base_url,
        "user_name": settings.TRAPPER.user_name,
        "has_password": bool(settings.TRAPPER.user_password),
    }


def resolve_credentials(url: str | None, username: str | None, password: str | None) -> tuple[str, str, str]:
    """Raises:
        ValueError: naming whatever is still missing after the fallback.
    """
    trapper = config.load_settings().TRAPPER
    resolved = (url or trapper.base_url, username or trapper.user_name, password or trapper.user_password)
    missing = [name for name, value in zip(("URL", "username", "password"), resolved) if not value]
    if missing:
        raise ValueError(f"Missing Trapper {', '.join(missing)} — provide it, or save it in the configuration first.")
    return resolved  # type: ignore[return-value]


def save_credentials(url: str, username: str, password: str) -> None:
    settings = config.load_settings()
    settings.TRAPPER.base_url = url
    settings.TRAPPER.user_name = username
    settings.TRAPPER.user_password = password
    config.save_settings(settings)


def test_connection(url: str, username: str, password: str) -> dict:
    """Checks the credentials with a single one-item page of research
    projects — its pagination still says how many there are."""
    result = _client(url, username, password).research_projects.get(page=1, page_size=1)
    return {"ok": True, "research_projects_count": result.pagination.count}


def list_research_projects(url: str, username: str, password: str) -> list[dict]:
    projects = _client(url, username, password).research_projects.where(page_size=LIST_PAGE_SIZE)
    return sorted(
        ({"pk": p.pk, "name": p.name or f"#{p.pk}", "acronym": p.acronym} for p in projects),
        key=lambda p: p["name"].lower(),
    )


def list_classification_projects(url: str, username: str, password: str, research_project_pk: int) -> list[dict]:
    projects = _client(url, username, password).classification_projects.where(
        research_project=research_project_pk, page_size=LIST_PAGE_SIZE,
    )
    return sorted(
        ({"pk": p.pk, "name": p.name, "is_active": p.is_active} for p in projects),
        key=lambda p: p["name"].lower(),
    )


def list_locations(url: str, username: str, password: str, research_project_pk: int) -> list[dict]:
    """A research project's locations: pk, location_id, name, timezone and its
    coordinates (latitude/longitude, WGS84) — those come from Trapper's export
    endpoint, since the plain list only has them as a display string. None
    when Trapper can't say."""
    trapper = _client(url, username, password)
    locations = trapper.locations.where(research_project=research_project_pk, page_size=LIST_PAGE_SIZE)
    coordinates: dict[int, tuple[float | None, float | None]] = {}
    try:
        for export in trapper.locations.export(query={"research_project": research_project_pk}):
            coordinates[export.pk] = (export.latitude, export.longitude)
    except Exception as exc:  # the locations are still usable, just without coordinates
        logger.warning("Could not read the locations' coordinates from Trapper: %s", exc)
    return sorted(
        (
            {
                "pk": l.pk, "location_id": l.location_id or f"#{l.pk}", "name": l.name, "timezone": l.timezone,
                "latitude": coordinates.get(l.pk, (None, None))[0], "longitude": coordinates.get(l.pk, (None, None))[1],
            }
            for l in locations
        ),
        key=lambda l: l["location_id"].lower(),
    )


def _plain_value(value):
    """A datetime becomes its ISO string — everything else, including
    DeploymentExport's own tags list, is already JSON-friendly."""
    return value.isoformat() if isinstance(value, datetime) else value


def list_deployments(url: str, username: str, password: str, research_project_pk: int) -> list[dict]:
    """Existing deployments of a research project, already shaped like
    DeploymentFields (plus "pk") — from Trapper's export endpoint, since
    the plain deployments list/get API doesn't carry camera/location
    details. Used by the "use an existing deployment" wizard branch, so the
    picked deployment can go straight into the deployment-details step."""
    exports = _client(url, username, password).deployments.export(query={"research_project": research_project_pk})
    deployments = [
        {"pk": export.pk, **{attr: _plain_value(getattr(export, attr, None)) for attr, _ in _CSV_COLUMNS}}
        for export in exports
    ]
    return sorted(deployments, key=lambda d: (d["deployment_id"] or "").lower())


def _csv_value(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return ",".join(value)
    return str(value)


def write_deployment_csv(deployment: DeploymentFields, path: Path) -> Path:
    """One-row CSV in the column order Trapper's import form expects."""
    values = deployment.model_dump()
    header = ",".join(csv_name for _, csv_name in _CSV_COLUMNS)
    row = ",".join(f'"{_csv_value(values[attr]).replace(chr(34), chr(34) * 2)}"' for attr, _ in _CSV_COLUMNS)
    path.write_text(f"{header}\n{row}\n", encoding="utf-8")
    return path


def import_deployment(
    url: str, username: str, password: str,
    research_project_pk: int, classification_project_pk: int | None,
    deployment: DeploymentFields, timezone: str, csv_path: Path, *, ignore_dst: bool = False,
) -> None:
    """Registers one deployment in Trapper from its CSV (see
    write_deployment_csv) — raises trapper_client.err.APIError on failure."""
    write_deployment_csv(deployment, csv_path)
    _client(url, username, password).deployments.import_deployments(
        file=csv_path, timezone=timezone, research_project=research_project_pk,
        classification_project=classification_project_pk, ignore_dst=ignore_dst,
    )
