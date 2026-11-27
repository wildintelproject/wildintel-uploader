"""TRAPPER's API for an upload, over its SDK (trapper_client, through trapper_service): what a research project has, the location and the
deployment created from csv files as TRAPPER's import forms take them, the uploader — a different door from the API's, with a login that copes
with what TRAPPER really answers —, and the processing of a package."""
from __future__ import annotations

import asyncio
import csv
import tempfile
from collections.abc import Callable
from pathlib import Path

import httpx

from wildintel_uploader.modules.uploaders.domain.models import Credentials, UploaderError
from wildintel_uploader.modules.uploaders.domain.ports import Deployment, TrapperSite
from wildintel_uploader.modules.uploaders.infrastructure import trapper_service


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
    def research_projects(self, credentials: Credentials) -> list[dict]:
        return trapper_service.list_research_projects(*credentials)

    def classification_projects(self, credentials: Credentials, research_project_pk: int) -> list[dict]:
        return trapper_service.list_classification_projects(*credentials, research_project_pk)

    def locations(self, credentials: Credentials, research_project_pk: int) -> list[dict]:
        return trapper_service.list_locations(*credentials, research_project_pk)

    def deployments(self, credentials: Credentials, research_project_pk: int) -> list[dict]:
        return trapper_service.list_deployments(*credentials, research_project_pk)

    def create_location(self, credentials: Credentials, research_project_pk: int, deployment: Deployment, timezone: str, ignore_dst: bool) -> None:
        with tempfile.TemporaryDirectory() as tmp:   # the csv is only for the import
            path = Path(tmp) / f"{deployment.location_id}_location.csv"
            _write_location_csv(path, deployment)
            trapper_service.client(*credentials).locations.import_locations(file=path, research_project=research_project_pk, timezone=timezone,
                                                                           ignore_dst=ignore_dst)

    def create_deployment(self, credentials: Credentials, research_project_pk: int, deployment: Deployment, timezone: str, ignore_dst: bool,
                          location_id: str) -> None:
        if location_id != deployment.location_id:
            deployment = deployment.model_copy(update={"location_id": location_id})
        with tempfile.TemporaryDirectory() as tmp:
            trapper_service.import_deployment(*credentials, research_project_pk, None, deployment, timezone, Path(tmp) / f"{deployment.deployment_id}_deployment.csv",
                                              ignore_dst=ignore_dst)

    def _log_in(self, credentials: Credentials) -> None:
        """Logs in to TRAPPER's uploader the way an upload does — and does nothing else. httpx.HTTPStatusError when it is refused."""
        client = trapper_service.client(*credentials)

        async def login() -> None:
            async with httpx.AsyncClient(base_url=client.base_url.rstrip("/") + "/", verify=client.verify_ssl) as http:
                await uploader_class()(client=client)._login(http)
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

        uploader = uploader_class()(client=trapper_service.client(*credentials), progress_callback=on_progress)
        try:
            asyncio.run(uploader.upload_file(path, f"/collections/{path.name}"))
        except httpx.HTTPStatusError as exc:
            raise UploaderError(refused(exc)) from exc
        Path(str(path) + ".uploadmeta.json").unlink(missing_ok=True)

    def process(self, credentials: Credentials, yaml_name: str, zip_name: str, remove_zip: bool) -> None:
        trapper_service.client(*credentials).collections.trigger_collection(payload={"yaml_file": yaml_name, "zip_file": zip_name, "remove_zip": remove_zip},
                                                                          raise_on_error=True)

    def collection(self, credentials: Credentials, research_project_pk: int, name: str) -> dict | None:
        found = next((c for c in trapper_service.client(*credentials).collections.where(research_projects=research_project_pk, search=name) if c.name == name), None)
        return {"pk": getattr(found, "pk", None), "name": found.name} if found is not None else None

    def collection_names(self, credentials: Credentials, classification_project_pk: int) -> list[str]:
        client = trapper_service.client(*credentials)
        return [c.name for c in client.classification_projects.where_project_collections(classification_project_pk, page_size=trapper_service.LIST_PAGE_SIZE)]

    def resources(self, credentials: Credentials, deployment_pk: int) -> list[dict]:
        return trapper_service.list_deployment_resources(*credentials, deployment_pk)

    def media(self, credentials: Credentials, classification_project_pk: int, deployment_pk: int) -> list[dict]:
        return trapper_service.list_deployment_media(*credentials, classification_project_pk, deployment_pk)

    def downloader(self, credentials: Credentials) -> Callable[[str, Path], int]:
        return trapper_service.file_downloader(*credentials)
