"""MetadataReader with ExifTool — the executable, bundled with the builds or installed —, which reads the serial number of most camera traps from the
makers' own notes, and names every field the same whatever the make (#227). All the files in one run, their names given on stdin."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from wildintel_uploader.modules.fileinfo.domain.models import clean
from wildintel_uploader.modules.fileinfo.domain.ports import MetadataReader, MetadataReadFailed

_EXIFTOOL_TIMEOUT_SECONDS = 600


def _bundled_exiftool() -> str | None:
    """The ExifTool shipped inside the packaged executable (see the PyInstaller spec), or None when running from source or when none was bundled."""
    if not getattr(sys, "frozen", False):
        return None
    candidate = Path(sys._MEIPASS) / "exiftool" / ("exiftool.exe" if os.name == "nt" else "exiftool")  # type: ignore[attr-defined]
    if not candidate.is_file():
        return None
    if os.name != "nt" and not os.access(candidate, os.X_OK):
        try:
            candidate.chmod(candidate.stat().st_mode | 0o755)
        except OSError:
            return None
    return str(candidate)


def exiftool_path() -> str | None:
    """Where ExifTool is: the bundled one first, then the one on the PATH; None if neither exists."""
    return _bundled_exiftool() or shutil.which("exiftool")


def _tags_with_exiftool(exiftool: str, paths: list[Path], tags: list[str]) -> dict[Path, dict[str, str | None]]:
    """The value of each tag in each file, in one ExifTool run (the file names on stdin): None where a file does not have it. A file ExifTool says nothing
    of — one it could not read — is not in what is returned."""
    args = [exiftool, "-json", "-charset", "filename=utf8", "-m", *(f"-{tag}" for tag in tags), "-@", "-"]
    completed = subprocess.run(
        args, input="\n".join(str(p) for p in paths), capture_output=True, text=True, encoding="utf-8", timeout=_EXIFTOOL_TIMEOUT_SECONDS, check=False,
    )
    rows = json.loads(completed.stdout) if completed.stdout.strip() else []
    by_source = {str(Path(row.get("SourceFile", ""))): {k.lower(): v for k, v in row.items()} for row in rows}
    return {path: {tag: clean(by_source[str(path)].get(tag.lower())) for tag in tags} for path in paths if str(path) in by_source}


class ExifToolReader(MetadataReader):
    """ExifTool, wherever it is when it is asked: one installed while the app runs is found."""

    def available(self) -> bool:
        return exiftool_path() is not None

    def location(self) -> str | None:
        return exiftool_path()

    def read(self, paths: list[Path], tags: list[str]) -> dict[Path, dict[str, str | None]]:
        exiftool = exiftool_path()
        if exiftool is None:
            raise MetadataReadFailed("there is no ExifTool")
        try:
            return _tags_with_exiftool(exiftool, paths, tags)
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError, ValueError) as exc:
            raise MetadataReadFailed(str(exc)) from exc
