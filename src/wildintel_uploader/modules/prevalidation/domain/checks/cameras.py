"""The distinct cameras among the images: a deployment is one camera."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from wildintel_uploader.modules.prevalidation.domain.models import ImageOptions
from wildintel_uploader.modules.prevalidation.domain.validators import ImageValidator
from wildintel_uploader.modules.fileinfo.domain.folder import MediaFolder
from wildintel_uploader.modules.fileinfo.domain.models import SERIAL_FIELDS

def camera_groups(folder: MediaFolder, images: list[Path], levels: list[list[str]]) -> tuple[list[str], dict[tuple[str, ...], list[Path]], int]:
    """The images grouped by the camera that took them, as ``levels`` tell a camera.

    The images are compared by the first level every image has all the fields of; when there is none, by the first
    that some have, and the images that lack it are without camera information. A serial number (SerialNumber and the
    like) is the one the file cache read with the camera; any other field is read as a tag.

    Args:
        folder: The folder the images are in.
        images: The images to group.
        levels: The fields of each level, the surest first — VALIDATION.camera_levels; by default
            ``[["SerialNumber"], ["Make", "Model"], ["Model"]]``.

    Returns:
        ``(by, groups, without)``: the fields of the level compared by (empty when no image has any level), the
        images of each camera by the values of those fields, and how many images have no value for them.

    Example:
        Three images of a Browning BTC-8A, one of them with no serial number: SerialNumber is not in every image, but
        Make and Model are::

            (["Make", "Model"],
             {("Browning", "BTC-8A"): [Path(".../IMG_0001.JPG"), Path(".../IMG_0002.JPG"), Path(".../IMG_0003.JPG")]},
             0)
    """
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
        """The distinct cameras among the images, the one that took most first.

        Args:
            folder: The folder whose images are checked.
            options: What the caller says of the checks; only ``camera_levels`` is read here: how a camera is told (see
                ``camera_groups``).

        Returns:
            ``{"cameras": [...], "camera_by": [...], "cameras_without_info": int}``:

            - ``cameras``: one dict for each camera, by how many images it took (most first), then by its values —
              ``{"model", "camera_id", "values", "count", "examples"}``: the model and the serial number the first of its
              images says, the value of each field it is told by, how many images it took and up to three of them,
              relative to the folder. More than one means images of different cameras got mixed.
            - ``camera_by``: the fields the cameras are told by; empty when no image says any.
            - ``cameras_without_info``: how many images do not say them, and are in no camera.

        Example:
            Two cameras mixed in one folder, told by their serial number::

                {
                    "cameras": [
                        {"model": "Browning BTC-8A", "camera_id": "BR5071", "values": {"SerialNumber": "BR5071"},
                         "count": 1203, "examples": ["IMG_0001.JPG", "IMG_0002.JPG", "IMG_0003.JPG"]},
                        {"model": "Browning BTC-8A", "camera_id": "BR9999", "values": {"SerialNumber": "BR9999"},
                         "count": 12, "examples": ["IMG_1204.JPG", "IMG_1205.JPG", "IMG_1206.JPG"]},
                    ],
                    "camera_by": ["SerialNumber"],
                    "cameras_without_info": 0,
                }
        """
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
