import os.path
import pytest

from awscatalyst import util


class SomeException(Exception):
    pass


def test_tempdir_instantiated():
    td = util.tempdir(base_path="/tmp")
    assert td.base_path

    with pytest.raises(AttributeError):
        print(td.path)

    assert td.cleanup() or True, "Cleaning up unused tempdir should not raise exceptions"


def test_tempdir():
    with util.tempdir() as td:
        assert td.base_path
        assert td.path
        assert td.base_path in td.path, "Temp dir should be a subfolder in base_path"
        assert os.path.isdir(td.path), "Temp dir should be created"

    assert not os.path.isdir(td.path), "Temp dir should be deleted after leaving function"

    try:
        with util.tempdir() as td:
            assert os.path.isdir(td.path), "Temp dir should be created"
            raise SomeException()
    except SomeException:
        assert not os.path.isdir(td.path), "Temp dir should be deleted on Exception"


def test_tempdir_no_cleanup():
    with util.tempdir(cleanup=False) as td:
        assert td.base_path in td.path, "Temp dir should be a sub-folder in base_path"
        assert os.path.isdir(td.path), "Temp dir should be created"

    assert os.path.isdir(td.path), "Temp dir should stay there after leaving function"
