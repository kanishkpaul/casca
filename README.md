# Casca v0.1 (Python prototype)

> **This branch is archived.** It holds the Python prototype of Casca, tagged `v0.1`. It is kept
> runnable as the baseline the Rust rebuild on [`main`](https://github.com/kanishkpaul/casca) has
> to beat. It gets no new features. Fixes land here only if they are needed to run the baseline.

A screenshot-driven desktop agent for studying visual grounding and computer-use loops. Each step
takes a screenshot, asks a vision model for one typed action, validates it, executes it with the
mouse and keyboard, and logs everything.

```text
observe (screenshot) → propose (one JSON action) → validate → execute → log → repeat
```

It is a harness for experiments, not an operator you should point at real accounts.

## What it does

- Captures one monitor as the model's only observation.
- Asks the model for exactly one action: click, double or right click, move, drag, type, key
  press, hotkey, scroll, wait, done or fail.
- Parses actions into Pydantic models instead of loose strings.
- `--dry-run` proposes actions without executing them. `--confirm-each-step` asks before each one.
- Saves every step's screenshot, raw model output and result under `logs/`.
- `casca web` opens a small Flask viewer for replaying past runs.

## Install

Python 3.10 or later. Tested on 3.14.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env    # then add your Hugging Face token
```

Install with `-e`. The packaged wheel leaves out `web/`, so `casca web` only works from an
editable install, with the virtual environment activated.

`.env` sets the model (`HF_MODEL_ID`, default `google/gemma-4-31b-it`), the step limit, the
monitor to capture and the screenshot width sent to the model.

## macOS setup

macOS will not let a program see or control the screen until you grant it permission. Casca runs
inside your terminal, so the grant goes to the terminal app (Terminal, iTerm, Ghostty, VS Code):

1. **System Settings → Privacy & Security → Screen Recording:** enable your terminal. Without it,
   screenshots come back blank and Casca does not warn you.
2. **System Settings → Privacy & Security → Accessibility:** enable your terminal. Without it,
   clicks and key presses are silently dropped.
3. Quit and reopen the terminal after changing either setting.

Check with a dry run and open the saved screenshot:

```bash
casca run "Open Calculator" --provider mock --dry-run --max-steps 3
open logs/run_*/screenshots/step_000.png
```

If the image shows your windows, capture works. Shortcuts on macOS use `command`, not `ctrl`.
The prompt's examples use `ctrl`, so a model may need telling.

## Usage

```bash
# Mock model, nothing executed
casca run "Open Calculator" --provider mock --dry-run

# Real model, confirm every action before it happens
casca run "Open TextEdit and type hello world" --max-steps 10 --confirm-each-step

# Browse past runs
casca web
```

Move the mouse into a screen corner to abort a run (PyAutoGUI's fail-safe).

## Known issues

Measured on 2026-10-13 on a MacBook with a 1470x956 display. None of these will be fixed here.
Each one shaped a decision in the rebuild.

- **Clicks land in the wrong place.** The model sees a screenshot shrunk to 1280 px wide, but the
  prompt gives the real screen size and coordinates are never scaled back. Clicks land at 87 % of
  the intended distance from the top-left corner on a 1470-wide screen, and at 67 % on a
  1920-wide one. Setting `CASCA_SCREENSHOT_MAX_WIDTH` to your screen width avoids it.
- **The model barely sees its own history.** It gets the action name and success or failure for
  the last five steps: no coordinates, no typed text, no reasons. It repeats itself.
- **The safety filter blocks harmless tasks and checks no actions.** It matches substrings of the
  task text, so "Find information about the weather" is refused ("information" contains "format")
  and so is "Check the bank holiday calendar". The per-action check approves everything. Use
  `--dry-run` or `--confirm-each-step` for anything real.
- **Some model outputs crash the run.** A `wait` with negative milliseconds passes validation and
  then raises. A 27-hour wait is accepted. Errors from PyAutoGUI, including its own fail-safe, end
  the run without logging the step.
- **Some failures are logged as success.** `typewrite` drops non-ASCII characters and `press`
  ignores unknown key names, and both report success.
- **A malformed reply ends the run.** There is no retry. Float coordinates, two JSON objects in
  one reply, or `done` without an `answer` all stop it.
- **Runs cannot be compared across models.** The run metadata records the provider class, not the
  model, and has no outcome, end time, screen size or scale factor.
- **Blank screenshots are not detected** (see the macOS setup above).
- **The default Hugging Face endpoint may be out of date.** It falls back to
  `api-inference.huggingface.co`. Not tested here. Set `HF_API_URL` if requests fail.
- `examples/tasks.yaml` uses Windows apps and is not read by any command.

On the same machine, one step spent about 50 ms on capture, resize and PNG encode, against 1 to
10 s waiting for the model. The prototype is slow because of the model and the number of steps,
not because it is written in Python.

## What the rebuild keeps and replaces

| Kept | Replaced |
|---|---|
| Typed actions | Coordinates first, by element numbers read from the accessibility tree |
| Dry runs and per-step confirmation | The keyword filter, by an envelope fixed before the screen is read, and gates on each act |
| One trace per run with every frame | Hugging Face only, by any hosted provider with your own key, or a local model |
| A replay viewer | One monitor on macOS, by macOS, Windows and Linux behind one trait |

The reasons are in [`docs/LESSONS.md`](https://github.com/kanishkpaul/casca/blob/main/docs/LESSONS.md)
and [`docs/DECISIONS.md`](https://github.com/kanishkpaul/casca/blob/main/docs/DECISIONS.md) on
`main`.

## Repo layout

```text
casca/            agent loop, actions, safety, screen capture, providers
casca/models/     Hugging Face and mock providers
web/              Flask replay viewer
examples/         sample tasks
logs/             run output, one folder per run
```

## License

MIT
