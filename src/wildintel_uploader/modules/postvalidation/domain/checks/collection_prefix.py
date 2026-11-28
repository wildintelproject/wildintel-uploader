"""The R0033 prefix of the deployment id is the collection it goes in."""
from __future__ import annotations

from wildintel_uploader.modules.postvalidation.domain.validators import DeploymentValidator
from wildintel_uploader.modules.fileinfo.domain.folder import MediaFolder
from wildintel_uploader.modules.postvalidation.domain.models import COLLECTION_NAME_RE, DeploymentContext, collection_of, collection_for, ok, problem

class CollectionPrefix(DeploymentValidator):
    key = "collection_prefix"
    label = "Collection prefix"
    description = "The R0033 prefix of the id is the collection it goes in."

    def run(self, folder: MediaFolder, context: DeploymentContext) -> dict:
        """Whether the deployment id starts with the collection it goes in: R0033-DONA_01 goes in R0033 or R0033_suffix.

        The prefix and the collection are compared whatever their case.

        Args:
            folder: Not read: the check is of names.
            context: ``deployment.deployment_id`` and ``collection``, the collection chosen; with none, the one the id
                names — which always matches.

        Returns:
            ``{"collection_prefix": {"ok": bool, "message": str}}`` — a problem when the id does not start with a
            collection, when the collection is not a valid name, or when they are not the same.

        Example:
            R0012-DONA_01 in the collection R0013::

                {"collection_prefix": {"ok": False,
                                       "message": "The deployment id starts with R0012, but it goes in the collection R0013."}}
        """
        deployment_id, collection = context.deployment.deployment_id, collection_for(context)
        prefix = collection_of(deployment_id)
        code = collection[:5] if collection is not None and COLLECTION_NAME_RE.match(collection) else None
        if prefix is None:
            found = problem(f"'{deployment_id}' doesn't start with a collection (R0033-…).")
        elif code is None:
            found = problem("There is no valid collection to compare the deployment id's prefix with.")
        elif prefix.lower() != code.lower():
            found = problem(f"The deployment id starts with {prefix}, but it goes in the collection {code}.")
        else:
            found = ok(f"The deployment id starts with its collection, {code}.")
        return {"collection_prefix": found}
