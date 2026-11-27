"""The photos of a deployment kept in the collections folder, to look at them: the list, and each one as a JPEG that fits. The rules are the
domain's (domain.photos); the folder is what it is given."""
from __future__ import annotations

from wildintel_uploader.modules.deployments.domain import photos as rules
from wildintel_uploader.modules.deployments.domain.ports import Photos, PhotoFolder


class DeploymentPhotos(Photos):
    def __init__(self, folder: PhotoFolder) -> None:
        self._folder = folder

    def list(self, project: str, collection: str, deployment_id: str) -> list[dict]:
        rules.check_parts(collection, deployment_id)
        names = [n for n in self._folder.names(project, collection, deployment_id) if rules.is_photo(n)]
        return rules.in_order(names, self._folder.taken(project, collection, deployment_id))

    def jpeg(self, project: str, collection: str, deployment_id: str, name: str, large: bool) -> bytes:
        """Only the photos of the deployment's own folder are shown."""
        rules.check_parts(collection, deployment_id)
        if not rules.is_photo(name):
            raise rules.no_photo(name)
        return self._folder.jpeg(project, collection, deployment_id, name, rules.size(large))
