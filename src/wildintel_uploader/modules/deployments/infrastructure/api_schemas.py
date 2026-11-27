"""The web API of the deployments as JSON — what the requests send, for entrypoints/api/deployments.py and desktop.py, with their fields and checks
as they were."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from wildintel_uploader.shared.camtrap import DeploymentFields


class ScanFolderRequest(BaseModel):
    path: str


class CardRequest(BaseModel):
    """A memory card — or the copy of one — by the path of its folder."""

    path: str = Field(min_length=1)


class BrowseFolderRequest(BaseModel):
    # None uses the picker's own default title.
    title: Optional[str] = None


class ExistingDeploymentsRequest(BaseModel):
    research_project_id: str = Field(min_length=1)
    deployment_ids: list[str] = Field(min_length=1, max_length=1000)


class PreviousDeploymentsRequest(BaseModel):
    research_project_id: str = Field(min_length=1)
    deployment_ids: list[str] = Field(min_length=1, max_length=1000)


class NextRevisionRequest(BaseModel):
    research_project_id: str = Field(min_length=1)
    location_id: str = Field(min_length=1)


class CheckCollectionRequest(BaseModel):
    path: str


class CollectionPathRequest(BaseModel):
    """Where a deployment's collection is kept locally by default."""

    research_project_id: str = Field(min_length=1)
    deployment_id: str = Field(min_length=1)


class PreprocessingRequest(BaseModel):
    """What to do to the images as they are imported (see services.preprocessing_service)."""

    rename: bool = True
    resize: bool = True
    resize_width: int = Field(default=2400, ge=100, le=20000)
    metadata: bool = True
    owner: str = ""
    publisher: str = ""
    coverage: str = ""
    license_url: str = "https://creativecommons.org/licenses/by-nc/4.0/"
    # The research project's name, for the creator metadata.
    research_project: str = ""
    # The timezone and summer-time setting the dates are read in are the location's, kept with it: not asked here.
    convert_to_utc: bool = True


class ImportLocalRequest(BaseModel):
    """Organizes a deployment into a local collection folder — no Trapper
    account involved (see services.local_folder_service)."""

    source_dir: str = Field(min_length=1)
    collection_dir: str = Field(min_length=1)
    # Recorded in the collection's own metadata — None when reusing an
    # existing collection that already has one.
    collection_name: Optional[str] = None
    deployment: DeploymentFields
    # None copies the images as they are; given, they are preprocessed as it says.
    preprocessing: Optional[PreprocessingRequest] = None


class OpenFolderRequest(BaseModel):
    path: str


class UploadCollectionsRequest(BaseModel):
    """The collections kept for a research project."""

    research_project_id: str = Field(min_length=1)


class StatisticsRequest(BaseModel):
    """A revision (collection) kept in the collections folder, to compare its deployments with the previous revisions of their locations."""

    research_project_id: str = Field(min_length=1)
    collection: str = Field(pattern=r"^R\d{4}(_.+)?$")


class RepairRequest(BaseModel):
    """One deployment kept in the collections folder, to look at or to repair."""

    research_project_id: str = Field(min_length=1)
    collection: str = Field(pattern=r"^R\d{4}(_.+)?$")
    deployment_id: str = Field(pattern=r"^R\d{4}-.+$")
