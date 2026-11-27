"""Moved to `wildintel_uploader.modules.settings.infrastructure.activity_log` (#248): this name is that very module — not a copy —, so that what imports or patches it here keeps working."""
import sys

from wildintel_uploader.modules.settings.infrastructure import activity_log as _moved

sys.modules[__name__] = _moved
