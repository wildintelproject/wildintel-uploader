"""The web API of the prevalidation as JSON — what the requests send, for entrypoints/api/prevalidation.py."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

ImageCheck = Literal["corrupted", "sequence", "structure", "camera", "exif", "duplicates"]


class ValidateImagesRequest(BaseModel):
    path: str
    # None runs every check.
    checks: Optional[list[ImageCheck]] = None
    # The research project the images are for: the duplicates check also looks for images imported before into it. None: only the folder itself.
    research_project_id: Optional[str] = None
    # The deployment being imported, when it is known: what was kept of it is not a duplicate (it is imported again).
    deployment_id: Optional[str] = None
