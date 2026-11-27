"""The use cases of the uploaders — what the routers of TRAPPER, of the uploads and of the sync did: the account, what TRAPPER has, importing a
deployment into it from the wizard, uploading the deployments kept (writing down how each went, for the dashboard to say it and a failed one to be
tried again), and bringing back what it has."""
from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from typing import TypeVar

from wildintel_uploader.modules.deployments.domain.models import DeploymentsError
from wildintel_uploader.modules.deployments.domain.ports import DeploymentsService
from wildintel_uploader.modules.uploaders.domain.models import Account, Credentials, NotThere, UploaderError
from wildintel_uploader.modules.uploaders.application.sync import TrapperSync
from wildintel_uploader.modules.uploaders.application.upload import TrapperUploads
from wildintel_uploader.modules.uploaders.domain.ports import (
    Deployment, DeploymentUploads, KeptCollections, Trapper, UploadersService, UploadPlaces, UploadReports,
)


logger = logging.getLogger(__name__)
T = TypeVar("T")


class UploadersUseCases(UploadersService):
    """`deployments` gives the module of the deployments when it is needed: it is built with the uploaders among what it uses."""

    def __init__(self, trapper: Trapper, kept: KeptCollections, reports: UploadReports, uploads: DeploymentUploads | None = None, *,
                 deployments: Callable[[], DeploymentsService] | None = None, sending: TrapperUploads | None = None,
                 places: UploadPlaces | None = None, syncing: TrapperSync | None = None) -> None:
        self._trapper, self._kept, self._reports, self._uploads = trapper, kept, reports, uploads
        self._deployments, self._sending, self._places, self._syncing = deployments, sending, places, syncing

    def _ours(self, call: Callable[[], T]) -> T:
        try:
            return call()
        except Exception as exc:  # noqa: BLE001 — every error is one of the module's
            raise self._trapper.failure(exc) from exc

    def _record(self, project: str) -> dict:
        record = self._kept.project(project)
        if record is None:
            raise NotThere(f"The research project '{project}' isn't in the collections folder.")
        return record

    # the account and what TRAPPER has

    def account_defaults(self) -> dict:
        return self._trapper.defaults()

    def test_connection(self, account: Account) -> dict:
        credentials = self._trapper.credentials(account)
        result = self._trapper.test_connection(credentials)
        self._trapper.keep_account(credentials)   # once it works, so that it needn't be typed again
        return result

    def research_projects(self, account: Account) -> list[dict]:
        return self._trapper.research_projects(self._trapper.credentials(account))

    def classification_projects(self, account: Account, research_project_pk: int) -> list[dict]:
        return self._trapper.classification_projects(self._trapper.credentials(account), research_project_pk)

    def locations(self, account: Account, research_project_pk: int) -> list[dict]:
        return self._trapper.locations(self._trapper.credentials(account), research_project_pk)

    def deployments(self, account: Account, research_project_pk: int) -> list[dict]:
        return self._trapper.deployments(self._trapper.credentials(account), research_project_pk)

    # importing a deployment into TRAPPER from the wizard

    def import_deployment(self, account: Account, research_project_pk: int, classification_project_pk: int | None, source_dir: str, deployment: Deployment,
                          research_project_id: str | None, register: bool, timezone: str | None = None) -> Iterator[dict]:
        """The images organized in their collection, by the deployments, then — unless it is already there (register False) — the deployment
        registered in TRAPPER: {"type": "copy"…}, {"type": "registering"}, {"type": "done", "dest_dir"}. What fails before anything is copied is
        said then."""
        credentials = self._trapper.credentials(account)
        # the timezone and the summer-time setting are the kept location's — the only source of them, whatever the request carries — unless one is given
        time = ({"timezone": timezone} if timezone else
                self._kept.location_time(research_project_id, deployment.location_id) if research_project_id else {})
        try:
            dest, copying = self._deployments().organize(str(research_project_id), source_dir, deployment)
        except DeploymentsError as exc:
            raise UploaderError(exc.message) from exc
        zone, ignore_dst = time.get("timezone"), time.get("ignore_dst", False)
        if register and not zone:
            raise UploaderError("A timezone is required to register a new deployment.")

        def events() -> Iterator[dict]:
            try:
                yield from copying
            except DeploymentsError as exc:
                raise UploaderError(exc.message) from exc
            if register:
                yield {"type": "registering"}
                self._trapper.register(credentials, research_project_pk, classification_project_pk, deployment, zone, ignore_dst)
                logger.info("Deployment %s registered in Trapper (files organized in %s)", deployment.deployment_id, dest)
            else:
                logger.info("Deployment %s already in Trapper (files organized in %s)", deployment.deployment_id, dest)
            yield {"type": "done", "dest_dir": str(dest)}
        return events()

    # uploading the deployments kept

    def collections(self, project: str) -> list[dict]:
        return self._kept.collections(project)

    def project_classification_projects(self, account: Account, project: str) -> list[dict]:
        credentials = self._trapper.credentials(account)
        record = self._record(project)
        return self._trapper.classification_projects(credentials, self._ours(lambda: self._sending.research_project_pk(credentials, record)))

    def check_selection(self, account: Account, project: str, collection: str | None) -> list[dict]:
        credentials = self._trapper.credentials(account)
        return self._sending.check_selection(credentials, self._record(project), collection, describe=self._trapper.describe)

    def check_access(self, account: Account, project: str, collection: str | None, deployment_ids: list[str],
                     classification_project_pk: int | None) -> list[dict]:
        credentials = self._trapper.credentials(account)
        record = self._record(project)
        location_ids: list[str] = []
        if collection:
            collection_dir = self._kept.collection_dir(project, collection)
            location_ids = [loc for d in deployment_ids if (loc := self._kept.location_of(collection_dir, d))]
        return self._sending.check_access(credentials, record, location_ids, classification_project_pk=classification_project_pk,
                                          describe=self._trapper.describe)

    def upload(self, account: Account, project: str, collection: str, deployment_id: str, mode: str, classification_project_pk: int | None,
               delete_files: bool) -> Iterator[dict]:
        credentials: Credentials | None
        if mode == "generate":   # generating the files needs no account when the research project's pk in TRAPPER is already known
            try:
                credentials = self._trapper.credentials(account)
            except UploaderError:
                credentials = None
        else:
            credentials = self._trapper.credentials(account)
        record = self._record(project)
        collection_dir = self._kept.collection_dir(project, collection)
        if not self._kept.has_deployment(collection_dir, deployment_id):
            raise NotThere(f"{deployment_id} isn't in the collection {collection}.")
        events = self._sending.upload(credentials, record, collection_dir, deployment_id, self._places.packages_dir(record["acronym"]), mode=mode,
                                      max_zip_bytes=self._places.max_zip_bytes(), classification_project_pk=classification_project_pk,
                                      delete_after_upload=delete_files)

        def keep(note: str | None) -> None:
            if mode == "upload":
                self._kept.note_failure(project, deployment_id, "trapper", note)

        def told() -> Iterator[dict]:
            try:
                for event in events:
                    if event.get("type") == "done":
                        keep(None)
                    yield event
            except Exception as exc:  # noqa: BLE001 — written down, and told
                detail = self._trapper.describe(exc)
                keep(detail)
                raise UploaderError(detail) from exc
        return told()

    def upload_report(self, collection: str, project: str, items: list[dict], started_at: str, finished_at: str) -> str | None:
        return self._reports.upload(collection, project, items, started_at, finished_at)

    # where the deployments kept were uploaded

    def trapper_state(self, project: str, deployment_id: str | None) -> tuple[str | None, bool]:
        return self._uploads.trapper_state(project, deployment_id)

    def uploads_of(self, project: str, deployment_id: str) -> list[dict]:
        return self._uploads.uploads_of(project, deployment_id)

    def upload_states(self, project: str, imported: str | None, deployment_id: str) -> list[dict]:
        return self._uploads.upload_states(project, imported, deployment_id)

    # bringing back what TRAPPER has

    def collection_names(self, account: Account, research_project_pk: int, classification_project_pk: int) -> list[dict]:
        credentials = self._trapper.credentials(account)
        return self._ours(lambda: self._syncing.collections_with_deployments(credentials, research_project_pk, classification_project_pk))

    def sync(self, account: Account, project: dict, classification_project_pk: int, collections: list[str], deployments: list[str] | None,
             download_images: bool) -> Iterator[dict]:
        credentials = self._trapper.credentials(account)
        self._kept.check_project_dir(project["acronym"] or str(project["pk"]))
        events = self._syncing.sync(credentials, project, classification_project_pk, collections, deployments, download_images)

        def told() -> Iterator[dict]:
            try:
                yield from events
            except Exception as exc:  # noqa: BLE001 — what fails mid-way is one of the module's errors, with its words
                raise self._trapper.failure(exc) from exc
        return told()
