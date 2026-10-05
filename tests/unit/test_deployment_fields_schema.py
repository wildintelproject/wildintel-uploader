"""core.schemas.requests.DeploymentFields — mirrors the Camtrap DP
"deployments" table (deployments-table-schema.json): field names, required
fields, numeric ranges, date format and the featureType enum."""
import pytest
from pydantic import ValidationError

from wildintel_uploader.core.schemas.requests import DeploymentFields

BASE = {
    "deployment_id": "dep1", "latitude": 52.70442, "longitude": 23.84995,
    "start_date": "2020-03-01T22:00:00Z", "end_date": "2020-04-01T22:00:00+02:00",
}


@pytest.mark.parametrize("missing", ["deployment_id", "latitude", "longitude", "start_date", "end_date"])
def test_the_standard_s_required_fields_are_required(missing: str):
    DeploymentFields.model_validate(BASE)
    with pytest.raises(ValidationError):
        DeploymentFields.model_validate({k: v for k, v in BASE.items() if k != missing})


def test_everything_else_is_optional():
    fields = DeploymentFields.model_validate(BASE)
    assert fields.location_id is None
    assert fields.camera_model is None


def test_latitude_and_longitude_are_bounded():
    DeploymentFields.model_validate({**BASE, "latitude": -90, "longitude": 180})
    with pytest.raises(ValidationError):
        DeploymentFields.model_validate({**BASE, "latitude": 91})
    with pytest.raises(ValidationError):
        DeploymentFields.model_validate({**BASE, "longitude": -181})


@pytest.mark.parametrize("field", ["start_date", "end_date"])
@pytest.mark.parametrize("value", [
    "2020-03-01T22:00:00",          # no timezone designator
    "2020-03-01",                   # date only
    "2020-03-01 22:00:00Z",         # no "T"
    "2020-03-01T22:00Z",            # no seconds
    "2020-13-01T22:00:00Z",         # no such month
    "yesterday",
])
def test_dates_need_iso_8601_with_a_timezone_designator(field: str, value: str):
    with pytest.raises(ValidationError):
        DeploymentFields.model_validate({**BASE, field: value})


@pytest.mark.parametrize("value", ["2020-03-01T22:00:00Z", "2020-03-01T22:00:00+02:00", "2020-03-01T22:00:00-05:30"])
def test_dates_accept_z_and_offsets(value: str):
    assert DeploymentFields.model_validate({**BASE, "start_date": value}).start_date == value


def test_the_deployment_starts_before_it_ends():
    with pytest.raises(ValidationError, match="earlier than"):
        DeploymentFields.model_validate({**BASE, "start_date": "2020-04-01T22:00:00Z", "end_date": "2020-03-01T22:00:00Z"})
    with pytest.raises(ValidationError, match="earlier than"):
        DeploymentFields.model_validate({**BASE, "start_date": "2020-03-01T22:00:00Z", "end_date": "2020-03-01T22:00:00Z"})  # not the same instant either


def test_the_dates_are_compared_as_instants_not_as_wall_clock_times():
    # 10:00 at +05:00 is 05:00 UTC, before 08:00 at +01:00 (07:00 UTC) even though 10 > 08 on the clock.
    DeploymentFields.model_validate({**BASE, "start_date": "2020-03-01T10:00:00+05:00", "end_date": "2020-03-01T08:00:00+01:00"})
    with pytest.raises(ValidationError):
        DeploymentFields.model_validate({**BASE, "start_date": "2020-03-01T08:00:00+01:00", "end_date": "2020-03-01T10:00:00+05:00"})


def test_coordinate_uncertainty_is_a_positive_integer():
    DeploymentFields.model_validate({**BASE, "coordinate_uncertainty": 100})
    with pytest.raises(ValidationError):
        DeploymentFields.model_validate({**BASE, "coordinate_uncertainty": 0})
    with pytest.raises(ValidationError):
        DeploymentFields.model_validate({**BASE, "coordinate_uncertainty": 10.5})


@pytest.mark.parametrize("field,bad_value", [
    ("camera_interval", -1), ("camera_height", -1), ("camera_depth", -1), ("detection_distance", -1),
    ("camera_tilt", -91), ("camera_tilt", 91), ("camera_heading", -1), ("camera_heading", 361),
    ("camera_interval", 1.5), ("camera_tilt", 10.5), ("camera_heading", 10.5),
])
def test_camera_fields_reject_out_of_range_or_non_integer_values(field: str, bad_value: float):
    with pytest.raises(ValidationError):
        DeploymentFields.model_validate({**BASE, field: bad_value})


def test_camera_height_and_depth_are_mutually_exclusive():
    DeploymentFields.model_validate({**BASE, "camera_height": 1.2})
    DeploymentFields.model_validate({**BASE, "camera_depth": 4.8})
    with pytest.raises(ValidationError, match="mutually exclusive"):
        DeploymentFields.model_validate({**BASE, "camera_height": 1.2, "camera_depth": 4.8})


def test_feature_type_only_accepts_the_standard_s_enum():
    DeploymentFields.model_validate({**BASE, "feature_type": "culvert"})
    with pytest.raises(ValidationError):
        DeploymentFields.model_validate({**BASE, "feature_type": "none"})  # Trapper's own value, not in the standard


def test_bait_type_no_longer_exists_bait_use_does():
    fields = DeploymentFields.model_validate({**BASE, "bait_use": True})
    assert fields.bait_use is True
    assert not hasattr(fields, "bait_type")


def test_session_and_array_are_merged_into_deployment_groups():
    fields = DeploymentFields.model_validate({**BASE, "deployment_groups": "season:winter 2020 | grid:A1"})
    assert fields.deployment_groups == "season:winter 2020 | grid:A1"
    assert not hasattr(fields, "session") and not hasattr(fields, "array")
