"""The folder has the photos the visit counted on the card."""
from __future__ import annotations

from wildintel_uploader.modules.postvalidation.domain.validators import DeploymentValidator
from wildintel_uploader.modules.fileinfo.domain.folder import MediaFolder
from wildintel_uploader.modules.postvalidation.domain.models import DeploymentContext, ok, problem

class PhotoCount(DeploymentValidator):
    key = "photo_count"
    label = "Number of photos"
    description = "The folder has the photos the visit counted on the card when it collected it."
    of_the_visit = True

    def run(self, folder: MediaFolder, context: DeploymentContext) -> dict:
        visit, found = context.visit, len(folder.images)
        if not visit:
            return {"photo_count": ok("No visit was chosen, so the number of images cannot be checked.")}
        counted, session = visit.get("counted_photos"), visit.get("collected_session") or "the visit"
        if counted is None:
            return {"photo_count": ok(f"The visit {session} did not count the images on the card, so the number of images cannot be checked.")}
        photos = lambda n: f"{n:,} {'image' if n == 1 else 'images'}"  # noqa: E731
        if counted == found:
            return {"photo_count": ok(f"The folder has {photos(found)}, as the visit {session} counted.")}
        gap = abs(counted - found)
        return {"photo_count": problem(f"The visit {session} counted {photos(counted)} on the card, and the folder has {photos(found)} — "
                                       f"{photos(gap)} {'missing' if found < counted else 'more'}.")}
