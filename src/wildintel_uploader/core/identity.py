"""Moved to `wildintel_uploader.shared.identity` (#248): this name is that very module — not a copy —, so that what imports or patches it here keeps working."""
import sys

from wildintel_uploader.shared import identity as _moved

sys.modules[__name__] = _moved
