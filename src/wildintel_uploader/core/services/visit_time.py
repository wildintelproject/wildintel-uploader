"""Moved to `wildintel_uploader.modules.visits.domain.wall_clock` (#248): this name is that very module — not a copy —, so that what imports or patches it here
keeps working."""
import sys

from wildintel_uploader.modules.visits.domain import wall_clock as _moved

sys.modules[__name__] = _moved
