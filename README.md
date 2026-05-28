# Casca

Casca is a model-agnostic, screenshot-based desktop-use scaffold for studying visual grounding, action reliability, and computer-use agents.

## Architecture
Casca treats computer use as a closed-loop perception-action problem. The agent receives pixels, predicts one bounded action, executes it on the desktop, observes the next state, and repeats. This makes it useful for studying visual grounding, UI action reliability, recovery behavior, safety boundaries, and model comparison across desktop-control tasks.

## Setup
1. Clone the repository
2. Run `pip install -e .`
3. Copy `.env.example` to `.env` and fill in your Hugging Face token.

## Usage
Run tasks from the CLI:
```bash
casca run "Open Notepad and type hello world" --max-steps 10 --confirm-each-step
```

## Logs and Replay
Replay your sessions using the built-in web viewer:
```bash
casca web
```

## Limitations
- This is not meant to beat production agents immediately.
- It is a clean experimental harness.
- The model is replaceable.
- The scaffold is the artifact.
