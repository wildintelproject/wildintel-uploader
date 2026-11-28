"""The collection is named R0033, optionally with a _suffix."""
from __future__ import annotations

from wildintel_uploader.modules.postvalidation.domain.validators import DeploymentValidator
from wildintel_uploader.modules.fileinfo.domain.folder import MediaFolder
from wildintel_uploader.modules.postvalidation.domain.models import COLLECTION_NAME_RE, DeploymentContext, collection_for, ok, problem

class CollectionName(DeploymentValidator):
    key = "collection_name"
    label = "Collection name"
    description = "The collection is named R0033, optionally with a _suffix."

    def run(self, folder: MediaFolder, context: DeploymentContext) -> dict:
        """Whether the collection the deployment goes in is named like R0033: R and four digits, optionally ``_suffix``.

        Args:
            folder: Not read: the check is of a name.
            context: ``collection``, the collection chosen; with none, the one the deployment id names (``R0033-…``).

        Returns:
            ``{"collection_name": {"ok": bool, "message": str}}`` — whether the name is valid, and what the page says.

        Example::

            {"collection_name": {"ok": False,
                                 "message": "The collection 'Rev33' must be named like R0033 (R and four digits, optionally _suffix)."}}
        """
        collection = collection_for(context)
        if collection is None:
            found = problem("There is no collection: the deployment id doesn't start with one (R0033-…).")
        elif COLLECTION_NAME_RE.match(collection):
            found = ok(f"'{collection}' is a valid collection name.")
        else:
            found = problem(f"The collection '{collection}' must be named like R0033 (R and four digits, optionally _suffix).")
        return {"collection_name": found}
