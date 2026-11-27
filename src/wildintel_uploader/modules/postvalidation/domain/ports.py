"""The contract of the postvalidation, and what its use cases are given: what is known of the files (the contract of modules.fileinfo)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from pathlib import Path

from wildintel_uploader.modules.postvalidation.domain.models import DeploymentContext
from wildintel_uploader.modules.postvalidation.domain.validators import DeploymentValidator

# on_check(check, state): a check starts ("running") or ends ("done").
OnCheck = Callable[[str, str], None]


class PostvalidationService(ABC):

    @abstractmethod
    def validators(self, keys: frozenset[str] | None = None) -> list[DeploymentValidator]:
        """The validators of a deployment, in the order they run — those of these keys, or all."""

    @abstractmethod
    def validate(self, folder: Path, context: DeploymentContext, validators: Sequence[DeploymentValidator] | None = None, *,
                 on_check: OnCheck | None = None) -> dict:
        """Runs these validators of the deployment over the images of `folder`, in the order given (None: all, in theirs): {"checked_count", and
        what each found}.
        PostvalidationError: the folder isn't one, or the tolerance is negative."""

    @abstractmethod
    def check_deployment(self, folder: Path, context: DeploymentContext, checks: frozenset[str] | None = None, *, on_check: OnCheck | None = None) -> dict:
        """The checks of a deployment as an import asks for them — those of these keys (None: all, the statistical ones last), against the record of
        its camera in the catalog and as the settings say a camera is told —, and the id of their report ("report_id")."""


# ── out ──

class CameraRecords(ABC):
    @abstractmethod
    def camera(self, research_project_id: str | None, camera_id: str | None) -> dict | None:
        """The record of a camera of the catalog — its serial number, make, model and label — or None."""


class CameraLevels(ABC):
    @abstractmethod
    def levels(self) -> list[list[str]]:
        """How two images are told to be of the same camera, as the settings say (VALIDATION.camera_levels)."""


class PostvalidationReports(ABC):
    @abstractmethod
    def postvalidation(self, result: dict, deployment_id: str, folder: Path, parameters: dict) -> str | None:
        """Keeps the report of a postvalidation; its id, or None when it could not be written."""
