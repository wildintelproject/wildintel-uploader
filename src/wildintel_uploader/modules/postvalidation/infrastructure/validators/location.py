"""The location of the deployment id is the one chosen."""
from __future__ import annotations

from wildintel_uploader.modules.postvalidation.domain.validators import DeploymentValidator
from wildintel_uploader.modules.fileinfo.domain.folder import MediaFolder
from wildintel_uploader.modules.postvalidation.domain.models import DeploymentContext, ok, problem

class LocationOfTheId(DeploymentValidator):
    key = "location"
    label = "Location"
    description = "The location of the id — after the first hyphen, without an optional _suffix — is the one chosen."

    def run(self, folder: MediaFolder, context: DeploymentContext) -> dict:
        deployment_id, expected = context.deployment.deployment_id, context.expected_location_id
        tail = deployment_id.split("-", 1)[1] if "-" in deployment_id else ""
        if not expected:
            found = ok("No location was chosen to compare with.")
        elif tail.lower() == expected.lower() or tail.lower().startswith(expected.lower() + "_"):
            found = ok(f"The deployment id's location is {expected}, the one chosen.")
        else:
            found = problem(f"The deployment id's location is '{tail}', but the location chosen is {expected}.")
        return {"location": found}
