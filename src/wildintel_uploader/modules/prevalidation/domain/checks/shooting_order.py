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
    match = _TRAILING_DIGITS_RE.search(path.stem)
    return int(match.group(1)) if match else None


class ShootingOrder(ImageValidator):
    key = "sequence"
    label = "Order of the shots"
    description = ("Camera traps number shots in the order they were taken, so within one folder a higher-numbered file shouldn't have an earlier "
                   "date than a lower-numbered one — a camera clock reset, a misnamed file, or images of two cards mixed. Undated, unnumbered and "
                   "corrupted images are skipped, and each folder is checked on its own.")

    def run(self, folder: MediaFolder, options: ImageOptions) -> dict:
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
