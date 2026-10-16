from casca.actions import BaseAction

POINT_FIELDS = ("x", "y", "x1", "y1", "x2", "y2")


def to_screen(action: BaseAction, image_size: tuple[int, int], monitor: dict) -> BaseAction:
    """Maps a point the model gave in screenshot pixels to global screen coordinates.

    The screenshot is resized (and on Retina captured at 2x), so its pixels are not the
    coordinates the OS input APIs take. Raises ValueError for a point outside the image.
    """
    update = {}
    for name, value in action.model_dump().items():
        if name not in POINT_FIELDS:
            continue
        horizontal = name.startswith("x")
        limit = image_size[0 if horizontal else 1]
        if value >= limit:
            raise ValueError(f"{name}={value} is outside the {image_size[0]}x{image_size[1]} screenshot")
        size, origin = ("width", "left") if horizontal else ("height", "top")
        update[name] = monitor[origin] + round(value * monitor[size] / limit)
    return action.model_copy(update=update)
