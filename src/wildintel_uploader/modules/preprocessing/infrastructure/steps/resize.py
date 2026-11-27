"""The image kept, resized to a width keeping its proportions — unlike wildintel-tools, where the resized image only fed the hash of the identifier,
the resized image is what is kept —; one no wider than that, or when resizing is not asked for, copied as it is. The EXIF and the colour profile are
kept, and a JPEG is saved at the quality it already had."""
from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path

from PIL import Image, JpegImagePlugin

from wildintel_uploader.modules.preprocessing.domain.models import ImageWork
from wildintel_uploader.modules.preprocessing.domain.steps import ImageStep, Job
from wildintel_uploader.modules.preprocessing.infrastructure.images import dimensions

_JPEG_QUALITY = 90  # only when the original's own JPEG settings can't be read


def _jpeg_settings(img: Image.Image) -> dict:
    """The original's JPEG quantization tables and chroma subsampling, so the resized image is saved at the quality it already had instead of a
    fixed one (which could make it heavier than the original). Falls back to a fixed quality."""
    tables = getattr(img, "quantization", None)
    if img.format != "JPEG" or not tables:
        return {"quality": _JPEG_QUALITY}
    settings: dict = {"qtables": tables}
    try:
        sampling = JpegImagePlugin.get_sampling(img)
        if sampling != -1:
            settings["subsampling"] = sampling
    except Exception:  # noqa: BLE001
        pass
    return settings


def resize_to_width(source: Path, dest: Path, width: int, on_decoded: Callable[[Path], None] | None = None) -> bool:
    """Writes source to dest, resized to `width` pixels wide keeping its proportions — or just copies it if it isn't wider than that. True if it
    was resized. Resizing decodes the image in full: one resized without an error is told to `on_decoded` — what is known of the files keeps it as
    not corrupted. One that is only copied is not opened in full, so nothing is said of it."""
    with Image.open(source) as img:
        if img.width <= width:
            shutil.copy2(source, dest)
            return False
        height = max(1, round(img.height * width / img.width))
        resized = img.resize((width, height), Image.LANCZOS)
        keep = {key: img.info[key] for key in ("exif", "icc_profile") if key in img.info}
        fmt = img.format or "JPEG"
        if fmt == "JPEG":
            resized = resized.convert("RGB") if resized.mode not in ("RGB", "L") else resized
            resized.save(dest, format="JPEG", **_jpeg_settings(img), **keep)
        else:
            resized.save(dest, format=fmt, **keep)
    if on_decoded:
        on_decoded(source)
    return True


class ResizeOrCopy(ImageStep):
    key = "resize"
    label = "Resize"

    def run(self, work: ImageWork, job: Job) -> None:
        target: Path = work.record["_target"]
        original_width, original_height = dimensions(work.source)
        if job.options.resize:
            resized = resize_to_width(work.source, target, job.options.resize_width, job.info.mark_decoded)
        else:
            shutil.copy2(work.source, target)
            resized = False
        width, height = dimensions(target) if resized else (original_width, original_height)
        # how big the image was and is — before the metadata, which adds a few kilobytes — to see that it was resized as asked
        work.record.update({"resized": resized, "original_width": original_width, "original_height": original_height,
                            "original_bytes": work.source.stat().st_size, "width": width, "height": height, "bytes": target.stat().st_size})
