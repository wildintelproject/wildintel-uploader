"""Moved to `wildintel_uploader.modules.catalog.infrastructure.status_history` (#248): this name is that very module — not a copy —, so that what imports or patches it here keeps
working."""
import sys

from wildintel_uploader.modules.catalog.infrastructure import status_history as _moved

sys.modules[__name__] = _moved
