"""#248: the rules a visit keeps to by itself are the domain's (visits.domain.integrity) — held without Pydantic, whatever made the visit."""
import doctest

import pytest

from wildintel_uploader.modules.visits.domain import integrity


def test_the_examples_of_the_rules_hold():
    assert doctest.testmod(integrity).failed == 0


@pytest.mark.parametrize("visit, problem", [
    ({"actions": ["Stolen"], "camera_status": "Working"}, "its status is Stolen"),
    ({"actions": ["Revision"], "camera_status": "Stolen"}, "its action is Stolen"),
    ({"actions": ["Desinstallation"], "sd": "SD01"}, "No SD card is left"),
    ({"actions": ["Revision"], "card_status": "CardFull", "num_photos": 3}, "not counted"),
    ({"actions": [], "camera_status": "Working"}, "at least one action"),
    ({"actions": ["Installation"], "camera_height": 1.2, "camera_depth": 3.0}, "mutually exclusive"),
], ids=["stolen status", "stolen action", "card left", "full card", "nothing done", "height and depth"])
def test_a_visit_that_breaks_a_rule_is_told_why(visit, problem):
    assert any(problem in p for p in integrity.problems(visit))


@pytest.mark.parametrize("visit", [
    {"actions": ["Stolen"]},
    {"actions": ["Desinstallation", "Installation"], "sd": "SD01"},
    {"actions": [], "camera_status": "Not revised"},
    {"actions": ["Revision"], "card_status": "CardFull"},
], ids=["stolen", "camera changed", "not revised", "full card"])
def test_a_visit_that_keeps_the_rules_has_no_problem(visit):
    assert integrity.problems(visit) == []


def test_the_camera_of_a_stolen_visit_is_stolen():
    assert integrity.camera_status_of({"actions": ["Stolen"]}) == "Stolen"
    assert integrity.camera_status_of({"actions": ["Revision"], "camera_status": "Working"}) == "Working"
