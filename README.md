# Casca

A screenshot-driven desktop agent. Each step takes a screenshot, asks a vision model for one typed
action, checks it, executes it with the mouse and keyboard, and records everything.

```text
observe (screenshot) → propose (one JSON action) → check → execute → record → repeat
```

It runs on any model you choose: a hosted provider with your own key, or a local model through
Ollama, LM Studio, llama.cpp or vLLM. It targets macOS and Windows. It is a harness for
experiments, not an operator you should point at real accounts yet.

## What it does

- Captures one monitor and maps the model's screenshot pixels back to screen points, including
  Retina scaling and the monitor's origin.
- Asks for exactly one action: click, double or right click, move, drag, type, key press, hotkey,
  scroll, wait, done or fail. Replies are parsed strictly; a bad one is retried twice with the
  validation error.
- Refuses out-of-range coordinates, unknown keys, quit and delete shortcuts, and text that looks
  like an API key or card number. Types non-ASCII text as Unicode.
- Stops before the first model call if the screen cannot be captured.
- `--dry-run` proposes without executing. `--confirm-each-step` asks before each action.
- Records every step's screenshot, raw reply, checks and result, and each run's outcome.
- `casca web` opens a viewer for past runs.

## Install

Python 3.10 or later. Tested on 3.14.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

## Choose a model

Casca talks to any OpenAI-compatible `/chat/completions` endpoint that accepts images. Set it in
`.env` or per run:

```bash
# Hosted, your own key
CASCA_BASE_URL=https://openrouter.ai/api/v1 CASCA_MODEL=<model> CASCA_API_KEY=<key> casca run "..."

# Local, no key
casca run "Open TextEdit and type hello" --base-url http://localhost:11434/v1 --model qwen3-vl:8b
```

The default is the Hugging Face router with `google/gemma-4-31b-it`, which needs a key in
`CASCA_API_KEY` (or the older `HF_API_TOKEN`).

## macOS setup

macOS will not let a program see or control the screen until you grant it. Casca runs inside your
terminal, so the grant goes to the terminal app (Terminal, iTerm, Ghostty, VS Code):

1. **System Settings → Privacy & Security → Screen Recording:** enable your terminal. Without it,
   Casca stops and says so.
2. **System Settings → Privacy & Security → Accessibility:** enable your terminal. Without it,
   clicks and key presses are dropped.
3. Quit and reopen the terminal after changing either.

## Usage

```bash
casca run "Open Calculator" --provider mock --dry-run      # mock model, nothing executed
casca run "Open TextEdit and type hello" --confirm-each-step
casca web                                                  # browse past runs
pytest -q                                                  # tests, on fakes only
```

Runs are stored in the OS data directory (`~/Library/Application Support/casca/logs` on macOS),
or `CASCA_LOG_DIR`. Move the mouse into a screen corner, or press Ctrl-C, to stop a run.

## Tested

On 2026-10-16, on a MacBook (M5, 16 GB, macOS 27), with Qwen3-VL 8B Instruct Q4_K_M served
locally by llama.cpp:

```bash
llama-server -m Qwen3VL-8B-Instruct-Q4_K_M.gguf --mmproj mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf --port 8080
casca run "Open TextEdit, create a new document and type hello" \
  --base-url http://127.0.0.1:8080/v1 --model qwen3-vl-8b --coords norm1000 --confirm-each-step
```

TextEdit was already running with its Open panel showing. The run clicked New Document, typed
"hello" and reported done in 3 steps and 22 s, and the document showed "hello". The click landed on
the New Document icon, about 18 px right of its centre in the 1280 px screenshot. In earlier attempts the model also
clicked in the wrong app and proposed clicking "Allow" on a macOS permission prompt, which is
why `--confirm-each-step` matters until the gates in plans/COMPUTER_USE.md exist.

## What is not verified

- Scrolling and non-ASCII typing on the real desktop. The tests use a fake desktop.
- Anything on Windows. The Windows code paths were written from the library sources.
- Any hosted provider since the provider was rewritten.
- Clicks on a Windows monitor other than the primary are still wrong: PyAutoGUI normalises mouse
  coordinates to the primary screen.

## Plans

| Plan | What it covers |
|---|---|
| [plans/BUGFIX_PLAN.md](plans/BUGFIX_PLAN.md) | The 31 bugs found on 2026-10-16 and their order |
| [plans/CROSS_PLATFORM.md](plans/CROSS_PLATFORM.md) | One `Desktop` interface for macOS and Windows |
| [plans/COMPUTER_USE.md](plans/COMPUTER_USE.md) | The minimal additions for a usable computer-use agent |
| [plans/TUI.md](plans/TUI.md) | The terminal interface, drawn in [plans/tui-mockups.html](plans/tui-mockups.html) |
| [TODO.md](TODO.md) | The MVP checklist |

## Layout

```text
casca/            agent loop, actions, coordinates, safety, screen capture, input
casca/models/     OpenAI-compatible and mock providers
casca/web/        replay viewer
tests/            tests on a fake screen and desktop
plans/            plans and design mockups
```
