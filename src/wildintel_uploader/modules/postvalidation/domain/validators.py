"""A validator of a deployment, as a class (#246): its key — the name the settings, the reports and the pages use —, its label and what it says,
whether it is of the visit (only in the wizard, where the visit is known: a seal or a repair has none), and what it finds, by the keys the results
have always had (deployment_id, out_of_range, camera_mismatches, sd_card…)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from wildintel_uploader.modules.fileinfo.domain.folder import MediaFolder
from wildintel_uploader.modules.postvalidation.domain.models import DeploymentContext


class DeploymentValidator(ABC):
    key: ClassVar[str]
    label: ClassVar[str]
    description: ClassVar[str]
    of_the_visit: ClassVar[bool] = False
    # compares this revision with the previous ones of the location — against the history the deployments keep
    statistical: ClassVar[bool] = False

    @abstractmethod
    def run(self, folder: MediaFolder, context: DeploymentContext) -> dict:
        """What it found, by the keys of the result."""
