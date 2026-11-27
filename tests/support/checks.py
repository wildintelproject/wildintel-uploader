"""The validations as the code of before calls them — validate_images, validate_deployment_consistency and the lists of checks —, over the modules
of the prevalidation and of the postvalidation (#248): the names of the checks are their validators' keys, and each call asks the module's contract.
What a module refuses is a DeploymentImportError, with its words, as it was."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from wildintel_uploader.modules.deployments.infrastructure.deployment_import_service import DeploymentImportError
from wildintel_uploader.modules.fileinfo.domain import models as _fileinfo
from wildintel_uploader.modules.postvalidation.domain import models as _post
from wildintel_uploader.modules.postvalidation.infrastructure import validators as _deployment_validators
from wildintel_uploader.modules.prevalidation.domain import models as _pre
from wildintel_uploader.modules.prevalidation.infrastructure import validators as _image_validators
from wildintel_uploader.shared.camtrap import DeploymentFields

# The checks of the images are the module `modules.prevalidation`, and those of a deployment `modules.postvalidation` (#248, #246): each a validator there. What is left here are the names of before, for those that call them.
IMAGE_CHECK_ORDER = tuple(c.key for c in _image_validators.VALIDATORS)
IMAGE_CHECKS = frozenset(IMAGE_CHECK_ORDER)
DEFAULT_CAMERA_LEVELS = _fileinfo.DEFAULT_CAMERA_LEVELS
_natural_key = _post.natural_key


def _wiring():
    from wildintel_uploader.entrypoints import wiring
    return wiring


def validate_images(
    source_dir: Path, checks: frozenset[str] | None = None, *, detail: bool = False, imported: dict[str, list[dict]] | None = None,
    progress: Callable[[str, int, int], None] | None = None, exif_fields: list[str] | None = None, camera_levels: list[list[str]] | None = None,
    on_check: Callable[[str, str], None] | None = None,
) -> dict:
    """The checks of the images of a folder (see modules.prevalidation): only "checked_count" and what the checks asked for found.

    Raises:
        DeploymentImportError: source_dir doesn't exist or isn't a folder.
    """
    try:
        prevalidation = _wiring().build_prevalidation()
        return prevalidation.validate(source_dir, prevalidation.validators(checks), detail=detail, imported=imported, progress=progress, exif_fields=exif_fields,
                                             camera_levels=camera_levels, on_check=on_check)
    except _pre.PrevalidationError as exc:
        raise DeploymentImportError(str(exc)) from exc


# The checks of a deployment (modules.postvalidation): those that need what the wizard knows of it, and those against the visit it
# is of — only in the wizard, where that visit is known —, in the order they run.
DEPLOYMENT_CHECK_ORDER = tuple(c.key for c in _deployment_validators.VALIDATORS if not c.statistical)
DEPLOYMENT_CHECKS = frozenset(c.key for c in _deployment_validators.VALIDATORS if not c.of_the_visit and not c.statistical)
VISIT_CHECKS = frozenset(c.key for c in _deployment_validators.VALIDATORS if c.of_the_visit)
DEFAULT_TOLERANCE_HOURS = _post.DEFAULT_TOLERANCE_HOURS


def validate_deployment_consistency(
    source_dir: Path, deployment: DeploymentFields, checks: frozenset[str] | None = None, *,
    collection_name: str | None = None, expected_location_id: str | None = None,
    tolerance_hours: float = DEFAULT_TOLERANCE_HOURS, visit: dict | None = None, camera: dict | None = None, camera_levels: list[list[str]] | None = None,
    on_check: Callable[[str, str], None] | None = None,
) -> dict:
    """The checks of a deployment — what the wizard knows of it — against its images, wildintel-tools' names and its visit (see
    modules.postvalidation): only "checked_count" and what the checks asked for found.

    Raises:
        DeploymentImportError: source_dir doesn't exist or isn't a folder, or tolerance_hours is negative.
    """
    context = _post.DeploymentContext(
        deployment=_post.Deployment(deployment_id=deployment.deployment_id, start_date=deployment.start_date, end_date=deployment.end_date,
                                                 camera_model=deployment.camera_model),
        collection=collection_name, expected_location_id=expected_location_id, tolerance_hours=tolerance_hours, visit=visit, camera=camera,
        **({"camera_levels": camera_levels} if camera_levels is not None else {}),
    )
    try:
        postvalidation = _wiring().build_postvalidation()
        # the statistical checks are run apart, against the history the deployments keep, as they always were here
        wanted = [v for v in postvalidation.validators(checks) if not v.statistical]
        return postvalidation.validate(source_dir, context, wanted, on_check=on_check)
    except _post.PostvalidationError as exc:
        raise DeploymentImportError(str(exc)) from exc


