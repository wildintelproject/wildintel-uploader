"""The records of the app as tables — SQLModel (SQLAlchemy + Pydantic) models, one for each JSON file of store/files, for the day they are kept in a database.

Nothing uses this yet: it is a design to have at hand. It follows the JSON files as they are *kept* (see store/files/*.schema.json), with three differences a database asks for:

  * What a record points to is a **foreign key**, not an id that may be missing: a visit says its location, its camera, its SD card and who went by key. The JSON files keep the name
    when what it names is not one of the project's (`visits.location_id`, `camera_id`, `sd`, `setup_by`, `trappers`); here those go in the `*_text` columns, and a location is
    always required — a migration creates the location that a visit names, or refuses the visit.
  * What is a list in a visit (its actions, who went) is a table of its own: `VisitAction`, `VisitTrapper`.
  * The instants and the days are `datetime` and `date`, not text. Every instant is UTC (the JSON ones end in Z); a location's timezone is how its visits are *told*.

The audit columns of every record — `id`, `created_at`, `updated_at`, `deleted_at` — are the app's, as in the files: nothing is deleted, a removed record has `deleted_at`. What the services
check across records (a camera is up at one location at a time, a revision starts when the one before it is finished…) is not here: a table cannot say it. The checks it can say are
the `CheckConstraint`s and the unique indexes; the rest is in `x-rules` of each schema and in the README.

    from sqlmodel import SQLModel, create_engine
    engine = create_engine("sqlite:///wildintel.db")        # or PostgreSQL: the models use nothing of SQLite
    SQLModel.metadata.create_all(engine)

Not here, as the images, the reports and the sessions are not kept in it: the images of a deployment (`images.json`, `preprocessing.json` and the files), the reports, the sessions, and the
settings (`settings.toml`).
"""

import enum
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import CheckConstraint, Index, JSON, UniqueConstraint, func
from sqlmodel import Column, Field, Relationship, SQLModel


def new_id() -> str:
    """A record's id: a UUID, as text, written by the app when the record is kept and never changed."""
    return str(uuid.uuid4())


def now() -> datetime:
    return datetime.now(timezone.utc)


# ── what a column may say ───────────────────────────────────────────────────────────────────────────────────────────────────

class ResearchProjectStatus(str, enum.Enum):
    planned = "planned"
    active = "active"
    finished = "finished"
    archived = "archived"


class GearStatus(str, enum.Enum):
    """The status of a location, a camera or an SD card. `archived` is for good: it never goes back."""
    planned = "planned"      # only in the settings: it is not in the app yet
    ready = "ready"          # available, not in the field yet
    active = "active"        # in use: a camera up at a location, a card in a camera, a location with a camera
    archived = "archived"


class TrapperStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    archived = "archived"


class ArchiveReason(str, enum.Enum):
    lost = "lost"
    stolen = "stolen"
    broken = "broken"
    other = "other"


class Connectivity(str, enum.Enum):
    none = "none"
    g4 = "4g"
    g5 = "5g"


class PowerSource(str, enum.Enum):
    cells = "cells"
    battery = "battery"


class YesNo(str, enum.Enum):
    yes = "yes"
    no = "no"


class RoleName(str, enum.Enum):
    """The roles of a contributor in Camtrap DP."""
    contact = "contact"
    principalInvestigator = "principalInvestigator"
    rightsHolder = "rightsHolder"
    publisher = "publisher"
    contributor = "contributor"


class Action(str, enum.Enum):
    Installation = "Installation"
    Revision = "Revision"
    Desinstallation = "Desinstallation"
    Stolen = "Stolen"
    Archive = "Archive"


class BatteryStatus(str, enum.Enum):
    OK = "OK"
    NoBatteries = "NoBatteries"


class CardStatus(str, enum.Enum):
    OK = "OK"
    CardFull = "CardFull"


class VisitState(str, enum.Enum):
    """Where a visit is in its life — worked out from the visits (visit_deployments.refresh_states)."""
    deployed = "deployed"          # it left a camera that is still out
    collected = "collected"        # its card was collected
    stolen = "stolen"              # the camera was found stolen: no images
    not_visited = "not_visited"    # the visit could not be made
    no_camera = "no_camera"        # it left none


class FeatureType(str, enum.Enum):
    """Camtrap DP's featureType."""
    roadPaved = "roadPaved"
    roadDirt = "roadDirt"
    trailHiking = "trailHiking"
    trailGame = "trailGame"
    roadUnderpass = "roadUnderpass"
    roadOverpass = "roadOverpass"
    roadBridge = "roadBridge"
    culvert = "culvert"
    burrow = "burrow"
    nestSite = "nestSite"
    carcass = "carcass"
    waterSource = "waterSource"
    fruitingTree = "fruitingTree"
    other = "other"


