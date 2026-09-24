# Casca

A screenshot-driven desktop agent for studying visual grounding and
computer-use loops. Each step takes a screenshot, asks a vision model for one
typed action, validates it, executes it with the mouse and keyboard, and logs
everything.

```text
observe (screenshot) → propose (one JSON action) → validate → execute → log → repeat
```

It's a harness for experiments, not a polished operator: the value is in the
typed actions, dry runs, and complete logs that make failures easy to inspect.

## What it does

- Captures the screen as the model's only observation
- Asks the model for exactly one action: click, double/right click, move, drag,
  type, key press, hotkey, scroll, wait, done, or fail
- Parses actions into Pydantic models instead of loose strings
- `--dry-run` proposes actions without executing them; `--confirm-each-step`
  asks before each one
- Saves every step's screenshot, raw model output, and result under `logs/`
- `casca web` opens a small Flask viewer for replaying past runs

## Install

Python 3.10+.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env    # then add your Hugging Face token
```

`.env` sets the model (`HF_MODEL_ID`, default `google/gemma-4-31b-it`), the
step limit, which monitor to capture, and the screenshot width sent to the
model.

## macOS setup

macOS won't let a program see or control the screen until you grant it
permission. Casca runs inside your terminal, so the permission goes to the
terminal app (Terminal, iTerm, Ghostty, VS Code, and so on):

1. **System Settings → Privacy & Security → Screen Recording**: enable your
   terminal. Without this, screenshots come back as a flat, empty frame
   and Casca doesn't warn you: the model is handed a blank screen.
2. **System Settings → Privacy & Security → Accessibility**: enable your
   terminal. Without this, clicks and key presses are silently dropped.
3. Quit and reopen the terminal after changing either setting.

Check with a dry run and open the saved screenshot:

```bash
casca run "Open Calculator" --provider mock --dry-run --max-steps 3
open logs/run_*/screenshots/step_000.png
```

If the image shows your windows, capture works. Keyboard shortcuts on macOS
use `command`, not `ctrl` (for example `["command", "space"]` for Spotlight).
The prompt's examples still use `ctrl`, so a model may need telling.

## Usage

```bash
# Safe first run: mock model, nothing executed
casca run "Open Calculator" --provider mock --dry-run

# Real model, confirm every action before it happens
casca run "Open TextEdit and type hello world" --max-steps 10 --confirm-each-step

# Browse past runs
casca web
```

Move the mouse into a screen corner to abort a run (PyAutoGUI's fail-safe).

## Known issues

Found while testing on a MacBook (1470×956 display):

- **Click coordinates are off by the resize factor.** Screenshots are shrunk
  to `CASCA_SCREENSHOT_MAX_WIDTH` (1280 px) before the model sees them, but the
  prompt gives the real screen size and coordinates are never scaled back. On
  a 1470-wide screen clicks land about 15% off; on a 1920-wide Windows screen,
  about 50%. Until this is fixed, set `CASCA_SCREENSHOT_MAX_WIDTH` to your
  screen width.
- **Per-action safety is a stub.** The only active check scans the *task text*
  for keywords (`password`, `delete`, `buy`, `bank`, ...) and refuses unless
  `--unsafe` is passed. `SafetyPolicy.check_action` currently approves every
  action, so use `--dry-run` or `--confirm-each-step` for anything real.
- **Blank screenshots aren't detected** (see the macOS setup above).
- `examples/tasks.yaml` still uses Windows apps (Notepad, File Explorer).

## Repo layout

```text
casca/            agent loop, actions, safety, screen capture, providers
casca/models/     Hugging Face and mock providers
web/              Flask replay viewer
examples/         sample tasks
logs/             run output (one folder per run)
```

## License

MIT
