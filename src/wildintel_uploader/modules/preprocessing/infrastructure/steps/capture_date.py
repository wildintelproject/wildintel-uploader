"""The date of an image: its capture date from its EXIF (the first of DateTimeOriginal, CreateDate, ModifyDate, #227) — or the modification time of
the file when it has none —, as the camera's wall clock in the timezone of the deployment, optionally ignoring summer time, and in UTC if asked."""
from __future__ import annotations

from datetime import datetime

from wildintel_uploader.modules.preprocessing.domain.models import ImageWork, as_kept, localize, zone_of
from wildintel_uploader.modules.preprocessing.domain.steps import ImageStep, Job


def camera_time(work: ImageWork, job: Job) -> tuple[datetime, datetime, str]:
    """The capture time as the camera's wall clock, the same in its timezone, and where it came from: "exif", or "file"."""
    naive, source = job.date_of(work), "exif"
    if naive is None:
        naive, source = datetime.fromtimestamp(work.source.stat().st_mtime).replace(microsecond=0), "file"
    return naive, localize(naive, zone_of(job.options.timezone), ignore_dst=job.options.ignore_dst), source


class CaptureDate(ImageStep):
    key = "date"
    label = "Date"

    def run(self, work: ImageWork, job: Job) -> None:
        naive, aware, source = camera_time(work, job)
        date = as_kept(aware, job.options)
        work.record.update({"original": str(work.relative), "date": date.isoformat(), "date_source": source, "_date": date, "_local": naive})
