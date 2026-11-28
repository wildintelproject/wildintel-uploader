"""The name an image is kept with: <DEPLOYMENT>__<YYYYMMDD>_<n>.<EXT>, upper case, .jpg as .jpeg — n its place in natural file-name order —; or
the one it had, when renaming is not asked for."""
from __future__ import annotations

from wildintel_uploader.modules.preprocessing.domain.models import ImageWork, new_name
from wildintel_uploader.modules.preprocessing.domain.steps import ImageStep, Job


class Rename(ImageStep):
    key = "rename"
    label = "Name"

    def run(self, work: ImageWork, job: Job) -> None:
        name = new_name(job.deployment.deployment_id, work.record["_date"], work.index, work.source.suffix) if job.options.rename else str(work.relative)
        target = work.work_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        work.record.update({"name": name, "_target": target})
