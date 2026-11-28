"""The distinct cameras among the images: a deployment is one camera."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from wildintel_uploader.modules.prevalidation.domain.models import ImageOptions
from wildintel_uploader.modules.prevalidation.domain.validators import ImageValidator
from wildintel_uploader.modules.fileinfo.domain.folder import MediaFolder
from wildintel_uploader.modules.fileinfo.domain.models import SERIAL_FIELDS

def camera_groups(folder: MediaFolder, images: list[Path], levels: list[list[str]]) -> tuple[list[str], dict[tuple[str, ...], list[Path]], int]:
    """The images grouped by the camera they were taken by, as `levels` tell it — the fields of each level, the most reliable first: the images are
    compared by the first level every image has; when none, by the first that any has, and the ones that have not got it are without camera
    information. Returns the fields compared by (none when no image has any level), the groups by their values, and how many are without."""
    cameras = folder.cameras()
    asked = list(dict.fromkeys(f for level in levels for f in level if f.lower() not in SERIAL_FIELDS))
    tags = folder.tags(images, asked) if asked else {}

    def value(path: Path, field: str) -> str | None:
        return cameras[path].camera_id if field.lower() in SERIAL_FIELDS else tags.get(path, {}).get(field)

    values = {tuple(level): {p: tuple(value(p, f) for f in level) for p in images} for level in levels}
    complete = lambda level: [p for p in images if all(values[tuple(level)][p])]  # noqa: E731
    chosen = next((level for level in levels if len(complete(level)) == len(images)), None) or next((level for level in levels if complete(level)), None)
    if chosen is None:
        return [], {}, len(images)
    groups: dict[tuple[str, ...], list[Path]] = defaultdict(list)
    for path in complete(chosen):
        groups[values[tuple(chosen)][path]].append(path)   # type: ignore[index]
    return list(chosen), dict(groups), len(images) - len(complete(chosen))


class Cameras(ImageValidator):
    key = "camera"
    label = "One camera"
    description = ("The distinct cameras among the images, with how many each took and a few examples — a deployment is one camera, so more than "
                   "one means images of different cameras got mixed.")

    def run(self, folder: MediaFolder, options: ImageOptions) -> dict:
        cameras = folder.cameras()
        by, groups, without = camera_groups(folder, sorted(folder.images), options.camera_levels)
        return {
            "cameras": [
                {"model": cameras[paths[0]].model, "camera_id": cameras[paths[0]].camera_id, "values": dict(zip(by, key)),
                 "count": len(paths), "examples": [folder.relative(p) for p in paths[:3]]}
                for key, paths in sorted(groups.items(), key=lambda item: (-len(item[1]), item[0]))
            ],
            "camera_by": by,
            "cameras_without_info": without,
        }
