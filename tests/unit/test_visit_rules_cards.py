"""The SD card a visit leaves: archived (from its day), in another camera, collected by the same revision."""
from wildintel_uploader.core.services import visit_rules


def _v(**over):
    base = {"location_id": "DONA_01", "session": "R0001", "date": "2026-06-10", "time": "09:00:00", "actions": ["Installation"], "camera_id": "C1", "sd": "A1", "camera_status": None}
    return {**base, "when": f"{over.get('date', base['date'])}T{over.get('time', base['time'])}+00:00", **{k: v for k, v in base.items() if k not in over}, **over}


def _stamped(v):
    return {**v, "when": f"{v['date']}T{v['time']}"}


def test_an_archived_card_is_refused_from_its_day_not_before():
    cards = [{"label": "Z1", "status": "archived", "status_date": "2026-10-01", "archive_reason": "lost"}, {"label": "Z2", "status": "archived", "status_date": None}]
    after = _stamped(_v(date="2026-12-01", location_id="DONA_02", sd="Z1"))
    before = _stamped(_v(date="2026-09-30", location_id="DONA_02", sd="Z1"))
    assert "not available since 2026-10-01" in visit_rules.card_block([], after, cards)
    assert visit_rules.card_block([], before, cards) is None
    assert "it is archived" in visit_rules.card_block([], _stamped(_v(sd="Z2")), cards)
    assert "not available" in visit_rules.availability_errors([], after, cards)["sd"]


def test_a_card_collected_in_a_revision_is_not_left_again_in_that_revision():
    kept = [_stamped(_v(session="R0001", sd="A1")),
            _stamped(_v(session="R0002", date="2026-11-02", actions=["Revision"], sd="A2", num_photos=5))]  # A1 collected at DONA_01 in R0002
    moved = _stamped(_v(session="R0002", date="2026-11-03", location_id="DONA_02", camera_id="C2", sd="A1"))
    later = _stamped(_v(session="R0003", date="2026-11-03", location_id="DONA_02", camera_id="C2", sd="A1"))
    assert "collected at DONA_01 in this revision (R0002)" in visit_rules.card_block(kept, moved)
    assert visit_rules.card_block(kept, later) is None
