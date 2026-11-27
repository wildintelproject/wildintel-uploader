"""The hash of each image as it ends up, metadata included — what sha1sum gives; the XMP can't hold its own hash."""
from __future__ import annotations

from collections.abc import Iterator

from wildintel_uploader.modules.preprocessing.domain.models import ImageWork
from wildintel_uploader.modules.preprocessing.domain.steps import FolderStep, Job
from wildintel_uploader.modules.preprocessing.infrastructure.images import sha1


class FinalHashes(FolderStep):
    key = "final_hash"
    label = "Final hashes"

    def run(self, works: list[ImageWork], job: Job) -> Iterator[dict]:
        for w in works:
            w.record["final_hash"] = sha1(w.record["_target"])
        yield from ()
