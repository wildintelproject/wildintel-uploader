"""The steps of the preprocessing — each a class in a file of its own (#246) —, and their registry, in the order they run: to each image, one after
the other, each on what the one before left in its record; then to all of them, once prepared."""
from __future__ import annotations

from wildintel_uploader.modules.preprocessing.domain.steps import FolderStep, ImageStep
from wildintel_uploader.modules.preprocessing.infrastructure.steps.camera import CameraOfTheImage
from wildintel_uploader.modules.preprocessing.infrastructure.steps.capture_date import CaptureDate
from wildintel_uploader.modules.preprocessing.infrastructure.steps.final_hash import FinalHashes
from wildintel_uploader.modules.preprocessing.infrastructure.steps.hashes import Hashes
from wildintel_uploader.modules.preprocessing.infrastructure.steps.metadata import XmpMetadata
from wildintel_uploader.modules.preprocessing.infrastructure.steps.rename import Rename
from wildintel_uploader.modules.preprocessing.infrastructure.steps.resize import ResizeOrCopy

IMAGE_STEPS: tuple[type[ImageStep], ...] = (CaptureDate, Rename, ResizeOrCopy, Hashes, CameraOfTheImage)
FOLDER_STEPS: tuple[type[FolderStep], ...] = (XmpMetadata, FinalHashes)
