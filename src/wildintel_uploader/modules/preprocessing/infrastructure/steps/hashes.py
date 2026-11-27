"""The hashes of an image (SHA-1): of the original — what is known of the files remembers it: the prevalidation asked it already to find the
images imported before — and of the image kept, before its metadata."""
from __future__ import annotations

from wildintel_uploader.modules.preprocessing.domain.models import ImageWork
from wildintel_uploader.modules.preprocessing.domain.steps import ImageStep, Job
from wildintel_uploader.modules.preprocessing.infrastructure.images import sha1


class Hashes(ImageStep):
    key = "hashes"
    label = "Hashes"

    def run(self, work: ImageWork, job: Job) -> None:
        source_hash = job.info.hash(work.source, "sha1")
        if source_hash is None:
            raise OSError(f"Could not read {work.source}")
        work.record.update({"source_hash": source_hash, "hash": sha1(work.record["_target"])})
