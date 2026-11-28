"""Sealing a deployment and verifying its seal: the checks the settings turn on run over the source images — the prevalidation's and the
postvalidation's, through their contracts, the statistical ones against the previous revisions of the location kept here —, and seal.json says
what they found, tied by hashes to what the deployment holds. What the seal says is the domain's (domain.seal)."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from wildintel_uploader.modules.catalog.domain.ports import CatalogEquipment
from wildintel_uploader.modules.deployments.application.statistics import RevisionStatistics
from wildintel_uploader.modules.deployments.domain import seal as rules
from wildintel_uploader.modules.deployments.domain.ports import CheckSettings, Deployment, SealedFolder
from wildintel_uploader.modules.postvalidation.domain.models import Deployment as CheckedDeployment, DeploymentContext
from wildintel_uploader.modules.postvalidation.domain.ports import PostvalidationService
from wildintel_uploader.modules.prevalidation.domain.ports import PrevalidationService


class Sealing:
    """`catalog_of` and `revisions_of` give the catalog and the statistics of a collections folder: the one the deployment is kept in."""

    def __init__(self, folder: SealedFolder, settings: CheckSettings, *, prevalidation: Callable[[], PrevalidationService],
                 postvalidation: Callable[[], PostvalidationService], catalog_of: Callable[[Path], CatalogEquipment],
                 revisions_of: Callable[[Path], RevisionStatistics], now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> None:
        self._folder, self._settings, self._prevalidation, self._postvalidation = folder, settings, prevalidation, postvalidation
        self._catalog_of, self._revisions_of, self._now = catalog_of, revisions_of, now

    def _camera(self, collections_dir: Path, research_project_id: str, label: str | None) -> dict | None:
        """The record of the deployment's camera in the catalog, as the checks of the camera read it."""
        camera = self._catalog_of(collections_dir).camera(research_project_id, label) if label else None
        if camera is None:
            return None
        return {"label": camera.label, "camera_id": camera.camera_id, "camera_make": camera.camera_make, "camera_model": camera.camera_model}

    def run_checks(self, source: Path, dest: Path, deployment: Deployment) -> dict:
        """Runs the checks the settings turn on over the source images — those of the deployment alone: the ones of the visit need the wizard —:
        what the seal says they found (domain.seal.checked)."""
        validation, post = self._settings.validation(), self._settings.postvalidation()
        prevalidation, postvalidation = self._prevalidation(), self._postvalidation()
        deployment_validators = postvalidation.validators()
        image_checks = rules.turned_on(validation, tuple(v.key for v in prevalidation.validators()))
        deployment_checks = rules.turned_on(post, tuple(v.key for v in deployment_validators if not v.of_the_visit and not v.statistical))
        stat_checks = rules.turned_on(post, tuple(v.key for v in deployment_validators if v.statistical))
        collections_dir, research_project_id = dest.parent.parent.parent, dest.parent.parent.name

        found = prevalidation.validate(source, prevalidation.validators(image_checks), detail=True, exif_fields=validation.exif_fields,
                                       camera_levels=validation.camera_levels)
        context = DeploymentContext(
            deployment=CheckedDeployment(deployment_id=deployment.deployment_id, start_date=deployment.start_date, end_date=deployment.end_date,
                                         camera_model=deployment.camera_model, camera_id=deployment.camera_id),
            collection=dest.parent.name, expected_location_id=deployment.location_id, tolerance_hours=post.tolerance_hours,
            camera=self._camera(collections_dir, research_project_id, deployment.camera_id), camera_levels=validation.camera_levels,
            research_project_id=research_project_id,
            statistics={"sequence_gap_seconds": post.sequence_gap_seconds, "min_revisions": post.min_revisions, "method": post.similarity_method,
                        "image_count_tolerance": post.image_count_tolerance, "sequence_count_tolerance": post.sequence_count_tolerance,
                        "sequence_length_tolerance": post.sequence_length_tolerance},
            previous=tuple(self._revisions_of(collections_dir).revisions_before(research_project_id, deployment.deployment_id)) if stat_checks else (),
        )
        consistency = postvalidation.validate(source, context, postvalidation.validators(deployment_checks | stat_checks))
        return rules.checked(self._folder.images(source), found, consistency, image_checks, deployment_checks, stat_checks)

    def seal(self, source: Path, dest: Path, deployment: Deployment, *, originals: dict[str, str] | None = None, source_hashes: dict[str, str] | None = None,
             preprocessing: dict | None = None, recovered: bool = False) -> dict:
        """Checks the source images, then writes dest/seal.json for what the import left in dest. Returns what was written."""
        checks = self.run_checks(source, dest, deployment)
        names = self._folder.images(dest)
        written = rules.body(deployment.deployment_id, self._now().isoformat(timespec="seconds"), self._folder.metadata_hash(dest), checks,
                             list(zip(names, self._folder.hashes(dest, names))), originals=originals, source_hashes=source_hashes,
                             preprocessing=preprocessing, recovered=recovered)
        self._folder.write_seal(dest, written)
        return written

    def verify(self, dest: Path) -> dict:
        """Whether dest is still what its seal says: {"status": "none" | "valid" | "broken", "changed", "missing", "added", "deployment_changed",
        "seal_changed"}. "none" is a deployment never sealed."""
        try:
            seal = self._folder.read_seal(dest)
            if seal is None:
                return dict(rules.NOT_SEALED)
            images, metadata_hash, seal_changed = rules.recorded(seal)
        except (ValueError, KeyError, TypeError):
            return {**rules.NOT_SEALED, "status": "broken", "seal_changed": True}
        present = self._folder.images(dest)
        there = [n for n in images if n in present]
        now = dict(zip(there, self._folder.hashes(dest, there)))
        current = self._folder.metadata_hash(dest)
        return rules.verdict(images, now, present, current is None or current != metadata_hash, seal_changed)
