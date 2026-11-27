"""The use cases of the deployments: most ask their ports; bringing a deployment into a local collection puts the modules together — the visit it
is of (modules.visits), the timezone of its location, and the preprocessing (modules.preprocessing) or a copy as it is."""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from wildintel_uploader.modules.deployments.application.statistics import RevisionStatistics
from wildintel_uploader.modules.deployments.domain.models import DeploymentMissing, DeploymentsFailed
from wildintel_uploader.modules.deployments.domain.ports import (
    Cards, CollectionLayout, Deployment, DeploymentsService, Folders, ImportSessions, Photos, Repairs,
)
from wildintel_uploader.modules.preprocessing.domain.models import PreprocessingError, PreprocessOptions
from wildintel_uploader.modules.preprocessing.domain.ports import PreprocessingService
from wildintel_uploader.modules.visits.domain.models import VisitsError
from wildintel_uploader.modules.visits.domain.ports import VisitsService


class DeploymentsUseCases(DeploymentsService):
    def __init__(self, cards: Cards, folders: Folders, revisions: RevisionStatistics, photos: Photos, *, visits: VisitsService,
                 preprocessing: PreprocessingService, repairs: Repairs | None = None, statistics: RevisionStatistics | None = None,
                 sessions: ImportSessions | None = None, layout: CollectionLayout | None = None) -> None:
        self._cards, self._folders, self._revisions, self._photos = cards, folders, revisions, photos
        self._visits, self._preprocessing, self._repairs, self._statistics = visits, preprocessing, repairs, statistics
        self._sessions, self._layout = sessions, layout

    def layout(self) -> CollectionLayout:
        return self._layout

    # the memory card

    def copy_card(self, path: str) -> Iterator[dict]:
        return self._cards.copy(path)

    def eject_card(self, path: str) -> dict:
        return self._cards.eject(path)

    def discard_card_copy(self, path: str) -> bool:
        return self._cards.discard(path)

    # a folder of images

    def scan_folder(self, folder: Path) -> dict:
        result = self._folders.scan(folder)
        if result["image_count"]:
            self._folders.read_ahead(folder)
        return result

    def guess_details(self, folder: Path) -> dict:
        return self._folders.guess(folder)

    def scan_session(self, folder: Path) -> dict:
        return self._folders.scan_session(folder)

    # the collections

    def check_collection(self, folder: Path) -> dict:
        return self._folders.check_collection(folder)

    def collection_path(self, project: str, deployment_id: str) -> dict:
        path = self._folders.default_collection(project, deployment_id)
        return {"path": str(path), "collection": path.name, **self._folders.check_collection(path)}

    def existing(self, project: str, deployment_ids: list[str]) -> dict[str, str | None]:
        return {d: (str(found) if (found := self._folders.kept(project, d)) else None) for d in deployment_ids}

    def local_deployments(self, folder: Path) -> list[dict]:
        return self._folders.local_deployments(folder)

    def imported_images(self, project: str, exclude_deployment: str | None = None) -> dict[str, list[dict]]:
        return self._folders.imported(project, exclude_deployment)

    def log_entry(self, project: str, deployment_id: str) -> dict:
        return self._folders.log_entry(project, deployment_id)

    def seal_status(self, project: str, deployment_id: str) -> dict:
        dest = self._folders.kept(project, deployment_id)
        if dest is None:
            raise DeploymentMissing(f"{deployment_id} isn't in the collections folder.")
        return self._folders.seal_status(dest)

    def previous(self, project: str, deployment_ids: list[str]) -> dict[str, dict | None]:
        return {d: self._revisions.previous(project, d) for d in deployment_ids}

    def next_revision(self, project: str, location_id: str) -> dict:
        return self._revisions.next(project, location_id)

    def previous_revisions(self, project: str, deployment_id: str) -> list[dict]:
        return self._revisions.before(project, deployment_id)

    # importing one

    def _require_visit(self, collection_dir: str, deployment_id: str) -> None:
        """A deployment is always of a visit: a collection of a research project kept in the collections folder takes only the deployments its
        visits say — or one already linked to a visit —; one that is not is refused before any image is touched."""
        folder = Path(collection_dir).expanduser().resolve().parent
        if folder.parent != self._folders.root().expanduser().resolve():
            return  # not a research project's collection: there are no visits to ask
        try:
            known = self._visits.has_deployment(folder.name, deployment_id)
        except VisitsError as exc:
            raise DeploymentsFailed(exc.message) from exc
        if not known:
            raise DeploymentsFailed(f"The deployment {deployment_id or '(none)'} is not of any visit of {folder.name}: a deployment is always linked to a "
                                    "visit. Register the visits first, by hand or from a file with their history.")

    def import_local(self, source_dir: str, collection_dir: str, collection_name: str | None, deployment: Deployment, preprocessing: dict | None,
                     consolidate: bool = True) -> Iterator[dict]:
        self._require_visit(collection_dir, deployment.deployment_id)
        if preprocessing is None:
            return self._folders.copy_as_it_is(source_dir, collection_dir, collection_name, deployment)
        # the collection sits in its research project's folder: the images are read in the timezone of the location kept there — the only place it is set
        time = self._folders.location_time(Path(collection_dir).expanduser().parent, deployment.location_id)
        if not time.get("timezone"):
            raise DeploymentsFailed(f"The location {deployment.location_id or '(none)'} has no timezone: set it in the location's time settings first.")
        options = PreprocessOptions(**{**preprocessing, "timezone": time["timezone"], "ignore_dst": time.get("ignore_dst", True)})
        try:
            return self._preprocessing.preprocess(Path(source_dir), Path(collection_dir), collection_name, deployment, options, consolidate)
        except PreprocessingError as exc:
            raise DeploymentsFailed(str(exc)) from exc

    def consolidate(self, source_dir: str, collection_dir: str, deployment: Deployment) -> Iterator[dict]:
        try:
            return self._preprocessing.consolidate(Path(source_dir), Path(collection_dir), deployment)
        except PreprocessingError as exc:
            raise DeploymentsFailed(str(exc)) from exc

    def organize(self, research_project_id: str, source_dir: str, deployment: Deployment) -> tuple[Path, Iterator[dict]]:
        return self._folders.organize(research_project_id, source_dir, deployment)

    # checking and repairing those kept, and the statistics of a revision

    def repair_collections(self, project: str) -> list[dict]:
        return self._repairs.collections(project)

    def inspect(self, project: str, collection: str, deployment_id: str) -> dict:
        return self._repairs.inspect(project, collection, deployment_id)

    def repair(self, project: str, collection: str, deployment_id: str) -> Iterator[dict]:
        return self._repairs.repair(project, collection, deployment_id)

    def revision_statistics(self, project: str, collection: str) -> list[dict]:
        return self._statistics.revision(project, collection)

    def compare(self, project: str, first: str, second: str) -> dict:
        return self._statistics.compare(project, first, second)

    # the sessions of the wizard

    def sessions(self) -> ImportSessions:
        return self._sessions

    # its photos

    def photos(self, project: str, collection: str, deployment_id: str) -> list[dict]:
        return self._photos.list(project, collection, deployment_id)

    def photo(self, project: str, collection: str, deployment_id: str, name: str, large: bool = False) -> bytes:
        return self._photos.jpeg(project, collection, deployment_id, name, large)
