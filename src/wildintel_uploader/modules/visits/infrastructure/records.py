"""The record of a visit — what is kept of it, and what a visit sent is checked against —, as Pydantic validates it: the rules a single visit
follows on its own (its actions, its status, what a full card or a camera taken away can't say). What it is with the other visits is the domain's
(domain.rules)."""
from __future__ import annotations

from datetime import date as date_type, time as time_type
from typing import Literal, Optional

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, field_validator, model_validator

from wildintel_uploader.modules.visits.domain.wall_clock import is_utc
from wildintel_uploader.modules.visits.domain.rules import CAMERA_STATUSES, battery_status_code, camera_status_code, card_status_code, split_card_batteries

# The kinds of place a deployment is at, as Camtrap DP names them (featureType).
FeatureType = Literal[
    "roadPaved", "roadDirt", "trailHiking", "trailGame", "roadUnderpass", "roadOverpass", "roadBridge",
    "culvert", "burrow", "nestSite", "carcass", "waterSource", "fruitingTree",
]


class VisitRecord(BaseModel):
    """A visit to a camera trap, as the fieldwork datasheet keeps it, at a location of the research project.

    What the datasheet has that Camtrap DP does not is the visit's own (session, action, status, card and batteries, the
    photos counted, the SD card, whether the camera's date and time were right, and who went: trappers); what it has of a
    deployment is named as DeploymentFields names it — camera_id (Camera), comments (Notes), the coordinates, setup_by —
    beside the optional details the field app may also ask for."""

    location_id: str = Field(min_length=1, max_length=100)
    session: str = Field(pattern=r"^R\d+$")
    date: date_type
    time: time_type
    # The instant of the visit, ISO 8601 in UTC with a Z — what is kept; the day and the time above are the wall clock of its location. Worked out when it is left out.
    when: Optional[str] = None
    # A visit may do several things: a camera revised and another put up, a card changed and the camera taken away…
    # Empty only for a visit that could not be made (its status says it was not revised): nothing was done at it.
    actions: list[Literal["SiteStart", "Installation", "Revision", "Desinstallation", "Stolen", "Archive"]] = Field(default_factory=list)
    trappers: Optional[str] = None
    # The status of the camera when the visit found it (e.g. Working, Not revised).
    camera_status: Optional[str] = None
    # How the batteries were (OK, or NoBatteries when there were none) and how the SD card was (OK, or CardFull). They were one field, card_batteries_ok: a visit that says it is read as both.
    battery_status: Optional[Literal["OK", "NoBatteries"]] = None
    card_status: Optional[Literal["OK", "CardFull"]] = None
    num_photos: Optional[int] = Field(default=None, ge=0)
    sd: Optional[str] = None
    date_time_ok: Optional[str] = None
    # Whether the camera was calibrated at the visit (a check of the field flow that Camtrap DP does not have) — asked where a camera is left or put up.
    calibration: Optional[bool] = None
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    # The deployment this visit started — the images of the card it left, once they are imported (see local_folder_service.closed_visits).
    deployment_id: Optional[str] = None
    # Where the visit is in its life: deployed (it left a camera that is still out), collected (its card was collected), stolen, or not visited (it could not be made).
    # Kept when the visit is added, and changed when a later visit gives it a deployment — see visit_deployments.refresh_states.
    state: Optional[Literal["deployed", "collected", "stolen", "not_visited", "no_camera"]] = None
    # When the visit was registered and when it was last changed (ISO 8601, UTC, with a Z): written by the app when the visit is kept (see services.audit), never typed —
    # what is sent for them is not taken.
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    setup_by: Optional[str] = None
    # The camera of the visit (#231): the id of its record in the research project (camera_ref) — what the visit points to — and its label (camera_id), to tell
    # it. What the camera is — its model as Camtrap DP says it and its serial number — is told from the record, and not kept in the visit.
    camera_ref: Optional[str] = None
    camera_id: Optional[str] = None
    camera_model: Optional[str] = None
    camera_serial: Optional[str] = None
    camera_interval: Optional[int] = Field(default=None, ge=0)
    camera_height: Optional[float] = Field(default=None, ge=0)
    camera_depth: Optional[float] = Field(default=None, ge=0)
    camera_tilt: Optional[int] = Field(default=None, ge=-90, le=90)
    camera_heading: Optional[int] = Field(default=None, ge=0, le=360)
    detection_distance: Optional[float] = Field(default=None, ge=0)
    timestamp_issues: Optional[bool] = None
    bait_use: Optional[bool] = None
    feature_type: Optional[FeatureType] = None
    habitat: Optional[str] = None
    deployment_groups: Optional[str] = None
    comments: Optional[str] = None
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _one_field_before(cls, data):
        """A visit that says card_batteries_ok — how it was kept before — says the status of the batteries and the one of the card."""
        if isinstance(data, dict) and "card_batteries_ok" in data:
            data = dict(data)
            battery, card = split_card_batteries(data.pop("card_batteries_ok"))
            if battery and not data.get("battery_status"):
                data["battery_status"] = battery
            if card and not data.get("card_status"):
                data["card_status"] = card
        return data

    @field_validator("battery_status", mode="before")
    @classmethod
    def _battery_code(cls, value):
        return None if value in (None, "") else (battery_status_code(value) or value)

    @field_validator("card_status", mode="before")
    @classmethod
    def _card_code(cls, value):
        return None if value in (None, "") else (card_status_code(value) or value)

    @field_validator("camera_status", mode="before")
    @classmethod
    def _camera_status_code(cls, value):
        if value is None or str(value).strip() == "":
            return None
        code = camera_status_code(value)
        if code is None:
            raise ValueError("The status of the camera is " + ", ".join(CAMERA_STATUSES[:-1]) + " or " + CAMERA_STATUSES[-1] + ".")
        return code

    @field_validator("actions")
    @classmethod
    def _once_each(cls, actions: list[str]) -> list[str]:
        return list(dict.fromkeys(actions))

    @model_validator(mode="after")
    def _the_status_of_a_camera_found_stolen_is_stolen(self):
        # a Stolen visit says it all with its action: the status of the camera is Stolen — and only there is the camera found stolen
        if "Stolen" in self.actions:
            if self.camera_status not in (None, "Stolen"):
                raise ValueError("The camera of a Stolen visit is stolen: its status is Stolen.")
            self.camera_status = "Stolen"
        elif self.camera_status == "Stolen":
            raise ValueError("The status Stolen is for the visit that finds the camera stolen: its action is Stolen.")
        return self

    @model_validator(mode="after")
    def _no_card_left_where_the_camera_is_taken_away(self):
        # the camera that is taken away goes with its card: nothing is left, unless another camera is put up
        actions = set(self.actions)
        if "Desinstallation" in actions and "Installation" not in actions and self.sd:
            raise ValueError("No SD card is left where the camera is taken away: leave the card out.")
        return self

    @model_validator(mode="after")
    def _no_photos_on_a_full_card(self):
        # with the card full its photos are not counted: their number is not given
        if self.card_status == "CardFull" and self.num_photos is not None:
            raise ValueError("The images on a full card are not counted: leave their number out.")
        return self

    @model_validator(mode="after")
    def _something_was_done(self):
        # a visit that could not be made did nothing; any other did at least one thing
        if not self.actions and str(self.camera_status or "").strip().lower() not in ("not revised", "no revisada", "no revisado"):
            raise ValueError("A visit does at least one action — only a visit that could not be made (status Not revised) has none.")
        return self

    @model_validator(mode="after")
    def _height_or_depth(self) -> "VisitRecord":
        if self.camera_height is not None and self.camera_depth is not None:
            raise ValueError("camera_height and camera_depth are mutually exclusive: only one should be set.")
        return self


class NewLocationRecord(BaseModel):
    """A location a file of visits makes (a New site), as the catalog takes one: with its timezone and its summer-time setting, and where it is."""

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
    def _no_summer_time_in_utc(self) -> "NewLocationRecord":
        # UTC has no summer time: whether the cameras ignore it does not apply there, so it is never said to.
        if is_utc(self.timezone):
            self.ignore_dst = False
        return self