class Audited(SQLModel):
    """What every record has: its id, and when it was kept, changed and — if it was — removed. Written by the app, never typed."""
    id: str = Field(default_factory=new_id, primary_key=True, max_length=36)
    created_at: datetime = Field(default_factory=now, nullable=False)
    updated_at: datetime = Field(default_factory=now, nullable=False)
    deleted_at: Optional[datetime] = Field(default=None, description="When it was removed: it is no longer listed, but it is kept.")


_DAY = "in_service"


# ── the people ──────────────────────────────────────────────────────────────────────────────────────────────────────────────

class Trapper(Audited, table=True):
    """One of the people who go to the field. They belong to no research project: what each is in a project is its role. (trappers.json)"""
    __tablename__ = "trappers"
    __table_args__ = (CheckConstraint("length(username) > 0 AND username NOT LIKE '% %'", name="ck_trappers_username"),)

    username: str = Field(index=False, description="What it is called in the app: unique whatever its case, with no spaces.")
    name: str = Field(min_length=1, description="The full name, as it should be on a visit.")
    affiliation: Optional[str] = None
    email: Optional[str] = None
    status: TrapperStatus = Field(default=TrapperStatus.active)
    trapper_pk: Optional[int] = Field(default=None, description="Its id in Trapper, when it was taken from there: such a trapper can only be seen here.")

    roles: list["TrapperRole"] = Relationship(back_populates="trapper")


# ── a research project and what belongs to it ───────────────────────────────────────────────────────────────────────────────

class ResearchProject(Audited, table=True):
    """A research project: its folder, what it studies and how it was designed. (research_project.json)"""
    __tablename__ = "research_projects"
    __table_args__ = (
        CheckConstraint("length(acronym) BETWEEN 3 AND 10", name="ck_research_projects_acronym"),
        CheckConstraint("sampling_design BETWEEN 1 AND 6", name="ck_research_projects_sampling_design"),
        CheckConstraint("sensor_method BETWEEN 1 AND 3", name="ck_research_projects_sensor_method"),
        CheckConstraint("animal_types BETWEEN 1 AND 3", name="ck_research_projects_animal_types"),
        CheckConstraint("bait_use BETWEEN 1 AND 6", name="ck_research_projects_bait_use"),
        CheckConstraint("event_interval >= 0", name="ck_research_projects_event_interval"),
    )

    acronym: str = Field(unique=True, index=True, max_length=10, description="It names the project's folder: letters, digits, '_', '-' and '.', starting with a letter or a digit.")
    name: str = Field(min_length=1, max_length=255)
    sampling_design: int = Field(default=1)
    sensor_method: int = Field(default=1)
    animal_types: int = Field(default=1)
    bait_use: int = Field(default=1)
    event_interval: int = Field(default=0)
    status: ResearchProjectStatus = Field(default=ResearchProjectStatus.active)
    keywords: str = Field(default="")
    abstract: str = Field(default="", max_length=2000)
    methods: str = Field(default="", max_length=2000)
    description: str = Field(default="", max_length=2000)
    trapper_pk: Optional[int] = Field(default=None, description="Its id in Trapper, when it is there.")

    locations: list["Location"] = Relationship(back_populates="research_project")
    cameras: list["Camera"] = Relationship(back_populates="research_project")
    sd_cards: list["SdCard"] = Relationship(back_populates="research_project")
    roles: list["TrapperRole"] = Relationship(back_populates="research_project")
    visits: list["Visit"] = Relationship(back_populates="research_project")
    collections: list["Collection"] = Relationship(back_populates="research_project")


class TrapperRole(Audited, table=True):
    """What a trapper is in a research project: a contributor of Camtrap DP. (roles.json)"""
    __tablename__ = "trapper_roles"
    __table_args__ = (UniqueConstraint("research_project_id", "trapper_id", "role", name="uq_trapper_roles"),)

    research_project_id: str = Field(foreign_key="research_projects.id", index=True)
    trapper_id: str = Field(foreign_key="trappers.id", index=True)
    role: RoleName = Field(default=RoleName.contributor)

    research_project: ResearchProject = Relationship(back_populates="roles")
    trapper: Trapper = Relationship(back_populates="roles")


