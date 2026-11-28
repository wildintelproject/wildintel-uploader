"""#248: what was read of a settings file is kept apart from how it is read (infrastructure.file_cache)."""
from pathlib import Path

from wildintel_uploader.modules.settings.infrastructure.file_cache import CachedReading


def _counting(tmp_path: Path):
    reads: list[Path] = []
    versions = {"v": 1}

    def reader(path: Path) -> dict:
        reads.append(path)
        return {"workers": len(reads)}
    return reads, versions, CachedReading(reader, lambda path: versions["v"])


def test_a_file_is_read_once_while_it_is_the_same(tmp_path: Path):
    reads, _, cache = _counting(tmp_path)
    assert cache.read(tmp_path / "a.toml") == cache.read(tmp_path / "a.toml") == {"workers": 1}
    assert len(reads) == 1


def test_a_file_is_read_again_when_it_changes_or_is_forgotten(tmp_path: Path):
    reads, versions, cache = _counting(tmp_path)
    cache.read(tmp_path / "a.toml")
    versions["v"] = 2
    assert cache.read(tmp_path / "a.toml") == {"workers": 2}
    cache.forget(tmp_path / "a.toml")
    assert cache.read(tmp_path / "a.toml") == {"workers": 3}


def test_what_is_given_is_a_copy(tmp_path: Path):
    _, _, cache = _counting(tmp_path)
    cache.read(tmp_path / "a.toml")["workers"] = 99
    assert cache.read(tmp_path / "a.toml") == {"workers": 1}
