"""#248: a plug (shared.plugs) stands for what is plugged into it, says so when nothing is, and is not patched itself."""
import pytest

from wildintel_uploader.shared.plugs import NotPlugged, Plug


class Shelf:
    size = 3

    def __call__(self, n: int) -> int:
        return n * 2


def test_a_plug_is_what_is_plugged_into_it():
    plug: Plug[Shelf] = Plug("a shelf")
    with pytest.raises(NotPlugged, match="Nothing is plugged into a shelf"):
        plug(1)
    plug.plug(Shelf())
    assert (plug(2), plug.size, plug.plugged) == (4, 3, True)


def test_a_plug_is_not_patched_what_is_plugged_into_it_is():
    plug: Plug[Shelf] = Plug("a shelf")
    plug.plug(Shelf())
    with pytest.raises(AttributeError, match="patch what is plugged"):
        plug.size = 4