class Location(Audited, table=True):
    """A place where the cameras are put up: a site of Camtrap DP. Its timezone is how the day and the time of its visits are told. (locations.json)"""
    __tablename__ = "locations"
    __table_args__ = (
        UniqueConstraint("research_project_id", "location_id", name="uq_locations_location_id"),
        CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_locations_latitude"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_locations_longitude"),
        CheckConstraint("coordinate_uncertainty IS NULL OR coordinate_uncertainty >= 1", name="ck_locations_uncertainty"),
        CheckConstraint("length(location_id) BETWEEN 1 AND 100", name="ck_locations_location_id"),
    )

    research_project_id: str = Field(foreign_key="research_projects.id", index=True)
    location_id: str = Field(max_length=100, description="What the location is called in the project: unique in it, whatever its case.")
    name: Optional[str] = None
    timezone: str = Field(min_length=1, description="An IANA name (Europe/Madrid).")
    ignore_dst: bool = Field(description="Whether its cameras ignore summer time.")
    latitude: float
    longitude: float
    coordinate_uncertainty: Optional[int] = Field(default=None, description="Metres.")
    in_service: Optional[date] = Field(default=None, description="The day it was put into production.")
    trapper_pk: Optional[int] = None
    status: GearStatus = Field(default=GearStatus.ready)
    status_date: Optional[date] = None
    status_note: Optional[str] = None

    research_project: ResearchProject = Relationship(back_populates="locations")
    visits: list["Visit"] = Relationship(back_populates="location")


class Camera(Audited, table=True):
    """A camera of a research project. (cameras.json)"""
    __tablename__ = "cameras"
    __table_args__ = (CheckConstraint("status <> 'archived' OR archive_reason IS NOT NULL", name="ck_cameras_archive_reason"),)

    research_project_id: str = Field(foreign_key="research_projects.id", index=True)
    label: str = Field(min_length=1, description="How it is called in the field: unique in the project, whatever its case.")
    camera_id: Optional[str] = Field(default=None, description="Its serial number, as Camtrap DP's cameraID: unique in the project when it has one.")
    camera_model: Optional[str] = None
    connectivity: Optional[Connectivity] = None
    power_source: Optional[PowerSource] = None
    battery_removable: Optional[YesNo] = None
    in_service: Optional[date] = None
    status: GearStatus = Field(default=GearStatus.ready)
    archive_reason: Optional[ArchiveReason] = None
    status_date: Optional[date] = None
    status_note: Optional[str] = None

    research_project: ResearchProject = Relationship(back_populates="cameras")
    visits: list["Visit"] = Relationship(back_populates="camera")


class SdCard(Audited, table=True):
    """An SD card of a research project. (sd_cards.json)"""
    __tablename__ = "sd_cards"
    __table_args__ = (CheckConstraint("status <> 'archived' OR archive_reason IS NOT NULL", name="ck_sd_cards_archive_reason"),)

    research_project_id: str = Field(foreign_key="research_projects.id", index=True)
    label: str = Field(min_length=1, description="The number written on it: unique in the project, whatever its case.")
    brand: Optional[str] = None
    capacity: Optional[str] = Field(default=None, description="Free text: 64 GB.")
    in_service: Optional[date] = None
    status: GearStatus = Field(default=GearStatus.ready)
    archive_reason: Optional[ArchiveReason] = None
    status_date: Optional[date] = None
    status_note: Optional[str] = None

    research_project: ResearchProject = Relationship(back_populates="sd_cards")
    visits: list["Visit"] = Relationship(back_populates="sd_card")


# ── the visits ──────────────────────────────────────────────────────────────────────────────────────────────────────────────

