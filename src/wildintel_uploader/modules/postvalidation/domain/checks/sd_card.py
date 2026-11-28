"""The SD card of the images is the one the visit left in the camera."""
from __future__ import annotations

from wildintel_uploader.modules.postvalidation.domain.validators import DeploymentValidator
from wildintel_uploader.modules.fileinfo.domain.folder import MediaFolder
from wildintel_uploader.modules.postvalidation.domain.models import DeploymentContext, ok, problem

class SdCardOfTheVisit(DeploymentValidator):
    key = "sd_card"
    label = "SD card"
    description = "The card the images are said to come from is the one the visit left in the camera."
    of_the_visit = True

    def run(self, folder: MediaFolder, context: DeploymentContext) -> dict:
        visit = context.visit
        if not visit:
            return {"sd_card": ok("No visit was chosen, so the card cannot be checked.")}
        said, left, session = (visit.get("sd_card") or "").strip(), (visit.get("left_sd") or "").strip(), visit.get("left_session") or "the visit"
        if not said:
            found = ok("No SD card was said for these images, so the card cannot be checked.")
        elif not left:
            found = ok(f"The visit {session} does not say which card it left, so the card cannot be checked.")
        elif said.lower() == left.lower():
            found = ok(f"The SD card is {said}, the one the visit {session} left in the camera.")
        else:
            found = problem(f"You said the images come from the card {said}, but the visit {session} left {left} in the camera.")
        return {"sd_card": found}
