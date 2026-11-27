"""#248: the record of a deployment the domains speak of (shared.deployment_record) is plain Python, and the Pydantic model handed to them keeps to it."""
import doctest
import typing

from wildintel_uploader.shared import deployment_record
from wildintel_uploader.shared.camtrap import DeploymentFields
from wildintel_uploader.shared.deployment_record import DeploymentRecord


def test_the_example_holds():
    assert doctest.testmod(deployment_record).failed == 0


def test_the_record_says_every_field_of_the_camtrap_model_and_nothing_else():
    said = {name for name, value in vars(DeploymentRecord).items() if isinstance(value, property)}
    assert said == set(DeploymentFields.model_fields)


def test_each_field_is_of_the_kind_the_record_says():
    for name, field in DeploymentFields.model_fields.items():
        said = typing.get_type_hints(getattr(DeploymentRecord, name).fget)["return"]
        kept = field.annotation
        literal_ok = typing.get_origin(kept) is typing.Union and any(typing.get_origin(a) is typing.Literal for a in typing.get_args(kept))
        assert literal_ok or set(typing.get_args(kept) or (kept,)) == set(typing.get_args(said) or (said,)), name
