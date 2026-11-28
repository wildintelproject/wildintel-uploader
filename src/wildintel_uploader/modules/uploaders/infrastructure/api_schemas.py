"""The web API of the uploaders as JSON — what the requests send, for entrypoints/api/uploaders.py, with their fields and checks as they were."""
from __future__ import annotations

from typing import Any

from wildintel_uploader.shared.answers import Answer

from typing import Literal, Optional

from pydantic import BaseModel, Field

from wildintel_uploader.shared.camtrap import DeploymentFields


class TrapperCredentials(BaseModel):
    # Any of these left blank falls back to settings.toml (see
    # TrapperClient.credentials).
    url: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None


class ClassificationProjectsRequest(TrapperCredentials):
    research_project_pk: int


class LocationsRequest(TrapperCredentials):
    research_project_pk: int


class DeploymentsRequest(TrapperCredentials):
    research_project_pk: int


class UploadCollectionsRequest(BaseModel):
    """The collections kept for a research project, to choose what to upload from."""

    research_project_id: str = Field(min_length=1)


class UploadDeploymentRequest(TrapperCredentials):
    """Upload one deployment of a collection kept locally to Trapper."""

    research_project_id: str = Field(min_length=1)
    collection: str = Field(pattern=r"^R\d{4}(_.+)?$")
    deployment_id: str = Field(pattern=r"^R\d{4}-.+$")
    # "upload" sends it; "dry_run" says what that would do and changes nothing; "generate" only writes the
    # files (the zips, the yamls and the collection's deployments csv) and leaves them.
    mode: Literal["upload", "dry_run", "generate"] = "upload"
    # The classification project the collection goes to — optional when the research project has only one.
    classification_project_pk: Optional[int] = None
    # With "upload": take the package files away once they are up (the zips, the yamls and the deployment's row of the
    # deployments csv). Left as they are, they stay in the packages folder, as "generate" leaves them.
    delete_files: bool = False


class AccessCheckRequest(TrapperCredentials):
    """Check the account can do what uploading a collection's deployments needs, changing nothing."""

    research_project_id: str = Field(min_length=1)
    collection: Optional[str] = Field(default=None, pattern=r"^R\d{4}(_.+)?$")
    # The deployments whose locations are looked for in Trapper.
    deployment_ids: list[str] = Field(default_factory=list)
    classification_project_pk: Optional[int] = None


class UploadClassificationProjectsRequest(TrapperCredentials):
    """The classification projects of a research project kept locally, as Trapper has them."""

    research_project_id: str = Field(min_length=1)


class ImportDeploymentRequest(TrapperCredentials):
    research_project_pk: int
    # Names the research project's folder in the local collections folder
    # (its acronym, or its pk when it has none).
    research_project_id: str = Field(min_length=1)
    classification_project_pk: Optional[int] = None
    # The folder scanned in the "scan-folder" step — copied into the app's
    # organized data directory before Trapper is told about the deployment.
    source_dir: str = Field(min_length=1)
    deployment: DeploymentFields
    # The timezone and summer-time setting it is registered with are the location's, kept with it: not asked here.
    # "register" collides with abc.ABCMeta.register, which pydantic warns
    # about — hence the longer name.
    register_deployment: bool = True


class SyncCollectionNamesRequest(TrapperCredentials):
    """The collections of a classification project that can be synced, and the deployments in each."""

    research_project_pk: int
    classification_project_pk: int


class SyncCollectionsRequest(TrapperCredentials):
    """Sync the collections folder with the classification project's collections, deployments and locations."""

    research_project_pk: int
    research_project_name: Optional[str] = None
    research_project_acronym: Optional[str] = None
    classification_project_pk: int
    # The collections to sync, by name; left out, every collection starting with R is synced.
    collections: Optional[list[str]] = None
    # The deployments to sync, by id, within those collections; left out, all of them are.
    deployments: Optional[list[str]] = None
    # Also download the images of those deployments from Trapper (through the classification project's media), into their folders.
    download_images: bool = False


class UploadReportRequest(BaseModel):
    collection: str
    research_project_id: str
    started_at: str
    finished_at: str
    items: list[dict]


# ── what the routes answer (#248) ──


class CollectionNamesAnswer(Answer):
    """What POST /api/sync/collection-names answers."""
    results: list[Any] | None = None


class CheckAccessAnswer(Answer):
    """What POST /api/upload/check-access answers."""
    checks: list[Any] | None = None


class CheckSelectionAnswer(Answer):
    """What POST /api/upload/check-selection answers."""
    checks: list[Any] | None = None


class UploadClassificationProjectsAnswer(Answer):
    """What POST /api/upload/classification-projects answers."""
    results: list[Any] | None = None


class CollectionsAnswer(Answer):
    """What POST /api/upload/collections answers."""
    results: list[Any] | None = None


class SaveUploadReportAnswer(Answer):
    """What POST /api/upload/report answers."""
    report_id: str | None = None


class TrapperDefaults(Answer):
    """The account of TRAPPER kept in the settings — the password only said to be there."""
    base_url: str | None = None
    user_name: str | None = None
    has_password: bool | None = None


class TrapperConnection(Answer):
    ok: bool | None = None
    research_projects_count: int | None = None


class TrapperResults(Answer):
    """What TRAPPER lists — its research projects, classification projects, locations or deployments —, each as TRAPPER says it."""
    results: list[dict[str, Any]] | None = None
