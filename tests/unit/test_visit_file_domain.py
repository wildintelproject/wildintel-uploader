"""#248: the rules of a file of visits (modules.visits.domain.visit_file) — plain Python, no CSV, no models."""
import pytest

from wildintel_uploader.modules.visits.domain import visit_file as rules
from wildintel_uploader.modules.visits.domain.models import VisitsFailed


def test_what_a_cell_says():
    assert rules.actions_of("i + R") == ["Installation", "Revision"] and rules.actions_of("Installation+Dance") is None
    assert rules.session_of("13") == "R0013" and rules.session_of("R0002") == "R0002" and rules.session_of("none") is None
    assert (rules.yes_no_of("Sí"), rules.yes_no_of("no"), rules.yes_no_of("maybe")) == (True, False, None)
    assert rules.card_code("Card full and no batteries") == "CarFullNoBatteries" and rules.card_code("SinPilas") == "NoBatteries"
    assert rules.whole_of("12.0") == 12 and rules.number_of("x") is None and rules.tags_of("a| b;") == ["a", "b"]


def test_when_a_visit_was():
    assert rules.when({"date": "04/09/2024", "time": "10:16"}, {}) == ("2024-09-04", "10:16:00")
    assert rules.when({"when": "2024-09-04 10:16"}, {}) == ("2024-09-04", "10:16:00")
    # the entry was created in UTC: the visit is on the wall clock of its location — unless the hour typed is asked for
    madrid = {"timezone": "Europe/Madrid", "ignore_dst": False}
    assert rules.when({"created_at": "2024-09-04T08:16:31.000Z"}, madrid) == ("2024-09-04", "10:16:31")
    assert rules.when({"created_at": "2024-09-04T08:16:31Z", "date": "2024-09-04", "time": "09:00"}, madrid, "hour") == ("2024-09-04", "09:00:00")
    with pytest.raises(rules.RowError) as wrong:
        rules.when({"date": "2024-13-01", "time": "10:00"}, {})
    assert wrong.value.code == "date_invalid"


def test_the_columns_a_file_needs():
    table = [["Site", "Fecha", "Hora", "Accion"], ["DONA_01", "2024-09-04", "10:00", "I"]]
    mapping = rules.suggest(table[0])
    assert mapping == {"location_id": "Site", "date": "Fecha", "time": "Hora", "actions": "Accion"}
    _, rows = rules.rows_of(table, mapping, {"sd": "A1"})
    assert rows == [{"sd": "A1", "location_id": "DONA_01", "date": "2024-09-04", "time": "10:00", "actions": "I"}]
    # creating the locations asks for their own coordinates, timezone and summer time: a file without them is refused, saying what it lacks
    with pytest.raises(VisitsFailed, match="no column for: location_latitude, location_longitude, timezone, daylight_saving"):
        rules.rows_of(table, mapping, create={"locations": True})


def test_what_a_file_creates_and_archives():
    assert rules.username_of("Ana Pérez", {"ana.perez"}) == "ana.perez2"
    fields = rules.location_fields("NEW_1", {"location_latitude": "37", "location_longitude": "-6", "timezone": "UTC", "daylight_saving": "no"})
    assert fields["ignore_dst"] is True and fields["status"] == "pending"
    archived = rules.archived_by([{"location_id": "A"}], [{"location_id": "a", "date": "2024-09-04", "actions": ["Archive"]}])
    assert archived == [{"location_id": "A", "status": "archived", "status_date": "2024-09-04"}]
    assert rules.export_rows([{"actions": ["Installation", "Revision"], "bait_use": True, "date": "2024-09-04"}])[1][rules.EXPORT_FIELDS.index("actions")] == "Installation+Revision"
