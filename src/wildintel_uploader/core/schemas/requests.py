"""Request/response models for the web API."""
from __future__ import annotations

from datetime import date as date_type, time as time_type
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from wildintel_uploader.core.services.visit_time import is_utc
from wildintel_uploader.modules.visits.infrastructure.records import VisitRecord  # noqa: F401 — the record of a visit is the module of the visits'


class TrapperCredentials(BaseModel):
    # Any of these left blank falls back to settings.toml (see
    # services.trapper_service.resolve_credentials).
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


class StatisticsRequest(BaseModel):
    """A revision (collection) kept in the collections folder, to compare its deployments with the previous revisions of their locations."""

    research_project_id: str = Field(min_length=1)
    collection: str = Field(pattern=r"^R\d{4}(_.+)?$")


class RepairRequest(BaseModel):
    """One deployment kept in the collections folder, to look at or to repair."""

    research_project_id: str = Field(min_length=1)
    collection: str = Field(pattern=r"^R\d{4}(_.+)?$")
    deployment_id: str = Field(pattern=r"^R\d{4}-.+$")


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


class ScanFolderRequest(BaseModel):
    path: str


class CardRequest(BaseModel):
    """A memory card — or the copy of one — by the path of its folder."""

    path: str = Field(min_length=1)


class BrowseFolderRequest(BaseModel):
    # None uses the picker's own default title.
    title: Optional[str] = None


# The checks validate-images/validate-deployment can run — see
# services.deployment_import_service's own IMAGE_CHECKS/DEPLOYMENT_CHECKS.
ImageCheck = Literal["corrupted", "sequence", "structure", "camera", "exif", "duplicates"]
DeploymentCheck = Literal[
    "deployment_id", "collection_prefix", "collection_name", "location", "time_range", "camera",
    "image_count", "sequence_count", "sequence_length", "sd_card", "photo_count",
]


class ValidateImagesRequest(BaseModel):
    path: str
    # None runs every check.
    checks: Optional[list[ImageCheck]] = None
    # The research project the images are for: the duplicates check also looks for images imported before into it. None: only the folder itself.
    research_project_id: Optional[str] = None
    # The deployment being imported, when it is known: what was kept of it is not a duplicate (it is imported again).
    deployment_id: Optional[str] = None


from wildintel_uploader.shared.camtrap import DeploymentFields, FeatureType  # noqa: E402,F401 — Camtrap DP is the shared kernel's


class ExistingDeploymentsRequest(BaseModel):
    research_project_id: str = Field(min_length=1)
    deployment_ids: list[str] = Field(min_length=1, max_length=1000)


class PreviousDeploymentsRequest(BaseModel):
    research_project_id: str = Field(min_length=1)
    deployment_ids: list[str] = Field(min_length=1, max_length=1000)


class NextRevisionRequest(BaseModel):
    research_project_id: str = Field(min_length=1)
    location_id: str = Field(min_length=1)


class StatisticsParams(BaseModel):
    """What the statistical checks mean by a sequence and by similar (see services.statistics_service)."""

    # A sequence starts when the gap to the previous image is at least this many seconds.
    sequence_gap_seconds: float = Field(default=60.0, gt=0, le=86400)
    # How many previous revisions of the location are needed to judge at all.
    min_revisions: int = Field(default=2, ge=1, le=50)
    method: Literal["median", "mean", "last", "range"] = "median"
    # What is similar, in percent, for each statistic.
    image_count_tolerance: float = Field(default=50.0, ge=0, le=1000)
    sequence_count_tolerance: float = Field(default=50.0, ge=0, le=1000)
    sequence_length_tolerance: float = Field(default=50.0, ge=0, le=1000)


class VisitCheckInfo(BaseModel):
    """What the visit the deployment is of says, for the checks against it: the card it left, and the photos counted when it was collected."""

    left_session: Optional[str] = None  # the visit that left the camera
    left_sd: Optional[str] = None  # the card it left in it
    collected_session: Optional[str] = None  # the visit that collected the card
    counted_photos: Optional[int] = Field(default=None, ge=0)  # the photos it counted on the card
    sd_card: Optional[str] = None  # the card the images are said to come from
    # how the visit that collected the card found it: a full card or flat batteries say why the camera stopped before it was collected
    collected_card_status: Optional[str] = None  # OK or CardFull
    collected_battery_status: Optional[str] = None  # OK or NoBatteries


