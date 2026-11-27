"""Opening a folder in the OS's file explorer. This is a local, single-user tool: the
backend runs on the same machine as the browser using it."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def open_folder(path: Path) -> None:
    """Opens `path` in the file explorer.

    Raises:
        OSError: it can't be opened.
    """
    if sys.platform.startswith("win"):
        os.startfile(path)  # type: ignore[attr-defined]
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
