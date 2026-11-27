"""Moved to `wildintel_uploader.modules.visits.domain.rules` (#248): this name is that very module — not a copy —, so that what imports or patches it here
keeps working."""
import sys

from wildintel_uploader.modules.visits.domain import rules as _moved

sys.modules[__name__] = _moved