class Visit(Audited, table=True):
    """A visit to a camera trap, at a location, in a revision: the history of the field work, from which the deployments are worked out. (visits.json)

    `when` is the instant, UTC; its day and time on the wall clock of the location are `when` in the location's timezone. A visit that could not be made has `camera_status`
    'Not revised' and no actions."""
    __tablename__ = "visits"
    __table_args__ = (
        UniqueConstraint("research_project_id", "location_id", "session", name="uq_visits_location_session"),
        CheckConstraint("session LIKE 'R%' AND length(session) >= 2", name="ck_visits_session"),
        CheckConstraint("num_photos IS NULL OR num_photos >= 0", name="ck_visits_num_photos"),
        CheckConstraint("card_status IS NOT 'CardFull' OR num_photos IS NULL", name="ck_visits_full_card_not_counted"),
        CheckConstraint("latitude IS NULL OR latitude BETWEEN -90 AND 90", name="ck_visits_latitude"),
        CheckConstraint("longitude IS NULL OR longitude BETWEEN -180 AND 180", name="ck_visits_longitude"),
        CheckConstraint("camera_interval IS NULL OR camera_interval >= 0", name="ck_visits_camera_interval"),
        CheckConstraint("camera_height IS NULL OR camera_height >= 0", name="ck_visits_camera_height"),
        CheckConstraint("camera_depth IS NULL OR camera_depth >= 0", name="ck_visits_camera_depth"),
        CheckConstraint("camera_height IS NULL OR camera_depth IS NULL", name="ck_visits_height_or_depth"),
        CheckConstraint("camera_tilt IS NULL OR camera_tilt BETWEEN -90 AND 90", name="ck_visits_camera_tilt"),
        CheckConstraint("camera_heading IS NULL OR camera_heading BETWEEN 0 AND 360", name="ck_visits_camera_heading"),
        CheckConstraint("detection_distance IS NULL OR detection_distance >= 0", name="ck_visits_detection_distance"),
        Index("ix_visits_when", "research_project_id", "when"),
    )

    research_project_id: str = Field(foreign_key="research_projects.id", index=True)
    location_id: str = Field(foreign_key="locations.id", index=True)
    session: str = Field(description="The revision: R0001, R0002… A location has one visit in a revision.")
    when: datetime = Field(description="The instant of the visit, UTC.")

    camera_status: Optional[str] = Field(default=None, description="How the camera was found: OK, Altered, Knocked down, Damaged, Stolen, Not revised, New site, Inactive site.")
    battery_status: Optional[BatteryStatus] = None
    card_status: Optional[CardStatus] = None
    num_photos: Optional[int] = Field(default=None, description="The photos on the card collected; none when the card was full (not counted).")
    date_time_ok: Optional[str] = None
    calibration: Optional[bool] = None
    latitude: Optional[float] = Field(default=None, description="Where the trapper was when the visit was noted: not the location's.")
    longitude: Optional[float] = None
    state: Optional[VisitState] = None
    deployment_id: Optional[str] = Field(default=None, description="The deployment the visit started, once its images are imported: <R000N>-<location>.")

    camera_id: Optional[str] = Field(default=None, foreign_key="cameras.id", index=True)
    sd_card_id: Optional[str] = Field(default=None, foreign_key="sd_cards.id", index=True, description="The SD card left in the camera.")
    setup_by_id: Optional[str] = Field(default=None, foreign_key="trappers.id", description="Who set the camera up.")
    # what was said and is not one of the project's — kept as it was said
    camera_text: Optional[str] = None
    sd_text: Optional[str] = None
    setup_by_text: Optional[str] = None
    trappers_text: Optional[str] = Field(default=None, description="The names of who went that are not trappers of the list, comma separated.")

    camera_model: Optional[str] = None
    camera_interval: Optional[int] = None
    camera_height: Optional[float] = None
    camera_depth: Optional[float] = None
    camera_tilt: Optional[int] = None
    camera_heading: Optional[int] = None
    detection_distance: Optional[float] = None
    timestamp_issues: Optional[bool] = None
    bait_use: Optional[bool] = None
    feature_type: Optional[FeatureType] = None
    habitat: Optional[str] = None
    deployment_groups: Optional[str] = None
    comments: Optional[str] = None
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False, server_default="[]"))

    research_project: ResearchProject = Relationship(back_populates="visits")
    location: Location = Relationship(back_populates="visits")
    camera: Optional[Camera] = Relationship(back_populates="visits")
    sd_card: Optional[SdCard] = Relationship(back_populates="visits")
    actions: list["VisitAction"] = Relationship(back_populates="visit", sa_relationship_kwargs={"cascade": "all, delete-orphan"})
    trappers: list["VisitTrapper"] = Relationship(back_populates="visit", sa_relationship_kwargs={"cascade": "all, delete-orphan"})


class VisitAction(SQLModel, table=True):
    """What a visit did — one or more. Empty only for a visit that could not be made. (visits.json › actions)"""
    __tablename__ = "visit_actions"

    visit_id: str = Field(foreign_key="visits.id", primary_key=True)
    action: Action = Field(primary_key=True)

    visit: Visit = Relationship(back_populates="actions")


class VisitTrapper(SQLModel, table=True):
    """Who went on a visit. (visits.json › trapper_refs)"""
    __tablename__ = "visit_trappers"

    visit_id: str = Field(foreign_key="visits.id", primary_key=True)
    trapper_id: str = Field(foreign_key="trappers.id", primary_key=True)

    visit: Visit = Relationship(back_populates="trappers")


class UnknownVisit(SQLModel, table=True):
    """A visit that nothing is known of — no day, no camera, no card — to a location in a revision before its first known visit. It counts as a visit to finish a revision, but nothing can
    be checked against it; a real visit takes its place. (unknown_visits.json)"""
    __tablename__ = "unknown_visits"
    __table_args__ = (CheckConstraint("session LIKE 'R%' AND length(session) >= 2", name="ck_unknown_visits_session"),)

    location_id: str = Field(foreign_key="locations.id", primary_key=True)
    session: str = Field(primary_key=True)


