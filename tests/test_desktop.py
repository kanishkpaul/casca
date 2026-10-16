import sys

import pytest

from casca.desktop import valid_key


def test_unknown_key_is_rejected():
    with pytest.raises(ValueError, match="enterr"):
        valid_key("enterr")


def test_cmd_alias_follows_the_os():
    assert valid_key("Cmd") == ("command" if sys.platform == "darwin" else "ctrl")
