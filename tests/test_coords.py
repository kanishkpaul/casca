import pytest

from casca.actions import ClickAction, DragAction
from casca.coords import to_screen

RETINA = {"left": 0, "top": 0, "width": 1470, "height": 956}


def click(x, y):
    return ClickAction(action="click", x=x, y=y, reason="r")


def test_screenshot_pixels_map_to_points_on_a_resized_retina_capture():
    moved = to_screen(click(640, 416), (1280, 832), RETINA)
    assert (moved.x, moved.y) == (735, 478)


def test_second_monitor_offset_is_added():
    right = {"left": 1470, "top": -200, "width": 1920, "height": 1080}
    moved = to_screen(click(0, 0), (1280, 720), right)
    assert (moved.x, moved.y) == (1470, -200)


def test_drag_maps_both_ends():
    drag = DragAction(action="drag", x1=0, y1=0, x2=1279, y2=831, reason="r")
    moved = to_screen(drag, (1280, 832), RETINA)
    assert (moved.x1, moved.y1, moved.x2, moved.y2) == (0, 0, 1469, 955)


def test_point_outside_the_screenshot_is_refused_not_clamped():
    with pytest.raises(ValueError, match="outside"):
        to_screen(click(1300, 10), (1280, 832), RETINA)
