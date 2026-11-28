"""The order of the shots: a higher-numbered file is not dated before a lower-numbered one of its folder."""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from wildintel_uploader.modules.prevalidation.domain.models import ImageOptions
from wildintel_uploader.modules.prevalidation.domain.validators import ImageValidator
from wildintel_uploader.modules.fileinfo.domain.folder import MediaFolder

_TRAILING_DIGITS_RE = re.compile(r"(\d+)(?!.*\d)")  # a filename's last run of digits — how camera traps number shots


def sequence_number(path: Path) -> int | None:
    """The number a camera gave a shot: the last run of digits of its file name, without the extension.

    Args:
        path: The image.

    Returns:
        That number, or None when the name has no digit.

    Examples:
        >>> sequence_number(Path("DCIM/100RECNX/IMG_0042.JPG"))
        42
        >>> sequence_number(Path("RCNX0007_2.JPG"))
        2
        >>> sequence_number(Path("photo.jpg")) is None
        True
    """
    match = _TRAILING_DIGITS_RE.search(path.stem)
    return int(match.group(1)) if match else None


class ShootingOrder(ImageValidator):
    key = "sequence"
    label = "Order of the shots"
    description = ("Camera traps number shots in the order they were taken, so within one folder a higher-numbered file shouldn't have an earlier "
                   "date than a lower-numbered one — a camera clock reset, a misnamed file, or images of two cards mixed. Undated, unnumbered and "
                   "corrupted images are skipped, and each folder is checked on its own.")

    def run(self, folder: MediaFolder, options: ImageOptions) -> dict:
        """The pairs of shots of a folder whose dates go back.

        Within each folder (a subfolder on its own), the images that have a date and a number are put in order by their
        number, and each is compared with the next: one dated before the one numbered before it is an issue; two with the
        same number are not compared. The images with no date or no number are skipped, and so are the corrupted ones —
        when the check of the corrupted images ran before.

        Args:
            folder: The folder whose images are checked.
            options: Not read: the check has no option.

        Returns:
            ``{"sequence_issues": [...]}`` — one dict for each pair: ``{"path_a", "index_a", "date_a", "path_b",
            "index_b", "date_b"}``, the lower-numbered image (a) and the next one (b), each with its path relative to the
            folder, its number and its date (ISO 8601). Empty when every folder is in order.

        Example:
            The camera clock went back an hour between the shots 41 and 42::

                {"sequence_issues": [{"path_a": "IMG_0041.JPG", "index_a": 41, "date_a": "2026-10-19T14:05:12",
                                      "path_b": "IMG_0042.JPG", "index_b": 42, "date_b": "2026-10-19T13:05:40"}]}
        """
        taken, errors = folder.dates(), folder.decode_errors_if_known()
        dated: dict[Path, datetime] = {}
        by_dir: dict[Path, list[Path]] = defaultdict(list)
        for path in folder.images:
            if errors.get(path) is not None:
                continue
            by_dir[path.parent].append(path)
            if taken[path] is not None:
                dated[path] = taken[path]  # type: ignore[assignment]
        issues: list[dict] = []
        for group in by_dir.values():
            numbered = [(path, n) for path in group if path in dated and (n := sequence_number(path)) is not None]
            numbered.sort(key=lambda pair: pair[1])
            for (path_a, num_a), (path_b, num_b) in zip(numbered, numbered[1:]):
                if num_a != num_b and dated[path_b] < dated[path_a]:
                    issues.append({
                        "path_a": folder.relative(path_a), "index_a": num_a, "date_a": dated[path_a].isoformat(),
                        "path_b": folder.relative(path_b), "index_b": num_b, "date_b": dated[path_b].isoformat(),
                    })
        return {"sequence_issues": issues}
