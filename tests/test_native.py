import ctypes
import sys

import pytest

from casca import native


def test_input_struct_matches_the_windows_x64_layout():
    assert ctypes.sizeof(native.INPUT) == 40


@pytest.mark.skipif(sys.platform != "win32", reason="SendInput is Windows only")
def test_mouse_move_lands_where_asked():
    native.win_move(100, 120)
    point = (ctypes.c_long * 2)()
    ctypes.windll.user32.GetCursorPos(point)
    assert tuple(point) == (100, 120)
