"""The statistics of the deployments kept: each deployment of a revision against the previous revisions of its location, two deployments side by
side, and what an import is filled from (the closest earlier revision of the location, the revision a new one is expected to be). The rules are
the domain's (domain.statistics, and the judging of modules.postvalidation); the folders kept and the settings are its ports."""
from __future__ import annotations

from wildintel_uploader.modules.deployments.domain import statistics as rules
from wildintel_uploader.modules.deployments.domain.models import DeploymentMissing, DeploymentsFailed
from wildintel_uploader.modules.deployments.domain.ports import RevisionFolders, StatisticsSettings
from wildintel_uploader.modules.postvalidation.domain import statistics as judging
from wildintel_uploader.modules.postvalidation.domain.models import PostvalidationError
from wildintel_uploader.modules.postvalidation.domain.statistics import Revision


class RevisionStatistics:
    def __init__(self, folders: RevisionFolders, settings: StatisticsSettings) -> None:
        self._folders, self._settings = folders, settings

    # ── the history of a location ──

    def revisions_before(self, project: str | None, deployment_id: str) -> list[Revision]:
        """The previous revisions of the location of a deployment, with when their images were taken — oldest first."""
        if not project:
            return []
        return [Revision(k.revision, k.deployment_id, self._folders.times(k.where)) for k in rules.earlier(self._folders.kept(project), deployment_id)]

    def before(self, project: str, deployment_id: str) -> list[dict]:
        return [{"revision": r.revision, "deployment_id": r.deployment_id, "image_count": r.times.image_count, "times": list(r.times.times)}
                for r in self.revisions_before(project, deployment_id)]

    def previous(self, project: str, deployment_id: str) -> dict | None:
        """What was kept of the closest earlier revision of the deployment's location — {"revision", "deployment_id", "deployment"} —, or None
        (R0002-DONA_01 is filled from R0001-DONA_01)."""
        for previous in reversed(rules.earlier(self._folders.kept(project), deployment_id)):
            details = self._folders.details(previous.where)
            if isinstance(details, dict):
                return {"revision": previous.revision, "deployment_id": previous.deployment_id, "deployment": details}
        return None

    def next(self, project: str, location_id: str) -> dict:
        return rules.next_revision(self._folders.kept(project), location_id)

    # ── the metrics ──

    def _metrics(self, where: object, gap_seconds: float) -> dict:
        """A deployment's metrics, kept beside it while its images.json and the gap are the same — so the history of a location is not read again
        for each collection."""
        cached = self._folders.cached_metrics(where, gap_seconds)
        if cached is not None:
            return cached
        metrics = rules.deployment_metrics(self._folders.times(where), gap_seconds)
        self._folders.keep_metrics(where, gap_seconds, metrics)
        return metrics

    def revision(self, project: str, collection: str) -> list[dict]:
        """Each deployment of a collection against the previous revisions of its location — {"deployment_id", "location", "revision", "metrics",
        "checks", "status", "revisions"} —, as the settings of the postvalidation say. `status` is "review" if a check is not similar,
        "insufficient_history" if none could be judged, else "ok". DeploymentMissing when the collection isn't there."""
        deployments = self._folders.in_collection(project, collection)
        if deployments is None:
            raise DeploymentMissing(f"The collection '{collection}' isn't in the research project '{project}'.")
        gap, method, tolerances, least = self._settings.gap_seconds(), self._settings.method(), self._settings.tolerances(), self._settings.min_revisions()
        kept = self._folders.kept(project)
        rows: list[dict] = []
        for deployment in deployments:
            now = self._metrics(deployment.where, gap)
            history = [(r, m) for r in rules.earlier(kept, deployment.deployment_id) if (m := self._metrics(r.where, gap))["image_count"]]
            checks: dict[str, dict] = {}
            for key in judging.STATISTIC_CHECKS:
                try:
                    result = judging.compare(now[key], [m[key] for _, m in history], method=method, tolerance_percent=tolerances[key], min_revisions=least)
                except PostvalidationError as exc:
                    raise DeploymentMissing(str(exc)) from exc
                result["message"] = judging.describe(judging.LABELS[key], judging.UNITS[key], result, method=method, tolerance_percent=tolerances[key],
                                                     min_revisions=least, location=deployment.location)
                result["history"] = [{"revision": r.revision, "deployment_id": r.deployment_id, "value": m[key]} for r, m in history]
                checks[key] = result
            judged = [c for c in checks.values() if not c["skipped"]]
            status = "insufficient_history" if not judged else ("ok" if all(c["ok"] for c in judged) else "review")
            revisions = [{"revision": r.revision, "deployment_id": r.deployment_id, "metrics": rules.without_daily(m)} for r, m in history]
            revisions.append({"revision": deployment.revision, "deployment_id": deployment.deployment_id, "metrics": rules.without_daily(now)})
            rows.append({"deployment_id": deployment.deployment_id, "location": deployment.location, "revision": deployment.revision, "metrics": now,
                         "checks": checks, "status": status, "revisions": revisions})
        return rows

    def compare(self, project: str, first: str, second: str) -> dict:
        """Two deployments side by side — typically the same location in two revisions."""
        kept = {k.deployment_id: k for k in self._folders.kept(project)}
        for deployment_id in (first, second):
            if deployment_id not in kept:
                raise DeploymentsFailed(f"The deployment '{deployment_id}' isn't in the research project '{project}'.")
        gap = self._settings.gap_seconds()
        return rules.side_by_side(first, second, self._metrics(kept[first].where, gap), self._metrics(kept[second].where, gap))
