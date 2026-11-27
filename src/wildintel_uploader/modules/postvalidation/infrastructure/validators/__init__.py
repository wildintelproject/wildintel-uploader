"""The validators of a deployment — each a class in a file of its own (#246) —, and their registry: the order they run in, which is the order the
pages list them in; the statistical checks (statistics_service) come after them."""
from __future__ import annotations

from wildintel_uploader.modules.postvalidation.domain.validators import DeploymentValidator
from wildintel_uploader.modules.postvalidation.infrastructure.validators.camera_of_the_deployment import CameraOfTheDeployment
from wildintel_uploader.modules.postvalidation.infrastructure.validators.collection_name import CollectionName
from wildintel_uploader.modules.postvalidation.infrastructure.validators.collection_prefix import CollectionPrefix
from wildintel_uploader.modules.postvalidation.infrastructure.validators.deployment_id import DeploymentId
from wildintel_uploader.modules.postvalidation.infrastructure.validators.location import LocationOfTheId
from wildintel_uploader.modules.postvalidation.infrastructure.validators.photo_count import PhotoCount
from wildintel_uploader.modules.postvalidation.infrastructure.validators.sd_card import SdCardOfTheVisit
from wildintel_uploader.modules.postvalidation.infrastructure.validators.statistics import ImageCount, SequenceCount, SequenceLength
from wildintel_uploader.modules.postvalidation.infrastructure.validators.time_range import TimeRange

VALIDATORS: tuple[type[DeploymentValidator], ...] = (
    DeploymentId, CollectionPrefix, CollectionName, LocationOfTheId, TimeRange, CameraOfTheDeployment, SdCardOfTheVisit, PhotoCount,
    ImageCount, SequenceCount, SequenceLength,
)
