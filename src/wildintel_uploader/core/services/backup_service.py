"""Moved to `wildintel_uploader.modules.backup.infrastructure.backup_service` (#248): this name is that very module — not a copy —, so that what imports or patches it here keeps
working."""
import sys

from wildintel_uploader.modules.backup.infrastructure import backup_service as _moved

sys.modules[__name__] = _moved
