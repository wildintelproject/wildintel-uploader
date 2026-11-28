"""The deployment id follows wildintel-tools' rule: R0033-DONA_01."""
from __future__ import annotations

from wildintel_uploader.modules.postvalidation.domain.validators import DeploymentValidator
from wildintel_uploader.modules.fileinfo.domain.folder import MediaFolder
from wildintel_uploader.modules.postvalidation.domain.models import DEPLOYMENT_ID_RE, DeploymentContext, ok, problem

class DeploymentId(DeploymentValidator):
    key = "deployment_id"
    label = "Deployment id"
    description = "The id looks like R0033-DONA_01: R, four digits, a hyphen, the location id and an optional _suffix."

    def run(self, folder: MediaFolder, context: DeploymentContext) -> dict:
        """Whether the deployment id looks like R0033-DONA_01: R, four digits, a hyphen, the location id and an optional
        ``_suffix``.

        Args:
            folder: Not read: the check is of a name.
            context: ``deployment.deployment_id``.

        Returns:
            ``{"deployment_id": {"ok": bool, "message": str}}`` — whether the id is valid, and what the page says.

        Example::

            {"deployment_id": {"ok": False, "message": "'R33-DONA_01' must look like R0033-DONA_01: R, four digits, a "
                                                       "hyphen, the location id and an optional _suffix."}}
        """
        deployment_id = context.deployment.deployment_id
        return {"deployment_id": ok(f"'{deployment_id}' is a valid deployment id.") if DEPLOYMENT_ID_RE.match(deployment_id)
                else problem(f"'{deployment_id}' must look like R0033-DONA_01: R, four digits, a hyphen, the location id and an optional _suffix.")}
