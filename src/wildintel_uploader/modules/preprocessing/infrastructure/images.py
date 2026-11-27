"""What the steps and the folders read of an image file: its size in pixels, its type, the SHA-1 of its content."""
from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image


def dimensions(path: Path) -> tuple[int | None, int | None]:
    """Only the header is read."""
    try:
        with Image.open(path) as img:
            return img.width, img.height
    except Exception:  # noqa: BLE001 — what can't be read has no size
        return None, None


def mime(path: Path) -> str:
    try:
        with Image.open(path) as img:
            return Image.MIME.get(img.format or "", "application/octet-stream")
    except Exception:  # noqa: BLE001
        return "application/octet-stream"


def sha1(path: Path) -> str:
    digest = hashlib.sha1()  # noqa: S324 — an identifier, not a security measure; what wildintel-tools used
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
