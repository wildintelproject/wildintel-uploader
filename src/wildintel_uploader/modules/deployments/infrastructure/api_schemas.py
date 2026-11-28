"""The web API of the deployments as JSON — what the requests send, for entrypoints/api/deployments.py and desktop.py, with their fields and checks
as they were."""
from __future__ import annotations

from typing import Any

from wildintel_uploader.shared.answers import Answer

from typing import Literal, Optional

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
    """What to do to the images as they are imported (see modules.preprocessing)."""

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
    account involved (see application.imports)."""

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


# ── the sessions of the wizard ──

class SelectedResearchProject(BaseModel):
    pk: int
    name: str
    acronym: Optional[str] = None


class SelectedClassificationProject(BaseModel):
    pk: int
    name: str


class SelectedLocation(BaseModel):
    pk: int
    location_id: str
    name: Optional[str] = None
    timezone: Optional[str] = None


class DeploymentSelection(BaseModel):
    """How the deployment is identified for this run — kept in its session
    so the resume screen can show it without reconnecting to Trapper.
    Two independent choices:

    destination — "trapper": registered in (or found in) a Trapper
    instance. "local": organized into a local collection folder instead,
    with no Trapper account involved at all.

    mode — "existing": the deployment already exists (in Trapper, or
    already organized in the chosen local collection) and was found rather
    than filled in — its own fields (including location) come from there
    (see SaveDetailsRequest), so classification_project/location aren't
    collected here. "new": it's being created for the first time, so they
    are.

    research_project/classification_project/location only apply to
    destination "trapper"; collection_dir/collection_name only to "local"."""

    destination: Literal["trapper", "local"]
    mode: Literal["new", "existing"]
    research_project: Optional[SelectedResearchProject] = None
    classification_project: Optional[SelectedClassificationProject] = None
    location: Optional[SelectedLocation] = None
    collection_dir: Optional[str] = None
    collection_name: Optional[str] = None


class SaveSelectionRequest(BaseModel):
    task_id: str
    selection: DeploymentSelection


class ScanResultFields(BaseModel):
    file_count: int
    image_count: int
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    camera_model: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)


class SaveScanRequest(BaseModel):
    # None starts a new session — the wizard's first step.
    task_id: Optional[str] = None
    source_dir: str = Field(min_length=1)
    scan: ScanResultFields


class SaveDetailsRequest(BaseModel):
    task_id: str
    deployment: DeploymentFields


# ── what the routes answer (#248) ──


class DiscardAnswer(Answer):
    """What DELETE /api/sessions/{task_id} answers."""
    status: str | None = None


class LogEntryAnswer(Answer):
    """What GET /api/deployment-import/log-entry answers."""
    collection: str | None = None
    timestamps: dict[str, Any] | None = None
    fieldwork: dict[str, Any] | None = None


class DeploymentPhotosListAnswer(Answer):
    """What GET /api/deployment-import/photos answers."""
    photos: list[Any] | None = None


class ListSessionsItem(Answer):
    """One of what GET /api/sessions answers."""
    task_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    phase: str | None = None
    task: str | None = None
    source_dir: str | None = None
    scan: dict[str, Any] | None = None
    selection: dict[str, Any] | None = None
    deployment: dict[str, Any] | None = None


class CheckCollectionAnswer(Answer):
    """What POST /api/deployment-import/check-collection answers."""
    exists: bool | None = None
    name: Any = None


class CollectionPathAnswer(Answer):
    """What POST /api/deployment-import/collection-path answers."""
    path: str | None = None
    collection: str | None = None
    exists: bool | None = None
    name: Any = None


class DiscardCardCopyAnswer(Answer):
    """What POST /api/deployment-import/discard-card-copy answers."""
    removed: bool | None = None


class EjectCardAnswer(Answer):
    """What POST /api/deployment-import/eject-card answers."""
    ejected: bool | None = None
    message: str | None = None


class ExistingDeploymentsAnswer(Answer):
    """What POST /api/deployment-import/existing-deployments answers."""
    results: dict[str, Any] | None = None


class GuessDetailsAnswer(Answer):
    """What POST /api/deployment-import/guess-details answers."""
    start_date: str | None = None
    end_date: str | None = None
    camera_model: Any = None
    camera_id: Any = None
    warnings: list[Any] | None = None


class ListLocalDeploymentsAnswer(Answer):
    """What POST /api/deployment-import/list-local-deployments answers."""
    results: list[Any] | None = None


class NextRevisionAnswer(Answer):
    """What POST /api/deployment-import/next-revision answers."""
    last: int | None = None
    next: int | None = None


class PreviousDeploymentsAnswer(Answer):
    """What POST /api/deployment-import/previous-deployments answers."""
    results: dict[str, Any] | None = None


class ScanFolderAnswer(Answer):
    """What POST /api/deployment-import/scan-folder answers."""
    file_count: int | None = None
    image_count: int | None = None
    warnings: list[Any] | None = None


class ScanSessionAnswer(Answer):
    """What POST /api/deployment-import/scan-session answers."""
    deployments: list[Any] | None = None
    loose_files: int | None = None
    warnings: list[Any] | None = None
    timestamp_log: Any = None


class SealStatusAnswer(Answer):
    """What POST /api/deployment-import/seal answers."""
    status: str | None = None
    changed: list[Any] | None = None
    missing: list[Any] | None = None
    added: list[Any] | None = None
    deployment_changed: bool | None = None
    seal_changed: bool | None = None


class RepairCollectionsAnswer(Answer):
    """What POST /api/repair/collections answers."""
    results: list[Any] | None = None


class InspectAnswer(Answer):
    """What POST /api/repair/inspect answers."""
    deployment_id: str | None = None
    status: str | None = None
    seal: dict[str, Any] | None = None
    files: dict[str, Any] | None = None
    images: int | None = None
    log: str | None = None
    problems: list[Any] | None = None


class SaveDetailsAnswer(Answer):
    """What POST /api/sessions/details answers."""
    task_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    phase: str | None = None
    task: str | None = None
    source_dir: str | None = None
    scan: dict[str, Any] | None = None
    selection: dict[str, Any] | None = None
    deployment: dict[str, Any] | None = None


class SaveScanAnswer(Answer):
    """What POST /api/sessions/scan answers."""
    task_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    phase: str | None = None
    task: str | None = None
    source_dir: str | None = None
    scan: dict[str, Any] | None = None
    selection: dict[str, Any] | None = None


class SaveSelectionAnswer(Answer):
    """What POST /api/sessions/selection answers."""
    task_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    phase: str | None = None
    task: str | None = None
    source_dir: str | None = None
    scan: dict[str, Any] | None = None
    selection: dict[str, Any] | None = None


class RevisionAnswer(Answer):
    """What POST /api/statistics/revision answers."""
    results: list[Any] | None = None
