"""The statistics of the deployments kept as the tests of before call them — by the collections folder — over the rules, the use cases and the
adapters the app uses (modules.deployments: domain.statistics, application.statistics, infrastructure.revision_folders)."""
from pathlib import Path
from types import SimpleNamespace

from wildintel_uploader.modules.deployments.application.statistics import RevisionStatistics
from wildintel_uploader.modules.deployments.domain import statistics as rules
from wildintel_uploader.modules.deployments.domain.models import DeploymentsError
from wildintel_uploader.modules.deployments.infrastructure import deployment_import_service as dis  # noqa: F401 — its DeploymentImportError
from wildintel_uploader.modules.deployments.infrastructure.revision_folders import STATS_FILE, RevisionFoldersOnDisk  # noqa: F401
from wildintel_uploader.modules.postvalidation.domain import statistics as judging
from wildintel_uploader.modules.postvalidation.domain.models import PostvalidationError
from wildintel_uploader.modules.postvalidation.domain.statistics import STATISTIC_CHECKS, DeploymentTimes, sequence_lengths  # noqa: F401


class _Settings:
    def __init__(self, gap: float, least: int = 2, method: str = "median", tolerances: dict | None = None) -> None:
        self.gap, self.least, self.how, self.tol = gap, least, method, tolerances or {}

    def gap_seconds(self):
        return self.gap

    def min_revisions(self):
        return self.least

    def method(self):
        return self.how

    def tolerances(self):
        return self.tol


def _folders(root: Path) -> RevisionFoldersOnDisk:
    from wildintel_uploader.entrypoints.wiring import file_info
    return RevisionFoldersOnDisk(lambda: root, file_info)


def _statistics(root: Path, settings: _Settings | None = None) -> RevisionStatistics:
    return RevisionStatistics(_folders(root), settings or _Settings(60))


def previous_revisions(root: Path, research_project_id: str, deployment_id: str) -> list:
    return [SimpleNamespace(revision=k.revision, deployment_id=k.deployment_id, path=k.where)
            for k in rules.earlier(_folders(root).kept(research_project_id), deployment_id)]


def times_of_revision(path: Path) -> DeploymentTimes:
    return _folders(path).times(path)


def times_of_folder(path: Path) -> DeploymentTimes:
    return _folders(path).times_of_folder(path)


def compare(value, previous, **kw) -> dict:
    try:
        return judging.compare(value, previous, **kw)
    except PostvalidationError as exc:
        raise dis.DeploymentImportError(str(exc)) from exc


def statistical_checks(current, root: Path, research_project_id, deployment_id: str, checks, **params) -> dict:
    if not any(c in checks for c in STATISTIC_CHECKS):
        return {}
    try:
        return judging.judge(current, _statistics(root).revisions_before(research_project_id, deployment_id), deployment_id, checks, **params)
    except PostvalidationError as exc:
        raise dis.DeploymentImportError(str(exc)) from exc


def next_revision(root: Path, research_project_id: str, location_id: str) -> dict:
    return _statistics(root).next(research_project_id, location_id)


def previous_deployment(root: Path, research_project_id: str, deployment_id: str) -> dict | None:
    return _statistics(root).previous(research_project_id, deployment_id)


def deployment_metrics(path: Path, gap_seconds: float) -> dict:
    return _statistics(path)._metrics(path, gap_seconds)


def collection_statistics(root: Path, research_project_id: str, collection: str, *, sequence_gap_seconds, min_revisions, method, tolerances) -> list[dict]:
    try:
        return _statistics(root, _Settings(sequence_gap_seconds, min_revisions, method, tolerances)).revision(research_project_id, collection)
    except DeploymentsError as exc:
        raise dis.DeploymentImportError(str(exc)) from exc


def compare_deployments(root: Path, research_project_id: str, first: str, second: str, *, sequence_gap_seconds) -> dict:
    try:
        return _statistics(root, _Settings(sequence_gap_seconds)).compare(research_project_id, first, second)
    except DeploymentsError as exc:
        raise dis.DeploymentImportError(str(exc)) from exc
