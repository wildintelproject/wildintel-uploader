"""The use cases of the uploaders — what the routers of TRAPPER, of the uploads and of the sync did: the account, what TRAPPER has, importing a
deployment into it from the wizard, uploading the deployments kept (writing down how each went, for the dashboard to say it and a failed one to be
tried again), and bringing back what it has."""
from __future__ import annotations

from collections.abc import Iterator

from wildintel_uploader.modules.uploaders.domain.models import Account, Credentials, NotThere, UploaderError
from wildintel_uploader.modules.uploaders.domain.ports import Deployment, KeptCollections, Trapper, UploadersService, UploadReports


class UploadersUseCases(UploadersService):
    def __init__(self, trapper: Trapper, kept: KeptCollections, reports: UploadReports) -> None:
        self._trapper, self._kept, self._reports = trapper, kept, reports

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
        result = self._trapper.ask("test_connection", credentials)
        self._trapper.keep_account(credentials)   # once it works, so that it needn't be typed again
        return result

    def research_projects(self, account: Account) -> list[dict]:
        return self._trapper.ask("list_research_projects", self._trapper.credentials(account))

    def classification_projects(self, account: Account, research_project_pk: int) -> list[dict]:
        return self._trapper.ask("list_classification_projects", self._trapper.credentials(account), research_project_pk)

    def locations(self, account: Account, research_project_pk: int) -> list[dict]:
        return self._trapper.ask("list_locations", self._trapper.credentials(account), research_project_pk)

    def deployments(self, account: Account, research_project_pk: int) -> list[dict]:
        return self._trapper.ask("list_deployments", self._trapper.credentials(account), research_project_pk)

    # importing a deployment into TRAPPER from the wizard

    def import_deployment(self, account: Account, research_project_pk: int, classification_project_pk: int | None, source_dir: str, deployment: Deployment,
                          research_project_id: str | None, register: bool, timezone: str | None = None) -> Iterator[dict]:
        credentials = self._trapper.credentials(account)
        # the timezone and the summer-time setting are the kept location's — the only source of them, whatever the request carries — unless one is given
        time = ({"timezone": timezone} if timezone else
                self._kept.location_time(research_project_id, deployment.location_id) if research_project_id else {})
        return self._trapper.import_deployment(credentials, research_project_pk, classification_project_pk, source_dir, deployment, time.get("timezone"),
                                               research_project_id, time.get("ignore_dst", False), register)

    # uploading the deployments kept

    def collections(self, project: str) -> list[dict]:
        return self._kept.collections(project)

    def project_classification_projects(self, account: Account, project: str) -> list[dict]:
        credentials = self._trapper.credentials(account)
        record = self._record(project)
        return self._trapper.ask("list_classification_projects", credentials, self._trapper.find_research_project(credentials, record))

    def check_selection(self, account: Account, project: str, collection: str | None) -> list[dict]:
        credentials = self._trapper.credentials(account)
        return self._trapper.check_selection(credentials, self._record(project), collection, self._trapper.describe)

    def check_access(self, account: Account, project: str, collection: str | None, deployment_ids: list[str],
                     classification_project_pk: int | None) -> list[dict]:
        credentials = self._trapper.credentials(account)
        record = self._record(project)
        location_ids: list[str] = []
        if collection:
            collection_dir = self._kept.collection_dir(project, collection)
            location_ids = [loc for d in deployment_ids if (loc := self._kept.location_of(collection_dir, d))]
        return self._trapper.check_access(credentials, record, location_ids, classification_project_pk, self._trapper.describe)

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
        if not (collection_dir / deployment_id).is_dir():
            raise NotThere(f"{deployment_id} isn't in the collection {collection}.")
        events = self._trapper.upload(credentials, record, collection_dir, deployment_id, mode, classification_project_pk, delete_files)

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

    # bringing back what TRAPPER has

    def collection_names(self, account: Account, research_project_pk: int, classification_project_pk: int) -> list[dict]:
        return self._trapper.collection_names(self._trapper.credentials(account), research_project_pk, classification_project_pk)

    def sync(self, account: Account, project: dict, classification_project_pk: int, collections: list[str], deployments: list[str] | None,
             download_images: bool) -> Iterator[dict]:
        credentials = self._trapper.credentials(account)
        self._kept.check_project_dir(project["acronym"] or str(project["pk"]))
        return self._trapper.sync(credentials, project, classification_project_pk, collections, deployments, download_images)
