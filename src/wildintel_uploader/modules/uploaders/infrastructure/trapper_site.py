"""TRAPPER's API, over its SDK (wildintel-trapper-sdk's trapper_client, the one wildintel-zooniverse and wildintel-publisher use): what a
research project has, the location and the deployment created from csv files as TRAPPER's import forms take them — the SDK's simulation of the
classic forms, since the REST API is read-only for deployments —, the uploader — a different door from the API's, with a login that copes with
what TRAPPER really answers —, the processing of a package, and the images of a deployment downloaded.

No session is kept: every call builds its own client from the account it is given."""
from __future__ import annotations

import asyncio
import csv
import tempfile
from collections.abc import Callable
from pathlib import Path

import logging

import httpx
from trapper_client import TrapperClient
from trapper_client.err import BadRequestError

from wildintel_uploader.modules.uploaders.domain import trapper as rules
from wildintel_uploader.modules.uploaders.domain.models import Credentials, UploaderError
from wildintel_uploader.modules.uploaders.domain.ports import Deployment, TrapperSite

logger = logging.getLogger(__name__)

LIST_PAGE_SIZE = 200


def _client(url: str, username: str, password: str) -> TrapperClient:
    logger.debug("Trapper client for %s as %s", url, username)
    return TrapperClient(base_url=url.rstrip("/"), user_name=username, user_password=password)


def client(credentials: Credentials) -> TrapperClient:
    return _client(*credentials)


def refused(exc: httpx.HTTPStatusError) -> str:
    """What TRAPPER's uploader answered — its URL, status and the start of the body —, since "Client error '403 Forbidden'" alone doesn't say
    whether the login was refused by the uploader itself or by something in front of it."""
    response = exc.response
    body = " ".join(response.text.split())[:300]
    server = response.headers.get("server")
    hint = ""
    if response.status_code in (401, 403) and response.url.path.endswith("/auth/login"):
        hint = " The login was refused: check the account's permissions on the uploader, or whether a proxy/firewall in front of TRAPPER blocks this address."
    return (f"TRAPPER's uploader refused {response.request.method} {response.url}: {response.status_code} {response.reason_phrase}"
            f"{f' (server: {server})' if server else ''}{f' — {body}' if body else ''}.{hint}")


def session_id(data: object) -> str | None:
    """The session the uploader's login hands out: {"results": [{"sessionid"}]} — or, in other TRAPPER versions, at the top."""
    if not isinstance(data, dict):
        return None
    results = data.get("results")
    row = results[0] if isinstance(results, list) and results and isinstance(results[0], dict) else data
    session = row.get("sessionid")
    return str(session) if session else None


def uploader_class():
    """The SDK's HTTPUploader, with a login that copes with what TRAPPER really answers: the SDK's own expects {"results": [{"sessionid": …}]} and
    fails with a bare KeyError("results") when the answer is anything else."""
    from trapper_client.components.http_uploader import HTTPUploader  # needs the SDK's "upload" extra

    class TrapperUploader(HTTPUploader):
        async def _login(self, http: httpx.AsyncClient) -> None:
            response = await http.post("uploader/auth/login", json={"username": self.client.user_name, "password": self.client.user_password})
            response.raise_for_status()
            try:
                data = response.json()
            except ValueError:
                data = None
            session = session_id(data)
            if session:
                http.cookies.set("sessionid", session)
            elif not any(cookie.name == "sessionid" for cookie in http.cookies.jar):   # it may only have come as a cookie, kept already
                body = " ".join(response.text.split())[:300]
                raise UploaderError(f"TRAPPER's uploader accepted the login but gave no session — {response.url} answered {response.status_code}{f': {body}' if body else ''}.")
            if self.progress_callback:
                self.progress_callback("login", {"username": data.get("username") if isinstance(data, dict) else None})

    return TrapperUploader


def _write_location_csv(path: Path, deployment: Deployment) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["locationID", "locationName", "longitude", "latitude", "coordinateUncertainty"])
        writer.writerow([deployment.location_id, deployment.location_name or "", deployment.longitude, deployment.latitude,
                         deployment.coordinate_uncertainty if deployment.coordinate_uncertainty is not None else ""])


