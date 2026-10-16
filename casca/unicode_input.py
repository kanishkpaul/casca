"""Types text as Unicode characters, which PyAutoGUI cannot: it maps characters to physical
keys and drops anything without one, such as "é" or "日本"."""
import sys


def _type_macos(text: str) -> None:
    import Quartz

    for char in text:
        for down in (True, False):
            event = Quartz.CGEventCreateKeyboardEvent(None, 0, down)
            Quartz.CGEventKeyboardSetUnicodeString(event, len(char.encode("utf-16-le")) // 2, char)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)


def _type_windows(text: str) -> None:
    import ctypes
    from ctypes import wintypes

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

    class INPUT(ctypes.Structure):
        # The union is padded to MOUSEINPUT's size, the largest member, so sizeof matches the OS.
        class _U(ctypes.Union):
            _fields_ = [("ki", KEYBDINPUT), ("pad", ctypes.c_byte * 32)]
        _anonymous_ = ("u",)
        _fields_ = [("type", wintypes.DWORD), ("u", _U)]

    KEYEVENTF_UNICODE, KEYEVENTF_KEYUP, INPUT_KEYBOARD = 0x4, 0x2, 1
    units = text.encode("utf-16-le")
    for i in range(0, len(units), 2):
        code = int.from_bytes(units[i:i + 2], "little")
        for flags in (KEYEVENTF_UNICODE, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP):
            event = INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(wScan=code, dwFlags=flags))
            if not ctypes.windll.user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(INPUT)):
                raise OSError("SendInput blocked, possibly by an administrator window")


def type_unicode(text: str) -> None:
    if sys.platform == "darwin":
        _type_macos(text)
    elif sys.platform == "win32":
        _type_windows(text)
    else:
        raise ValueError("typing non-ASCII text is not supported on this platform yet")
