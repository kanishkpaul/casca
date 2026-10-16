# Plan: Casca on macOS and Windows

Scope: the Python code on `main`. The goal is one codebase that captures, maps coordinates,
types and clicks correctly on macOS 14+ and Windows 11, and says plainly what it cannot do on
each. Linux is out of scope here and stays possible later.

This plan borrows the shape of the Rust plan on the local `new` branch (`docs/ARCHITECTURE.md`,
`docs/BUILD_PLAN.md` Phase 0 and Phase 4, `docs/SAFETY.md`): one `Desktop` interface with one
implementation per OS, one coordinate module, a `fake` platform for tests, and `casca doctor`
as the proof on each machine. It does not port the Rust crates. It assumes `BUGFIX_PLAN.md`
Phases 0 and 1 are done, because this work needs the fake harness and a loop that records
failures.

## What is wrong today, per OS

Each item was read from the code on `main` and from the installed library source
(pyautogui 0.9.54, mss 10.2.0). None was run on Windows.

| Area | macOS | Windows |
|---|---|---|
| Capture size | `mss` returns physical pixels (2940 x 1912 on this Retina screen) while the monitor is 1470 x 956 points | Depends on which library sets DPI awareness first (below) |
| DPI awareness | Not applicable | `pyautogui` calls `SetProcessDPIAware()` (system aware) on import. `mss` calls `SetProcessDpiAwareness(2)` (per-monitor) later. A process can set it once, so the order of imports decides, and on a mixed-scale setup capture and input disagree |
| Mouse | Points, global coordinates, multi-monitor works | `mouse_event` coordinates are normalised to the primary screen (`65536 * x // width`), so clicks on any other monitor land wrong |
| Keys | `ctrl` in the prompt is the wrong modifier; `command` is right | `ctrl` is right; `win` exists |
| Unicode text | Dropped silently (no mapping in `_pyautogui_osx.keyboardMapping`) | `keybd_event` with virtual keys only, so non-ASCII is dropped too |
| Scroll | Lines, so `-650` is 650 lines | Wheel delta, so `-650` is about 5 notches |
| Permissions | Screen Recording and Accessibility attach to the terminal app, and a missing grant gives a blank frame and silently ignored input | None for ordinary windows. Input to an elevated window is dropped silently (UIPI). The UAC prompt is on a secure desktop and captures as black |
| Logs | Relative `logs/` | Same, plus backslash paths in the viewer's URLs |
| Console | UTF-8 | Legacy console code pages can turn `⬡ ┊ ❯` into `?` |

## Target shape

```
casca/
  platform/
    __init__.py      get_desktop(): picks by sys.platform, or "fake" from CASCA_PLATFORM
    base.py          Desktop protocol, Display, Frame, Capabilities, PlatformError
    coords.py        the only place coordinates are converted
    macos.py         Quartz and ApplicationServices through pyobjc
    windows.py       ctypes: SendInput, DPI awareness, UIPI and UAC checks
    fake.py          scripted frames and recorded input, for tests
```

```python
class Desktop(Protocol):
    def displays(self) -> list[Display]: ...
    def capture(self, display: Display) -> Frame: ...      # Frame carries its geometry
    def move(self, p: ScreenPoint) -> None: ...
    def button(self, button: Button, down: bool) -> None: ...
    def scroll(self, notches: int) -> None: ...
    def key(self, key: Key, down: bool) -> None: ...
    def text(self, value: str) -> None: ...                 # Unicode, no clipboard
    def cursor(self) -> ScreenPoint: ...
    def capabilities(self) -> Capabilities: ...
    def permissions(self) -> Permissions: ...
```

`DesktopController` becomes a thin layer that turns validated actions into these calls. PyAutoGUI
leaves the input path. It may stay for its fail-safe corner until the stop hotkey lands (see
`COMPUTER_USE.md`).

Why drop PyAutoGUI for input: three of the defects above (multi-monitor on Windows, Unicode on
both, silent unknown keys) are inside it, and its Windows mouse path is `mouse_event`, which its
own source marks as superseded. Rejected: patching around it with the clipboard for text, which
overwrites the user's clipboard and is visible to other apps; and switching to `pynput` for
input, which is a dependency for what is about 150 lines of `ctypes` or pyobjc per OS, and has
not been checked against the multi-monitor and Unicode cases here.

## Tasks

Ids continue the Rust plan's style so branches read the same: `xp-01`.