class TrapperSdk(TrapperSite):
    def test_connection(self, credentials: Credentials) -> dict:
        """The account checked with one page of one research project — its pagination still says how many there are."""
        result = client(credentials).research_projects.get(page=1, page_size=1)
        return {"ok": True, "research_projects_count": result.pagination.count}

    def research_projects(self, credentials: Credentials) -> list[dict]:
        projects = client(credentials).research_projects.where(page_size=LIST_PAGE_SIZE)
        return rules.by_name([{"pk": p.pk, "name": p.name or f"#{p.pk}", "acronym": p.acronym} for p in projects], "name")

    def classification_projects(self, credentials: Credentials, research_project_pk: int) -> list[dict]:
        projects = client(credentials).classification_projects.where(research_project=research_project_pk, page_size=LIST_PAGE_SIZE)
        return rules.by_name([{"pk": p.pk, "name": p.name, "is_active": p.is_active} for p in projects], "name")

    def locations(self, credentials: Credentials, research_project_pk: int) -> list[dict]:
        """The coordinates (WGS84) and whether it ignores summer time come from TRAPPER's export, since its plain list only has the coordinates
        as a display string; whether this account can manage one, from whether TRAPPER offers it its deletion — only its owner and managers."""
        trapper = client(credentials)
        locations = trapper.locations.where(research_project=research_project_pk, page_size=LIST_PAGE_SIZE)
        coordinates: dict[int, tuple[float | None, float | None]] = {}
        ignore_dst: dict[int, bool | None] = {}
        try:
            for export in trapper.locations.export(query={"research_project": research_project_pk}):
                coordinates[export.pk] = (export.latitude, export.longitude)
                ignore_dst[export.pk] = getattr(export, "ignore_dst", None)
        except Exception as exc:  # noqa: BLE001 — the locations are still usable, just without coordinates
            logger.warning("Could not read the locations' coordinates from Trapper: %s", exc)
        return rules.by_name([
            {"pk": loc.pk, "location_id": loc.location_id or f"#{loc.pk}", "name": loc.name, "timezone": loc.timezone, "ignore_dst": ignore_dst.get(loc.pk),
             "latitude": coordinates.get(loc.pk, (None, None))[0], "longitude": coordinates.get(loc.pk, (None, None))[1],
             "owner": getattr(loc, "owner", None), "can_manage": bool(loc.delete_data) if hasattr(loc, "delete_data") else None}
            for loc in locations
        ], "location_id")

    def deployments(self, credentials: Credentials, research_project_pk: int) -> list[dict]:
        """Shaped like the deployment's own fields, and its pk — from TRAPPER's export, since the plain list doesn't carry the camera or the
        location."""
        try:
            exports = client(credentials).deployments.export(query={"research_project": research_project_pk})
        except BadRequestError as exc:
            # a research project with no deployments (or none this account can see) is answered with an error, not with an empty list
            if "Empty queryset" not in str(exc):
                raise
            return []
        return rules.by_name([{"pk": e.pk, **{field: rules.plain(getattr(e, field, None)) for field, _ in rules.DEPLOYMENT_CSV_COLUMNS}} for e in exports],
                             "deployment_id")

    def register(self, credentials: Credentials, research_project_pk: int, classification_project_pk: int | None, deployment: Deployment,
                 timezone: str, ignore_dst: bool) -> None:
        with tempfile.TemporaryDirectory() as tmp:   # the csv is only for the import
            path = Path(tmp) / f"{deployment.deployment_id}_deployment.csv"
            path.write_text(rules.deployment_csv(deployment.model_dump(), timezone, ignore_dst), encoding="utf-8")
            client(credentials).deployments.import_deployments(file=path, timezone=timezone, research_project=research_project_pk,
                                                                classification_project=classification_project_pk, ignore_dst=ignore_dst)

    def create_location(self, credentials: Credentials, research_project_pk: int, deployment: Deployment, timezone: str, ignore_dst: bool) -> None:
        with tempfile.TemporaryDirectory() as tmp:   # the csv is only for the import
            path = Path(tmp) / f"{deployment.location_id}_location.csv"
            _write_location_csv(path, deployment)
            client(credentials).locations.import_locations(file=path, research_project=research_project_pk, timezone=timezone, ignore_dst=ignore_dst)

    def create_deployment(self, credentials: Credentials, research_project_pk: int, deployment: Deployment, timezone: str, ignore_dst: bool,
                          location_id: str) -> None:
        if location_id != deployment.location_id:
            deployment = deployment.model_copy(update={"location_id": location_id})
        self.register(credentials, research_project_pk, None, deployment, timezone, ignore_dst)

    def _log_in(self, credentials: Credentials) -> None:
        """Logs in to TRAPPER's uploader the way an upload does — and does nothing else. httpx.HTTPStatusError when it is refused."""
        trapper = client(credentials)

        async def login() -> None:
            async with httpx.AsyncClient(base_url=trapper.base_url.rstrip("/") + "/", verify=trapper.verify_ssl) as http:
                await uploader_class()(client=trapper)._login(http)
        asyncio.run(login())

    def log_in_to_uploader(self, credentials: Credentials) -> None:
        try:
            self._log_in(credentials)
        except httpx.HTTPStatusError as exc:
            raise UploaderError(refused(exc)) from exc

    def upload_file(self, credentials: Credentials, path: Path, report: Callable[[dict], None]) -> None:
        sent = {"bytes": 0}
        total = path.stat().st_size

        def on_progress(event: str, info: dict) -> None:
            if event == "chunk_progress":
                sent["bytes"] += info["bytes"]
                report({"type": "upload_progress", "file": path.name, "bytes": sent["bytes"], "total": total})

        uploader = uploader_class()(client=client(credentials), progress_callback=on_progress)
        try:
            asyncio.run(uploader.upload_file(path, f"/collections/{path.name}"))
        except httpx.HTTPStatusError as exc:
            raise UploaderError(refused(exc)) from exc
        Path(str(path) + ".uploadmeta.json").unlink(missing_ok=True)

    def process(self, credentials: Credentials, yaml_name: str, zip_name: str, remove_zip: bool) -> None:
        client(credentials).collections.trigger_collection(payload={"yaml_file": yaml_name, "zip_file": zip_name, "remove_zip": remove_zip},
                                                                          raise_on_error=True)

    def collection(self, credentials: Credentials, research_project_pk: int, name: str) -> dict | None:
        found = next((c for c in client(credentials).collections.where(research_projects=research_project_pk, search=name) if c.name == name), None)
        return {"pk": getattr(found, "pk", None), "name": found.name} if found is not None else None

    def collection_names(self, credentials: Credentials, classification_project_pk: int) -> list[str]:
        trapper = client(credentials)
        return [c.name for c in trapper.classification_projects.where_project_collections(classification_project_pk, page_size=LIST_PAGE_SIZE)]

    def resources(self, credentials: Credentials, deployment_pk: int) -> list[dict]:
        resources = client(credentials).resources.where(deployments=deployment_pk, page_size=LIST_PAGE_SIZE)
        return [{"pk": r.pk, "name": r.name, "date_recorded": r.date_recorded, "mime": r.mime, "date_recorded_correct": r.date_recorded_correct,
                 "observation_type": list(r.observation_type), "species": list(r.species), "tags": list(r.tags)} for r in resources]

    def media(self, credentials: Credentials, classification_project_pk: int, deployment_pk: int) -> list[dict]:
        """The url is the one TRAPPER serves the file from, with the access token it asks for in its query: without it the file is a 404, even
        for the account that owns it. The token is made for the account asking, so private images have it too."""
        media = client(credentials).classification_media.where_project_media(classification_project_pk, deployment=[deployment_pk], page_size=LIST_PAGE_SIZE)
        return [{"pk": int(m.mediaID), "name": m.fileName, "url": str(m.filePath)} for m in media]

    def downloader(self, credentials: Credentials) -> Callable[[str, Path], int]:
        """Written under a temporary name and moved into place when it is whole, so a stop never leaves half an image. One client serves every
        call, from as many threads as wanted."""
        media = client(credentials).classification_media

        def download(file_url: str, destination: Path) -> int:
            partial = destination.with_name(destination.name + ".part")
            try:
                media.download_media_file(file_url, partial)
                partial.replace(destination)
            finally:
                partial.unlink(missing_ok=True)
            return destination.stat().st_size

        return download
