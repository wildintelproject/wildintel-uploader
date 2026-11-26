"""Moved to `wildintel_uploader.shared.storage` (#248): this name is that very package — not a copy —, so that its state (the backend in use, the
registered ones) is one, and what imports or patches it here keeps working. So are its modules `base` and `json_files`."""
import sys

from wildintel_uploader.shared import storage as _moved
from wildintel_uploader.shared.storage import base as _base, json_files as _json_files

sys.modules[__name__] = _moved
sys.modules[__name__ + ".base"] = _base
sys.modules[__name__ + ".json_files"] = _json_files
