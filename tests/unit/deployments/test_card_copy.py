"""Copying a memory card to a temporary folder."""
import json
import os
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.support import built
from wildintel_uploader.modules.deployments.domain.cards import CardCopyError
from wildintel_uploader.modules.deployments.infrastructure.memory_cards import base_dir
from wildintel_uploader.modules.deployments.infrastructure import memory_cards
from wildintel_uploader.web.main import app


@pytest.fixture(autouse=True)
def _temp(tmp_path, monkeypatch):
    monkeypatch.setattr(memory_cards.tempfile, "gettempdir", lambda: str(tmp_path / "temp"))
    (tmp_path / "temp").mkdir()


def _card(tmp_path: Path) -> Path:
    card = tmp_path / "CARD_A"
    (card / "DCIM" / "100").mkdir(parents=True, exist_ok=True)
    (card / "DCIM" / "100" / "IMG_0001.JPG").write_bytes(b"a" * 10)
    (card / "DCIM" / "100" / "IMG_0002.JPG").write_bytes(b"b" * 20)
    return card


def test_a_card_is_copied_to_a_temporary_folder_named_like_it_and_reports_its_progress(tmp_path: Path):
    card = _card(tmp_path)
    events = list(built.card_copying().copy(str(card)))

    assert events[0] == {"type": "start", "files": 2, "bytes": 30}
    assert [e["copied"] for e in events if e["type"] == "progress"] == [1, 2]
    done = events[-1]
    assert done["type"] == "done" and Path(done["path"]).name == "CARD_A" and done["files"] == 2
    assert (Path(done["path"]) / "DCIM" / "100" / "IMG_0002.JPG").read_bytes() == b"b" * 20
    assert (card / "DCIM" / "100" / "IMG_0001.JPG").exists()   # the card is only read


def test_a_card_is_not_copied_when_the_temporary_folder_has_no_room_for_it(tmp_path: Path, monkeypatch):
    """#212: the copy goes to the temporary folder of the system; with no room for the whole card, it is said before anything is copied."""
    from wildintel_uploader.modules.deployments.infrastructure import disk_space
    card = _card(tmp_path)
    monkeypatch.setattr(disk_space, "free_bytes", lambda path: 12)   # 30 bytes on the card

    with pytest.raises(CardCopyError) as refused:
        list(built.card_copying().copy(str(card)))

    assert "The SD card needs 30 bytes and the temporary folder of the system" in str(refused.value) and "has 12 bytes free" in str(refused.value)
    assert not any((tmp_path / "temp").rglob("*.JPG"))   # nothing was copied


def test_a_card_that_is_not_there_or_is_empty_is_refused(tmp_path: Path):
    (tmp_path / "EMPTY").mkdir()
    with pytest.raises(CardCopyError, match="not a folder"):
        list(built.card_copying().copy(str(tmp_path / "nowhere")))
    with pytest.raises(CardCopyError, match="nothing on the SD card"):
        list(built.card_copying().copy(str(tmp_path / "EMPTY")))


def test_a_copy_is_discarded_but_nothing_else_is(tmp_path: Path):
    done = list(built.card_copying().copy(str(_card(tmp_path))))[-1]
    outside = tmp_path / "keep"
    outside.mkdir()

    assert built.card_copying().discard(str(outside)) is False and outside.exists()      # not a copy of a card
    assert built.card_copying().discard(done["path"]) is True and not Path(done["path"]).exists()
    assert not any(base_dir().iterdir())                             # the folder that held it is gone too


def test_the_copies_left_behind_for_a_day_are_removed_when_a_card_is_copied(tmp_path: Path):
    old = list(built.card_copying().copy(str(_card(tmp_path))))[-1]
    holder = Path(old["path"]).parent
    long_ago = time.time() - 3 * 24 * 3600
    os.utime(holder, (long_ago, long_ago))

    new = list(built.card_copying().copy(str(_card(tmp_path))))[-1]
    assert not holder.exists() and Path(new["path"]).exists()


def test_the_api_copies_a_card_as_a_stream_and_discards_the_copy(tmp_path: Path):
    client = TestClient(app)
    with client.stream("POST", "/api/deployment-import/copy-card", json={"path": str(_card(tmp_path))}) as response:
        events = [json.loads(line) for line in response.iter_lines() if line]
    done = events[-1]
    assert response.status_code == 200 and done["type"] == "done" and Path(done["path"]).is_dir()

    assert client.post("/api/deployment-import/discard-card-copy", json={"path": done["path"]}).json() == {"removed": True}
    assert client.post("/api/deployment-import/discard-card-copy", json={"path": str(tmp_path)}).json() == {"removed": False}

    with client.stream("POST", "/api/deployment-import/copy-card", json={"path": str(tmp_path / "nowhere")}) as response:
        failed = [json.loads(line) for line in response.iter_lines() if line]
    assert failed[-1]["type"] == "error" and "not a folder" in failed[-1]["detail"]


# ── ejecting the card ───────────────────────────────────────────────────────

class _Done:
    def __init__(self, stdout="", returncode=0, stderr=""):
        self.stdout, self.returncode, self.stderr = stdout, returncode, stderr


def _fake_linux(monkeypatch, answers: list, calls: list):
    """The system commands answer in order: findmnt, lsblk (parent disk), lsblk (flags), then udisksctl."""
    queue = iter(answers)
    monkeypatch.setattr(memory_cards.platform, "system", lambda: "Linux")
    monkeypatch.setattr(memory_cards, "_run", lambda command: (calls.append(command), next(queue, _Done()))[1])


