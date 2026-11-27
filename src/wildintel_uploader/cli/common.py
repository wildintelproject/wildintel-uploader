"""Moved to `wildintel_uploader.entrypoints.cli.common` (#248): this name is that very module — not a copy —, so that what imports it here (the script
of pyproject.toml, the desktop launcher, the tests) keeps working."""
import sys

from wildintel_uploader.entrypoints.cli import common as _moved

sys.modules[__name__] = _moved
