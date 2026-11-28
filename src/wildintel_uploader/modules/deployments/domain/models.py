"""What the deployments refuse: what can't be done (failed), and what is not there (missing)."""
from __future__ import annotations


class DeploymentsError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class DeploymentsFailed(DeploymentsError):
    """A folder that isn't one, a collection that can't be read, a deployment that is of no visit…"""


class DeploymentMissing(DeploymentsError):
    """A deployment, or a photo of it, that is not kept."""


class PickerUnavailable(DeploymentsError):
    """The computer has no folder picker to open."""


class BadDeploymentName(DeploymentsFailed, ValueError):
    """A deployment id, or a revision, that doesn't follow wildintel-tools' rules."""


class DeploymentImportError(DeploymentsFailed, ValueError):
    """A problem with the source/destination paths — reported to the user, not a bug. One of what the deployments refuse (their domain's
    DeploymentsFailed), so that the other modules tell it by that."""
