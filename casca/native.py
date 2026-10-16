"""Input PyAutoGUI gets wrong: Unicode text on macOS and Windows, which it maps to physical keys
and drops when there is none, and the mouse on Windows, which it normalises to the primary
monitor so clicks on any other monitor land in the wrong place."""
import ctypes
import sys
import time

u16, u32, i32 = ctypes.c_uint16, ctypes.c_uint32, ctypes.c_int32


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", i32), ("dy", i32), ("mouseData", u32), ("dwFlags", u32), ("time", u32),
                ("dwExtraInfo", ctypes.c_size_t)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", u16), ("wScan", u16), ("dwFlags", u32), ("time", u32), ("dwExtraInfo", ctypes.c_size_t)]


class INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]
    _anonymous_ = ("u",)
    _fields_ = [("type", u32), ("u", _U)]


MOVE, ABSOLUTE, VIRTUALDESK = 0x1, 0x8000, 0x4000
BUTTONS = {"left": (0x2, 0x4), "right": (0x8, 0x10)}
KEYEVENTF_UNICODE, KEYEVENTF_KEYUP = 0x4, 0x2


def _send(*events: INPUT) -> None:
    array = (INPUT * len(events))(*events)
    if ctypes.windll.user32.SendInput(len(events), array, ctypes.sizeof(INPUT)) != len(events):
        raise OSError("Windows blocked the input, possibly because an administrator window has focus")


def _mouse(x: int, y: int, flags: int = 0) -> INPUT:
    metric = ctypes.windll.user32.GetSystemMetrics
    left, top, width, height = (metric(i) for i in (76, 77, 78, 79))  # the virtual screen
    dx, dy = round((x - left) * 65535 / (width - 1)), round((y - top) * 65535 / (height - 1))
    return INPUT(type=0, mi=MOUSEINPUT(dx=dx, dy=dy, dwFlags=MOVE | ABSOLUTE | VIRTUALDESK | flags))


def win_move(x: int, y: int) -> None:
    _send(_mouse(x, y))


def win_click(x: int, y: int, button: str = "left", count: int = 1) -> None:
    down, up = BUTTONS[button]
    _send(_mouse(x, y), *[_mouse(x, y, f) for _ in range(count) for f in (down, up)])


def win_drag(x1: int, y1: int, x2: int, y2: int, duration: float) -> None:
    down, up = BUTTONS["left"]
    _send(_mouse(x1, y1), _mouse(x1, y1, down))
    for i in range(1, 11):
        time.sleep(duration / 10)
        _send(_mouse(x1 + (x2 - x1) * i // 10, y1 + (y2 - y1) * i // 10))
    _send(_mouse(x2, y2, up))


def _type_macos(text: str) -> None:
    import Quartz

    for char in text:
        for down in (True, False):
            event = Quartz.CGEventCreateKeyboardEvent(None, 0, down)
            Quartz.CGEventKeyboardSetUnicodeString(event, len(char.encode("utf-16-le")) // 2, char)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)


def _type_windows(text: str) -> None:
    units = text.encode("utf-16-le")
    codes = [int.from_bytes(units[i:i + 2], "little") for i in range(0, len(units), 2)]
    _send(*[INPUT(type=1, ki=KEYBDINPUT(wScan=c, dwFlags=KEYEVENTF_UNICODE | up))
            for c in codes for up in (0, KEYEVENTF_KEYUP)])


def type_unicode(text: str) -> None:
    if sys.platform == "darwin":
        _type_macos(text)
    elif sys.platform == "win32":
        _type_windows(text)
    else:
        raise ValueError("typing non-ASCII text is not supported on this platform yet")


def win_foreground_elevated() -> bool:
    """Windows drops input sent to an administrator window from a normal process (UIPI)."""
    user32, kernel32, advapi32 = ctypes.windll.user32, ctypes.windll.kernel32, ctypes.windll.advapi32
    if ctypes.windll.shell32.IsUserAnAdmin():
        return False
    user32.GetForegroundWindow.restype = kernel32.OpenProcess.restype = ctypes.c_void_p
    pid = u32()
    user32.GetWindowThreadProcessId(ctypes.c_void_p(user32.GetForegroundWindow()), ctypes.byref(pid))
    process = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    token, elevated, size = ctypes.c_void_p(), u32(), u32()
    try:
        # A normal process is refused the token of an elevated one.
        if not process or not advapi32.OpenProcessToken(ctypes.c_void_p(process), 0x8, ctypes.byref(token)):
            return True
        advapi32.GetTokenInformation(token, 20, ctypes.byref(elevated), 4, ctypes.byref(size))  # TokenElevation
        return bool(elevated.value)
    finally:
        kernel32.CloseHandle(token)
        kernel32.CloseHandle(ctypes.c_void_p(process))
