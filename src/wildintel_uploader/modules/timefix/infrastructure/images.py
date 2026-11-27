"""The images of a folder copied from a card, on disk, and their dates shifted with ExifTool — every date of the image: DateTimeOriginal,
CreateDate and ModifyDate. The folder is the one the card was copied to; the card itself is never touched."""
from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

from wildintel_uploader.modules.deployments.domain.naming import natural_key
from wildintel_uploader.modules.fileinfo.domain.models import IMAGE_EXTENSIONS
from wildintel_uploader.modules.timefix.domain.ports import DateShifter, ImageFolder, TimeFixError


class FolderOfImages(ImageFolder):
    def open(self, folder: str) -> Path:
        path = Path(folder).expanduser() if folder else None
        if path is None or not path.is_dir():
            raise TimeFixError(f"'{folder}' is not a folder.")
        return path

    def images(self, folder: Path) -> list[Path]:
        return sorted((p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS), key=lambda p: natural_key(Path(p.name)))

    def delete(self, images: list[Path]) -> None:
        for image in images:
            image.unlink()


def shift_argument(offset_seconds: int) -> str:
    """ExifTool's shift, "Y:M:D h:m:s", for an offset in seconds: "-AllDates+=0:0:400 5:30:15"."""
    sign = "+" if offset_seconds >= 0 else "-"
    days, rest = divmod(abs(offset_seconds), 86400)
    hours, rest = divmod(rest, 3600)
    minutes, seconds = divmod(rest, 60)
    return f"-AllDates{sign}=0:0:{days} {hours}:{minutes}:{seconds}"


class ExifToolShifter(DateShifter):
    """`exiftool` says where ExifTool is (modules.fileinfo), or None."""

    def __init__(self, exiftool: Callable[[], str | None]) -> None:
        self._exiftool = exiftool

    def shift(self, folder: Path, images: list[Path], offset_seconds: int) -> None:
        exiftool = self._exiftool()
        if exiftool is None:
            raise TimeFixError("Fixing the dates needs ExifTool, and it isn't installed.")
        argfile = folder / ".timefix-args.txt"
        argfile.write_text("\n".join(str(p) for p in images) + "\n", encoding="utf-8")
        try:
            result = subprocess.run([exiftool, "-charset", "filename=utf8", "-overwrite_original", "-P", shift_argument(offset_seconds), "-@", str(argfile)],
                                    capture_output=True, text=True, check=False)
        finally:
            argfile.unlink(missing_ok=True)
        if result.returncode != 0:
            raise TimeFixError(f"ExifTool could not change the dates: {(result.stderr or result.stdout).strip()}")