class ValidateDeploymentRequest(BaseModel):
    """Checks a scanned folder's images against a deployment's own declared
    fields — run once the deployment (new or existing) is known."""

    path: str
    deployment: DeploymentFields
    # None runs every check.
    checks: Optional[list[DeploymentCheck]] = None
    # The collection the deployment goes in, when it has a folder of its own (the
    # "Local folder" destination: its name). None for a Trapper deployment, whose
    # collection is the one its id names.
    collection_name: Optional[str] = None
    # The location chosen as where the images were taken, to compare the id's with.
    expected_location_id: Optional[str] = None
    # Hours of leeway around the deployment's start and end for the images' dates.
    tolerance_hours: float = Field(default=1.0, ge=0)
    # The research project whose collections hold the previous revisions of the location.
    research_project_id: Optional[str] = None
    statistics: StatisticsParams = Field(default_factory=StatisticsParams)
    # The visit the deployment is of, for the checks of the card and of the photos (none: they have nothing to compare with).
    visit: Optional[VisitCheckInfo] = None


class CheckCollectionRequest(BaseModel):
    path: str


class ResearchProjectRecord(BaseModel):
    """A research project kept in the collections folder — the fields of
    Trapper's own "Add research project" form, its choice fields holding
    Trapper's option numbers. The acronym names its folder."""

    name: str = Field(min_length=1, max_length=255)
    acronym: str = Field(min_length=3, max_length=10, pattern=r"^[0-9A-Za-z][0-9A-Za-z_.-]*$")
    sampling_design: int = Field(default=1, ge=1, le=6)
    sensor_method: int = Field(default=1, ge=1, le=3)
    animal_types: int = Field(default=1, ge=1, le=3)
    bait_use: int = Field(default=1, ge=1, le=6)
    event_interval: int = Field(default=0, ge=0)
    # Whether it is being prepared, running or over: a finished one is not offered when a deployment is imported.
    status: Literal["planned", "active", "finished", "archived"] = "active"
    keywords: str = ""
    abstract: str = Field(default="", max_length=2000)
    methods: str = Field(default="", max_length=2000)
    description: str = Field(default="", max_length=2000)
    # Set when it was filled in from Trapper — to find its locations there later.
    trapper_pk: Optional[int] = None


