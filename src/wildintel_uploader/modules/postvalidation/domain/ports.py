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
