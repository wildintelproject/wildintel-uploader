"""#248: what the visits offer the catalog (visits.domain.for_the_catalog) — its example holds, and it says the same as the rules it opens onto."""
import doctest

from wildintel_uploader.modules.visits.domain import for_the_catalog, rules


def test_the_example_holds():
    assert doctest.testmod(for_the_catalog).failed == 0


def test_what_a_visit_does_is_what_the_rules_of_the_visits_say():
    before = [{"location_id": "DONA_01", "session": "R0001", "date": "2026-06-10", "time": "09:00:00", "when": "2026-06-10T09:00:00Z",
               "actions": ["Installation"], "camera_id": "C1", "sd": "S1"}]
    visit = {"location_id": "DONA_01", "session": "R0002", "date": "2026-08-05", "time": "09:00:00", "when": "2026-08-05T09:00:00Z",
             "actions": ["Desinstallation"], "camera_id": "C1"}
    assert for_the_catalog.entity_changes(visit, before) == rules.entity_changes(visit, before) != []


def test_the_example_of_the_door_of_the_timefix_holds():
    from wildintel_uploader.modules.visits.domain import for_the_timefix
    assert doctest.testmod(for_the_timefix).failed == 0