class UpdateResearchProjectRequest(ResearchProjectRecord):
    """Change a research project already kept: the fields given are the ones that change, the rest stay. The acronym names it, and its folder,
    so it is the one that is found, never changed."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)  # type: ignore[assignment]
    acronym: str = Field(min_length=1)
    sampling_design: Optional[int] = Field(default=None, ge=1, le=6)  # type: ignore[assignment]
    sensor_method: Optional[int] = Field(default=None, ge=1, le=3)  # type: ignore[assignment]
    animal_types: Optional[int] = Field(default=None, ge=1, le=3)  # type: ignore[assignment]
    bait_use: Optional[int] = Field(default=None, ge=1, le=6)  # type: ignore[assignment]
    event_interval: Optional[int] = Field(default=None, ge=0)  # type: ignore[assignment]
    status: Optional[Literal["planned", "active", "finished", "archived"]] = None  # type: ignore[assignment]
    keywords: Optional[str] = None  # type: ignore[assignment]
    abstract: Optional[str] = Field(default=None, max_length=2000)  # type: ignore[assignment]
    methods: Optional[str] = Field(default=None, max_length=2000)  # type: ignore[assignment]
    description: Optional[str] = Field(default=None, max_length=2000)  # type: ignore[assignment]


DEFAULT_TIMEZONE = "UTC"


class LocationRecord(BaseModel):
    """A location of a research project kept in the collections folder."""

    location_id: str = Field(min_length=1, max_length=100)
    name: Optional[str] = None
    # IANA timezone and whether its cameras ignore summer time. Both belong to the location — never to a deployment: every deployment there uses them,
    # and Trapper only accepts a package that declares the same. They are always said when a location is made: the cameras' clocks are taken as UTC, and the
    # time of a field visit is read in the timezone of its location.
    timezone: str = Field(min_length=1)
    ignore_dst: bool
    # Where it is — WGS84 decimal degrees, as in Camtrap DP's deployments table. Always said.
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    coordinate_uncertainty: Optional[int] = Field(default=None, ge=1)
    # The day it was put into production (YYYY-MM-DD).
    in_service: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    trapper_pk: Optional[int] = None
    # Whether it is in use; an archived or a planned one is not offered for a visit. When it changed (YYYY-MM-DD) and why are free to leave out. A new one is pending: its first
    # visit starts it — it is not waited for in the revisions before.
    status: Literal["planned", "pending", "ready", "active", "archived"] = "pending"
    status_date: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    status_note: Optional[str] = None

    # what was kept as "retired" is archived now
    _legacy_status = field_validator("status", mode="before")(lambda cls, v: "archived" if v == "retired" else v)

    @field_validator("timezone")
    @classmethod
    def _known_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("is not a known IANA timezone") from exc
        return value

    @model_validator(mode="after")
    def _no_summer_time_in_utc(self) -> "LocationRecord":
        # UTC has no summer time: whether the cameras ignore it does not apply there, so it is never said to.
        if is_utc(self.timezone):
            self.ignore_dst = False
        return self


class LocalLocationsRequest(BaseModel):
    research_project_id: str = Field(min_length=1)


class DeleteLocationRequest(LocalLocationsRequest):
    location_id: str = Field(min_length=1)


class SaveLocationRequest(LocalLocationsRequest):
    location: LocationRecord
    # A person making it in the settings: it can only start as pending, or planned — a visit makes it ready (Location start) or active (an Installation).
    by_hand: bool = False


class ListVisitsRequest(LocalLocationsRequest):
    """The visits of a research project — only those to one location when it is given."""

    location_id: Optional[str] = None


class CreateRevisionRequest(LocalLocationsRequest):
    """Plan the next revision: a visit to each location that is ready, planned."""


class MarkNotVisitedRequest(LocalLocationsRequest):
    """Finish a revision: the locations with no visit in it are marked as not visited."""

    session: str = Field(pattern=r"^R\d+$")


class SaveVisitRequest(LocalLocationsRequest):
    visit: VisitRecord


class UpdateVisitRequest(LocalLocationsRequest):
    """Edit a visit kept: its site and its revision are its key — they say which one it is, and do not change."""

    location_id: str = Field(min_length=1)
    session: str = Field(pattern=r"^R\d+$")
    visit: VisitRecord


class LinkVisitRequest(LocalLocationsRequest):
    """The visit that closed a deployment (found by its location, day and time), and the deployment."""

    location_id: str = Field(min_length=1)
    date: date_type
    time: time_type
    deployment_id: str = Field(min_length=1)


class CloseAfter(BaseModel):
    """The day a revision is closed on: so many days, weeks or months after its last visit (`after_last`), or before the first visit of the revision after it (`before_next`)."""
    amount: int = Field(ge=0)
    unit: Literal["days", "weeks", "months"] = "days"
    anchor: Literal["after_last", "before_next"] = "after_last"


class ImportVisitsCsvRequest(LocalLocationsRequest):
    """The text of a CSV file with visits — only read and checked unless `save` is set, then the visits that can be kept are."""

    csv: str = ""
    save: bool = False
    # How the file is read: with the column of each field said in `mapping`, as the download of the new Epicollect5 project, or as the entries of the Epicollect5
    # project of the settings (`csv` is then not used: they are read from Epicollect5).
    format: Literal["mapped", "epicollect-api", "epicollect-csv"] = "mapped"
    mapping: Optional[dict[str, str]] = None
    # What to create when the file names a location, a camera or an SD card that does not exist: {"locations": bool, "cameras": bool, "sd_cards": bool}. The fields each one
    # needs become required (see visits_csv.CREATABLE).
    create: Optional[dict[str, bool]] = None
    # The revision before the ones the file starts is closed when it has locations still planned: each is marked as not visited (an unknown one is not).
    close_revisions: bool = False
    # The day a revision that is closed is closed on — so long after its last visit, or before the first visit of the revision after it —: the locations still to be visited in
    # it are marked as not visited on that day. The same for every revision the file closes; none closes them on the day of their last visit.
    close_after: Optional[CloseAfter] = None
    # A row with no coordinates of the visit takes those of its location — unless this is off: then it is refused.
    coordinates_from_location: bool = True
    # The photos on the cards were not counted (an old datasheet): a Revision or a Desinstallation with no count is accepted, and the deployment is not checked against a count it has not.
    photos_not_counted: bool = False
    # The value of a field that the file has no column for, or whose cell is empty: {field: value}.
    defaults: Optional[dict[str, str]] = None


class VisitsCsvColumnsRequest(BaseModel):
    """The text of a CSV file whose columns are asked for, to map them to the fields of a visit."""

    csv: str


class UpdateLocationRequest(LocalLocationsRequest):
    """Change a location already kept — its name, where it is, its timezone and/or summer-time setting. The fields left out stay as
    they are; one given as null is cleared."""

    location_id: str = Field(min_length=1)
    name: Optional[str] = None
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    coordinate_uncertainty: Optional[int] = Field(default=None, ge=1)
    timezone: Optional[str] = None
    ignore_dst: Optional[bool] = None
    in_service: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    status: Optional[Literal["planned", "pending", "ready", "active", "archived"]] = None
    status_date: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    status_note: Optional[str] = None

    @field_validator("timezone")
    @classmethod
    def _known_timezone(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("is not a known IANA timezone") from exc
        return value

    @model_validator(mode="after")
    def _no_summer_time_in_utc(self) -> "UpdateLocationRequest":
        if is_utc(self.timezone) and self.ignore_dst is not None:
            self.ignore_dst = False
        return self


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


# ── Wizard sessions (see services.session_store) ──────────────────────────


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


class SyncCollectionNamesRequest(TrapperCredentials):
    """The collections of a classification project that can be synced, and the deployments in each."""

    research_project_pk: int
    classification_project_pk: int
