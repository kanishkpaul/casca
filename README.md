# Casca

Casca is a screenshot-based desktop agent scaffold for studying visual grounding, action reliability, and computer-use loops.

I built it as an experimental harness for desktop-use agents: take a screenshot, ask a model for one structured action, execute it, log the outcome, and repeat. The emphasis is on grounded interaction and inspectable runs, not pretending this is a polished general-purpose operator.

## What it does today

- Captures desktop screenshots as the model's observation stream
- Supports a model-backed Hugging Face provider and a mock provider
- Predicts one structured action at a time
- Executes mouse, keyboard, scroll, drag, wait, and terminal completion actions
- Logs metadata, screenshots, model output, safety decisions, and execution results
- Offers `--dry-run` and `--confirm-each-step` modes for safer iteration
- Ships with a small Flask web viewer for replaying past runs

## Why this project matters

Desktop-use agents are interesting because they force a model to deal with messy interfaces, partial observability, and action consequences.

Casca is the kind of repo I like building when I want to study:

- how well a model grounds actions in pixels
- how often action loops appear
- what logging is needed to debug failures
- where safety checks belong in a desktop-control stack

## Local setup

```bash
pip install -e .
```

Create a `.env` file using the values from `.env.example`:

```env
HF_API_TOKEN=hf_your_token_here
HF_MODEL_ID=google/gemma-4-31b-it
HF_API_URL=
CASCA_MAX_STEPS=20
CASCA_MONITOR=1
CASCA_SCREENSHOT_MAX_WIDTH=1280
CASCA_STEP_DELAY=0.5
```

## Usage

Run the agent:

```bash
casca run "Open Notepad and type hello world" --max-steps 10 --confirm-each-step
```

Dry-run without executing actions:

```bash
casca run "Open Calculator" --provider mock --dry-run
```

Open the replay viewer:

```bash
casca web
```

## Repo layout

```text
casca/            agent loop, actions, safety, logging, providers
web/              Flask replay viewer
examples/         sample task definitions
logs/             run outputs
```

## Implementation notes

- The run loop is intentionally simple: observe, propose, validate, execute, log.
- Actions are defined as typed Pydantic models rather than loose strings.
- Every executed step stores a screenshot plus the raw model output, which makes debugging much easier later.
- The replay UI is basic, but useful enough to inspect what happened across a run without digging through JSONL by hand.

## Current limitations

- The safety layer is still lightweight and keyword-based
- Coordinate-based desktop actions are inherently brittle
- This is a single-agent scaffold, not a full planning stack
- The replay UI is functional but minimal

## What I am adding next

- Better safety checks for sensitive typing and destructive actions
- Stronger recovery behavior after failed desktop actions
- More robust replay and trace browsing
- Additional providers and evaluation-style task sets

## Why it belongs in this repo collection

Casca shows the desktop side of the same broader interest that drives my browser and reasoning repos: grounded agents, inspectable traces, and practical experiments around reliability instead of hype.
