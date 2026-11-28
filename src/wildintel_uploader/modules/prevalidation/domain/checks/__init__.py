"""The validators of the images — each a class in a file of its own (#246) —, and their registry: the order they run in, which is the order the
pages list them in. Adding one is a file here and a line below; the settings, the reports and the pages take its key, label and description."""
from __future__ import annotations

from wildintel_uploader.modules.prevalidation.domain.validators import ImageValidator
from wildintel_uploader.modules.prevalidation.domain.checks.cameras import Cameras
from wildintel_uploader.modules.prevalidation.domain.checks.corrupted import Corrupted
from wildintel_uploader.modules.prevalidation.domain.checks.duplicates import Duplicates
from wildintel_uploader.modules.prevalidation.domain.checks.exif_fields import ExifFields
from wildintel_uploader.modules.prevalidation.domain.checks.shooting_order import ShootingOrder
from wildintel_uploader.modules.prevalidation.domain.checks.structure import Structure

# Which images decode is known before the order of the shots, which leaves out the corrupted ones; the camera and the dates read for one are there
# for the next.
VALIDATORS: tuple[type[ImageValidator], ...] = (Corrupted, ShootingOrder, Structure, Cameras, ExifFields, Duplicates)
