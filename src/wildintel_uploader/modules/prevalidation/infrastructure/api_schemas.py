"""The web API of the prevalidation as JSON — what the requests send, for entrypoints/api/prevalidation.py."""
from __future__ import annotations

from typing import Any
from pydantic import Field

from wildintel_uploader.shared.answers import Answer

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


# ── what the routes answer (#248) ──


class ValidateImagesAnswer(Answer):
    """What POST /api/deployment-import/validate-images answers."""
    checked_count: int | None = None
    corrupted: list[Any] | None = None
    sequence_issues: list[Any] | None = None
    subdirectories: list[Any] | None = None
    exiftool: bool | None = None
    cameras: list[Any] | None = None
    camera_by: list[Any] | None = None
    cameras_without_info: int | None = None
    exif_missing: dict[str, Any] | None = None
    duplicates: list[Any] | None = None
    report_id: str | None = None
    duplicates_in_project: list[Any] | None = None
