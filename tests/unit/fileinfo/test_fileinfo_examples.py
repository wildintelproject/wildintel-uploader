"""The examples of how the metadata of an image are understood (fileinfo.domain.models) hold."""
import doctest

from wildintel_uploader.modules.fileinfo.domain import models


def test_the_examples_of_the_models_hold():
    result = doctest.testmod(models)
    assert result.attempted > 0 and result.failed == 0
