"""Moved to `wildintel_uploader.modules.uploaders.infrastructure.sync_service` (#248): this name is that very module — not a copy —, so that what imports or patches it here keeps
working."""
import sys

from wildintel_uploader.modules.uploaders.infrastructure import sync_service as _moved

sys.modules[__name__] = _moved
