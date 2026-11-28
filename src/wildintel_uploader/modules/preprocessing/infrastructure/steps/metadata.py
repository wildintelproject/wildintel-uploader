"""The XMP of the images prepared — authorship, rights and license, with the hash of the original (Source) and of the image kept (Identifier) —,
written with ExifTool, in batches: the files and their tags go in on stdin, so no command line limit is in the way."""
from __future__ import annotations

import subprocess
from collections.abc import Iterator
from pathlib import Path

from wildintel_uploader.modules.preprocessing.domain.models import ImageWork, PreprocessingError, PreprocessOptions, xmp_tags
from wildintel_uploader.modules.preprocessing.domain.steps import FolderStep, Job
from wildintel_uploader.modules.preprocessing.infrastructure.images import mime

_XMP_BATCH = 200  # files per ExifTool run
EXIFTOOL_TMP_SUFFIX = "_exiftool_tmp"  # what ExifTool adds to a file's name while it rewrites it


def write_xmp_batches(exiftool_path: str, items: list[tuple[Path, dict[str, str]]]) -> Iterator[int]:
    """Writes each file's own tags, in place, with one ExifTool run per batch, yielding how many files are written after each batch, for the
    progress and the time left.

    ExifTool writes each file to a "<file>_exiftool_tmp" and renames it over the original; one it was interrupted in the middle of (a failure, the
    app being stopped) is left behind, so those are removed however this ends."""
    try:
        for start in range(0, len(items), _XMP_BATCH):
            lines: list[str] = []
            for path, tags in items[start:start + _XMP_BATCH]:
                lines += [f"-{tag}={value.replace(chr(10), ' ')}" for tag, value in tags.items()]
                lines += [str(path), "-execute"]
            completed = subprocess.run(
                [exiftool_path, "-@", "-", "-common_args", "-overwrite_original", "-charset", "filename=utf8", "-charset", "utf8"],
                input="\n".join(lines) + "\n", capture_output=True, text=True, encoding="utf-8", check=False,
            )
            if completed.returncode != 0 or "error" in completed.stderr.lower():
                raise PreprocessingError(f"ExifTool could not write the metadata: {(completed.stderr or completed.stdout).strip()[:300]}")
            yield min(start + _XMP_BATCH, len(items))
    finally:
        for folder in {path.parent for path, _ in items}:
            for leftover in folder.glob(f"*{EXIFTOOL_TMP_SUFFIX}"):
                leftover.unlink(missing_ok=True)


class XmpMetadata(FolderStep):
    key = "metadata"
    label = "Metadata"

    def wanted(self, options: PreprocessOptions) -> bool:
        return options.metadata

    def check(self, job: Job) -> None:
        if job.exiftool is None:
            raise PreprocessingError("Adding metadata needs ExifTool, and it isn't installed.")

    def run(self, works: list[ImageWork], job: Job) -> Iterator[dict]:
        if not works:
            return
        yield {"type": "metadata", "index": 0, "total": len(works)}
        items = [(w.record["_target"], xmp_tags(job.options, job.deployment, camera=w.record["camera"], date=w.record["_date"],
                                                mime=mime(w.record["_target"]), source_hash=w.record["source_hash"], image_hash=w.record["hash"]))
                 for w in works]
        for written in write_xmp_batches(job.exiftool or "exiftool", items):
            yield {"type": "metadata", "index": written, "total": len(works)}
