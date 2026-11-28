"""The reports as JSON files in the reports folder — `<date>-<time>_<kind>_<name>.json` —, the images of a folder, and an image made small
with Pillow."""
from __future__ import annotations

import io
import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from wildintel_uploader.modules.deployments.domain.naming import natural_key
from wildintel_uploader.modules.fileinfo.domain.models import IMAGE_EXTENSIONS
from wildintel_uploader.modules.reports.domain.ports import FolderImages, KeptReports, ReportMissing


class ReportFiles(KeptReports):
    """`root` says the reports folder (the settings' REPORTS dir), asked each time."""

    def __init__(self, root: Callable[[], Path]) -> None:
        self._root = root

    def keep(self, report: dict, kind: str, name: str) -> str:
        root = self._root()
        root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        report_id, n = f"{stamp}_{kind}_{name}", 1
        while (root / f"{report_id}.json").exists():   # two reports in the same second do not overwrite each other
            n += 1
            report_id = f"{stamp}_{kind}_{name}-{n}"
        tmp = root / f"{report_id}.json.tmp"
        tmp.write_text(json.dumps({**report, "id": report_id}, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(root / f"{report_id}.json")
        return report_id

    def _path(self, report_id: str) -> Path:
        path = self._root() / f"{report_id}.json"
        if not path.is_file():
            raise ReportMissing(f"There is no report '{report_id}'.")
        return path

    def read(self, report_id: str) -> dict:
        return json.loads(self._path(report_id).read_text(encoding="utf-8"))

    def all(self) -> list[dict]:
        root = self._root()
        out = []
        for path in sorted(root.glob("*.json"), reverse=True) if root.is_dir() else []:
            try:
                out.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                continue
        return out

    def delete(self, report_id: str) -> None:
        self._path(report_id).unlink()


class ImagesOnDisk(FolderImages):
    def images(self, folder: Path) -> list[str]:
        return [str(p.relative_to(folder)) for p in sorted(
            (p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS), key=lambda p: natural_key(p.relative_to(folder)),
        )]

    def small(self, folder: Path, relative: str, size: int) -> bytes:
        from PIL import Image, ImageOps

        folder = folder.resolve()
        path = (folder / relative).resolve()
        if folder not in path.parents or not path.is_file():
            raise ReportMissing(f"The report doesn't have the image '{relative}'.")
        try:
            with Image.open(path) as opened:
                img = ImageOps.exif_transpose(opened)
                img.thumbnail((size, size))
                out = io.BytesIO()
                img.convert("RGB").save(out, "JPEG", quality=75)
                return out.getvalue()
        except Exception as exc:
            raise ReportMissing(f"'{relative}' can't be shown: {exc}") from exc
