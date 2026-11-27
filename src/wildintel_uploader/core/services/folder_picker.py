"""Moved to `wildintel_uploader.shared.desktop.folder_picker` (#248): this name is that very module — not a copy —, so that what imports or patches it here keeps
working."""
import sys

from wildintel_uploader.shared.desktop import folder_picker as _moved

sys.modules[__name__] = _moved
