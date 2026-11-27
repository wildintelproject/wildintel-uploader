"""The camera of an image, as its metadata say it: its make and model, and its serial number."""
from __future__ import annotations

from wildintel_uploader.modules.preprocessing.domain.models import ImageWork
from wildintel_uploader.modules.preprocessing.domain.steps import ImageStep, Job


class CameraOfTheImage(ImageStep):
    key = "camera"
    label = "Camera"

    def run(self, work: ImageWork, job: Job) -> None:
        camera = job.camera_of(work)
        work.record.update({"camera": camera.model, "camera_id": camera.camera_id})
