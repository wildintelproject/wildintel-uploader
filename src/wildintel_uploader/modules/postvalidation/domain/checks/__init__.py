"""The validators of a deployment — each a class in a file of its own (#246) —, and their registry: the order they run in, which is the order the
pages list them in; the statistical checks (judged against the history the deployments keep) come after them."""
from __future__ import annotations

from wildintel_uploader.modules.postvalidation.domain.validators import DeploymentValidator
from wildintel_uploader.modules.postvalidation.domain.checks.camera_of_the_deployment import CameraOfTheDeployment
from wildintel_uploader.modules.postvalidation.domain.checks.collection_name import CollectionName
from wildintel_uploader.modules.postvalidation.domain.checks.collection_prefix import CollectionPrefix
from wildintel_uploader.modules.postvalidation.domain.checks.deployment_id import DeploymentId
from wildintel_uploader.modules.postvalidation.domain.checks.location import LocationOfTheId
from wildintel_uploader.modules.postvalidation.domain.checks.photo_count import PhotoCount
from wildintel_uploader.modules.postvalidation.domain.checks.sd_card import SdCardOfTheVisit
from wildintel_uploader.modules.postvalidation.domain.checks.statistics import ImageCount, SequenceCount, SequenceLength
from wildintel_uploader.modules.postvalidation.domain.checks.time_range import TimeRange

VALIDATORS: tuple[type[DeploymentValidator], ...] = (
    DeploymentId, CollectionPrefix, CollectionName, LocationOfTheId, TimeRange, CameraOfTheDeployment, SdCardOfTheVisit, PhotoCount,
    ImageCount, SequenceCount, SequenceLength,
)
