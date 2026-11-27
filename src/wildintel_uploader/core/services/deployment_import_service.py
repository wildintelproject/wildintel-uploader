"""Moved to `wildintel_uploader.modules.deployments.infrastructure.deployment_import_service` (#248): this name is that very module — not a copy —, so that what imports or patches it here keeps
working."""
import sys

from wildintel_uploader.modules.deployments.infrastructure import deployment_import_service as _moved

sys.modules[__name__] = _moved