# ── what is kept beside the images ──────────────────────────────────────────────────────────────────────────────────────────

class Collection(Audited, table=True):
    """A collection — a revision — of a research project: R0001, R0002… Its images are files. (<R000N>/collection.json)"""
    __tablename__ = "collections"
    __table_args__ = (
        UniqueConstraint("research_project_id", "name", name="uq_collections_name"),
        CheckConstraint("name LIKE 'R%' AND length(name) >= 2", name="ck_collections_name"),
    )

    research_project_id: str = Field(foreign_key="research_projects.id", index=True)
    name: str

    research_project: ResearchProject = Relationship(back_populates="collections")
    deployments: list["Deployment"] = Relationship(back_populates="collection")


class Deployment(Audited, table=True):
    """A deployment, with the fields Camtrap DP names: where a camera was, from when to when and how. Kept beside its images; the images are files. (<R000N>/<deployment id>/deployment.json)"""
    __tablename__ = "deployments"
    __table_args__ = (
        UniqueConstraint("collection_id", "deployment_id", name="uq_deployments_deployment_id"),
        CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_deployments_latitude"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_deployments_longitude"),
        CheckConstraint("end_date >= start_date", name="ck_deployments_period"),
        CheckConstraint("coordinate_uncertainty IS NULL OR coordinate_uncertainty >= 1", name="ck_deployments_uncertainty"),
        CheckConstraint("camera_height IS NULL OR camera_depth IS NULL", name="ck_deployments_height_or_depth"),
        CheckConstraint("camera_tilt IS NULL OR camera_tilt BETWEEN -90 AND 90", name="ck_deployments_camera_tilt"),
        CheckConstraint("camera_heading IS NULL OR camera_heading BETWEEN 0 AND 360", name="ck_deployments_camera_heading"),
    )

    collection_id: str = Field(foreign_key="collections.id", index=True)
    location_id: Optional[str] = Field(default=None, foreign_key="locations.id", index=True)
    deployment_id: str = Field(min_length=1, description="<R000N>-<location id>.")
    location_name: Optional[str] = None
    latitude: float
    longitude: float
    coordinate_uncertainty: Optional[int] = None
    start_date: datetime = Field(description="The start, UTC — told on the wall clock of the location's timezone.")
    end_date: datetime
    setup_by: Optional[str] = Field(default=None, description="Free text: 'Setup: … | Retrieval: …' when the two visits say different things.")
    camera_id: Optional[str] = None
    camera_model: Optional[str] = None
    camera_interval: Optional[int] = None
    camera_height: Optional[float] = None
    camera_depth: Optional[float] = None
    camera_tilt: Optional[int] = None
    camera_heading: Optional[int] = None
    detection_distance: Optional[float] = None
    timestamp_issues: Optional[bool] = None
    bait_use: Optional[bool] = None
    feature_type: Optional[FeatureType] = None
    habitat: Optional[str] = None
    deployment_groups: Optional[str] = None
    comments: Optional[str] = None
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False, server_default="[]"))

    collection: Collection = Relationship(back_populates="deployments")


class UploadFailure(SQLModel, table=True):
    """An upload of a deployment to a destination that was tried and failed. A success takes it away. (upload_failures.json)"""
    __tablename__ = "upload_failures"

    research_project_id: str = Field(foreign_key="research_projects.id", primary_key=True)
    deployment_id: str = Field(primary_key=True, description="The <R000N>-<location id> of the deployment.")
    destination: str = Field(primary_key=True, description="Where it was to go: trapper…")
    note: Optional[str] = Field(default=None, description="Why it failed.")
    at: datetime = Field(default_factory=now, description="When it was tried.")


# ── unique without regard to case — the files compare them lower-cased ─────────────────────────────────────────────────────

Index("uq_trappers_username", func.lower(Trapper.__table__.c.username), unique=True)
Index("uq_cameras_label", Camera.__table__.c.research_project_id, func.lower(Camera.__table__.c.label), unique=True)
Index("uq_cameras_camera_id", Camera.__table__.c.research_project_id, func.lower(Camera.__table__.c.camera_id), unique=True)
Index("uq_sd_cards_label", SdCard.__table__.c.research_project_id, func.lower(SdCard.__table__.c.label), unique=True)
Index("uq_locations_location_id_nocase", Location.__table__.c.research_project_id, func.lower(Location.__table__.c.location_id), unique=True)
