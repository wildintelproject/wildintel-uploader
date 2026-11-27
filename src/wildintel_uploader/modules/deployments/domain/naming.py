"""How the deployments are named — wildintel-tools' own rules —, in plain Python: a deployment is R + its revision as four digits, a hyphen and its
location ("R0003-DONA_01"); its collection is the R0003 its id starts with; its images are walked in natural file-name order ("IMG_2" before
"IMG_10")."""
from __future__ import annotations

import re
from pathlib import Path

from wildintel_uploader.modules.deployments.domain.models import BadDeploymentName

_COLLECTION_PREFIX = re.compile(r"^(R\d{4})-")


def deployment_id_for(revision: int, location_id: str) -> str:
    """BadDeploymentName: the revision isn't 1..9999 or the location is empty."""
    if not 1 <= revision <= 9999 or not location_id.strip():
        raise BadDeploymentName("A deployment id needs a revision from 1 to 9999 and a location id.")
    return f"R{revision:04d}-{location_id.strip()}"


def collection_code(deployment_id: str) -> str:
    """The collection a deployment belongs to — its id's "R0003" prefix. BadDeploymentName: the id doesn't start with R + four digits + a hyphen."""
    match = _COLLECTION_PREFIX.match(deployment_id)
    if not match:
        raise BadDeploymentName(
            f"The deployment id '{deployment_id}' must start with its collection, R + four digits + a hyphen (e.g. R0003-DONA_01)."
        )
    return match.group(1)


def natural_key(path: Path | str) -> list:
    """Sorts "IMG_2" before "IMG_10" — the order wildintel-tools walks a deployment's images in."""
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", str(path))]
