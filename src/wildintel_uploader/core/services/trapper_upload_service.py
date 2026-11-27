"""Moved to `wildintel_uploader.modules.uploaders.infrastructure.trapper_upload_service` (#248): this name is that very module — not a copy —, so that what imports or patches it here keeps
working."""
import sys

from wildintel_uploader.modules.uploaders.infrastructure import trapper_upload_service as _moved

sys.modules[__name__] = _moved
