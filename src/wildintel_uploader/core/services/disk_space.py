"""Moved to `wildintel_uploader.modules.deployments.infrastructure.disk_space` (#248): this name is that very module — not a copy —, so that what imports or patches it here keeps
working."""
import sys

from wildintel_uploader.modules.deployments.infrastructure import disk_space as _moved

sys.modules[__name__] = _moved