def test_eject_unmounts_and_powers_off_a_removable_drive(tmp_path, monkeypatch):
    calls: list = []
    _fake_linux(monkeypatch, [_Done("/dev/sdb1 /run/media/me/CARD_A\n"), _Done("sdb\n"), _Done("1 1\n")], calls)
    result = built.card_copying().eject(str(tmp_path))
    assert result["ejected"] is True and "CARD_A" in result["message"]
    assert ["udisksctl", "unmount", "-b", "/dev/sdb1"] in calls and ["udisksctl", "power-off", "-b", "/dev/sdb"] in calls


def test_eject_leaves_a_fixed_disk_alone(tmp_path, monkeypatch):
    calls: list = []
    # lsblk answers PKNAME with a disk, then the flags "0 0" (not removable, not hotplug)
    answers = iter([_Done("/dev/nvme0n1p2 /\n"), _Done("nvme0n1\n"), _Done("0 0\n"), _Done("  HintSystem:  true\n")])
    monkeypatch.setattr(memory_cards.platform, "system", lambda: "Linux")
    monkeypatch.setattr(memory_cards, "_run", lambda command: (calls.append(command), next(answers))[1])
    result = built.card_copying().eject(str(tmp_path))
    assert result["ejected"] is False
    assert not any(c[:2] in (["udisksctl", "unmount"], ["udisksctl", "power-off"]) for c in calls)


def test_eject_says_why_it_could_not(tmp_path, monkeypatch):
    answers = iter([_Done("/dev/sdb1 /run/media/me/CARD_A\n"), _Done("sdb\n"), _Done("1 1\n"), _Done(returncode=1, stderr="target is busy")])
    monkeypatch.setattr(memory_cards.platform, "system", lambda: "Linux")
    monkeypatch.setattr(memory_cards, "_run", lambda command: next(answers))
    result = built.card_copying().eject(str(tmp_path))
    assert result["ejected"] is False and "busy" in result["message"]


def test_eject_endpoint(tmp_path, monkeypatch):
    monkeypatch.setattr(memory_cards.CardOnDisk, "eject", lambda self, path: {"ejected": True, "message": f"{path} ejected"})
    response = TestClient(app).post("/api/deployment-import/eject-card", json={"path": "/run/media/me/CARD_A"})
    assert response.status_code == 200 and response.json() == {"ejected": True, "message": "/run/media/me/CARD_A ejected"}


def test_eject_takes_the_reader_of_a_laptop_that_udisks_says_is_not_a_system_drive(tmp_path, monkeypatch):
    calls: list = []
    # lsblk says "0 0" for an mmcblk, but udisks knows the card is not a system drive
    _fake_linux(monkeypatch, [_Done("/dev/mmcblk0p1 /run/media/me/CARD_B\n"), _Done("mmcblk0\n"), _Done("0 0\n"), _Done("  HintSystem:  false\n")], calls)
    result = built.card_copying().eject(str(tmp_path))
    assert result["ejected"] is True
    assert ["udisksctl", "unmount", "-b", "/dev/mmcblk0p1"] in calls


# ── the use case over ports in memory ───────────────────────────────────────

class _Card:
    def files(self, card):
        return Path("/media/CARD_C"), [(Path("DCIM/1.JPG"), 10), (Path("DCIM/2.JPG"), 5)]

    def eject(self, card):
        return {"ejected": True, "message": card}


class _Copies:
    def __init__(self, fail_at=None, room=None):
        self.kept, self.copied, self.removed, self._fail_at, self._room = {}, [], [], fail_at, room

    def base(self):
        return Path("/tmp/wildintel-sd")

    def holders(self):
        return list(self.kept.items())

    def shortfall(self, needed):
        return None if self._room is None or self._room >= needed else "no room"

    def new_holder(self):
        holder = Path("/tmp/wildintel-sd/card-new")
        self.kept[holder] = 1e9
        return holder

    def copy(self, card, file, to):
        from wildintel_uploader.modules.deployments.domain.cards import not_copied
        if file.name == self._fail_at:
            raise not_copied("disk gone")
        self.copied.append(to / file)

    def remove(self, holder):
        self.removed.append(holder)
        return self.kept.pop(holder, None) is not None


def test_the_use_case_copies_cleans_the_leftovers_and_removes_a_failed_copy():
    from wildintel_uploader.modules.deployments.application.cards import CardCopying
    copies = _Copies()
    copies.kept[Path("/tmp/wildintel-sd/card-old")] = 0.0
    events = list(CardCopying(_Card(), copies, now=lambda: 1e9).copy("/media/CARD_C"))
    assert events[-1] == {"type": "done", "path": "/tmp/wildintel-sd/card-new/CARD_C", "files": 2, "bytes": 15}
    assert Path("/tmp/wildintel-sd/card-old") in copies.removed and len(copies.copied) == 2

    failing = _Copies(fail_at="2.JPG")
    with pytest.raises(CardCopyError, match="disk gone"):
        list(CardCopying(_Card(), failing).copy("/media/CARD_C"))
    assert failing.removed == [Path("/tmp/wildintel-sd/card-new")] and not failing.kept

    with pytest.raises(CardCopyError, match="no room"):
        list(CardCopying(_Card(), _Copies(room=3)).copy("/media/CARD_C"))


def test_the_use_case_discards_only_inside_the_folder_of_the_copies():
    from wildintel_uploader.modules.deployments.application.cards import CardCopying
    copies = _Copies()
    holder = copies.new_holder()
    cards = CardCopying(_Card(), copies)
    assert cards.discard("/home/me/photos") is False and cards.discard("/tmp/wildintel-sd") is False
    assert cards.discard(str(holder / "CARD_C" / "DCIM")) is True and copies.removed == [holder]