| Id | Task | Done when |
|---|---|---|
| xp-01 | **Spike on both OSes.** A script, not product code, that prints: display list with origins and scale; capture size per display; cursor position after moving to each display's centre; whether a Unicode string round-trips into a text field; scroll distance for 1 notch; on Windows the DPI awareness in effect and whether an elevated Notepad receives input | The printed output for this Mac and one Windows 11 machine with two monitors at different scales, pasted into `docs/DECISIONS.md` on `main` with the command |
| xp-02 | **Platform package and `fake`.** The protocol, the dataclasses, `get_desktop()`, and a fake that records calls | The agent's end-to-end test from `BUGFIX_PLAN.md` Phase 0 runs on the fake on both OSes in CI |
| xp-03 | **Coordinates.** `ImagePx -> ScreenPoint` and back, from each frame's geometry: image size, captured pixel size, logical size, origin. Supports `image_px` and `norm1000` model conventions | Property tests round-trip on synthetic geometries: Retina 2x, Windows 125 % and 150 %, a monitor at negative x |
| xp-04 | **macOS platform.** Capture with `mss` and the backing scale from `NSScreen`. Input with `CGEventCreateMouseEvent`, `CGEventCreateScrollWheelEvent` in pixel units, `CGEventKeyboardSetUnicodeString` for text. Permissions from `CGPreflightScreenCaptureAccess` and `AXIsProcessTrusted` | Clicks on a test page with numbered boxes land within 2 points on the built-in display and an external one, measured and recorded |
| xp-05 | **Windows platform.** Set per-monitor DPI awareness v2 first thing in `casca/__init__.py` on Windows, before any other import. Input with `SendInput`: `MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK` against the virtual screen, `KEYEVENTF_UNICODE` for text, wheel delta 120 per notch. Capture with `mss` | The same test page on two monitors at different scales, within 2 pixels, recorded |
| xp-06 | **Windows realities.** Before each act, check whether the foreground window's process is elevated while Casca is not, and refuse with "Casca cannot act in an administrator window. Run the task without it, or start Casca as administrator." A frame that is near-black right after an act is treated as a possible UAC prompt and handed back | Both shown in a trace on Windows 11 |
| xp-07 | **Keys per OS.** One key table with the names the model may use (`enter`, `tab`, `cmd`, `ctrl`, `alt`, `shift`, arrows, function keys) mapped per OS. `cmd` on Windows maps to `ctrl`. The prompt names the OS and its modifier | An unknown key is rejected before execution with the list of valid names, on both OSes |
| xp-08 | **Permissions and `casca doctor`.** One row per check: capture granted and not blank, input permitted, cursor round trip on each display, scale per display, DPI awareness on Windows, console encoding, model endpoint reachable. Each failure prints the fix. On macOS that names the app that needs the grant (Terminal, iTerm, VS Code) because the grant attaches to it | On this Mac with Screen Recording revoked for the terminal, doctor says so and how to fix it |
| xp-09 | **Paths and packaging.** Logs under `platformdirs.user_data_dir("casca")`. The viewer packaged inside `casca/` (B23). Viewer URLs built with `/` regardless of OS | `pip install` of the wheel into a fresh venv on both OSes, then `casca web` from the home directory lists runs |
| xp-10 | **Console encoding.** If stdout cannot encode `⬡ ┊ ❯ ─`, fall back to `* | > -`. On Windows, enable virtual terminal processing for colour | `casca run --dry-run` in Windows Terminal and in legacy `conhost` both render without `?` |
| xp-11 | **Example tasks per OS.** `examples/macos.yaml` (TextEdit, Calculator, Safari, Finder) and `examples/windows.yaml` (Notepad, Calculator, Edge, File Explorer). Remove the shared file | Each file's tasks run in dry run on its OS |
| xp-12 | **CI.** GitHub Actions on `macos-latest` and `windows-latest`: tests on the fake platform, wheel build and install. Real input in CI only if the spike shows the runner can do it | Green on both. A skipped test fails the job |

## Dependencies

| Package | OS | Why | Status |
|---|---|---|---|
| `pyobjc-framework-Quartz` | macOS | Events and display scale | Already installed through PyAutoGUI; make it direct |
| `pyobjc-framework-ApplicationServices` | macOS | `AXIsProcessTrusted`, and the hit test in `COMPUTER_USE.md` | New |
| `ctypes` | Windows | `SendInput`, DPI, token elevation | Standard library |
| `platformdirs` | both | Log and config paths | Already listed, unused |

Pin lower and upper bounds for each (B22).

## Order and gate

xp-01, then xp-02 and xp-03 together, then xp-04 and xp-05 in parallel, then xp-06 to xp-12.

**Gate:** the numbered-box test page passes on this Mac (built-in and external display) and on
one Windows 11 machine (two monitors, different scales), with the pixel error per box recorded,
and `casca doctor` is green on both.

## Not verified

- Every Windows statement above comes from reading PyAutoGUI 0.9.54 and mss 10.2.0 source on this
  Mac. xp-01 is the first time any of it runs on Windows.
- Whether GitHub's hosted runners can send real input and capture a desktop is unknown until
  xp-01 and xp-12.
