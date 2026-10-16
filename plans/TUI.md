# Plan: Casca as a terminal app

Scope: the Python code on `main`. The goal is a terminal interface that follows the shared
design kit (`../design-kit`, the same files as `design/` on the local `new` branch): the Hermes
grammar in `system/TUI.md`, Casca's direction in `directions/casca.md`, and the `shell` skin.
The drawn screens are in `tui-mockups.html` beside this file.

It assumes the loop from `COMPUTER_USE.md` exists or is being built: gates, hand-back, stop and
the trace. The TUI is how those reach the user, so it can start in parallel with cu-04, as long
as the event interface (step 1) lands first.

## Two modes, one event stream

| Mode | Started by | What it is |
|---|---|---|
| Line mode | `casca run "task"`, `casca doctor`, `casca trace <run>` | Rows printed as they happen, scrolling like any CLI. No banner. Works over SSH, in CI and when piped |
| Interactive | `casca` with no arguments | Full screen: banner on the empty state, a log pane of tool rows, a rail with the current step's details, a prompt, and the status bar |
| Machine | `--json` or `--jsonl` on any command | One object per event. No colour, spinners or glyphs, whatever else is set |

The agent never prints. It emits events, and a renderer chooses how to show them:

```python
@dataclass(frozen=True)
class Event: ...
class RunStarted(Event):   task, profile, locality, os, permissions
class Observed(Event):     app, window, frame_size, bytes, seconds
class Proposed(Event):     tool, target, args, expect, why
class GateAsked(Event):    tool, target_label, app, reason, choices   # waits on an answer
class Acted(Event):        tool, target_label, result, seconds
class Verified(Event):     expect, held
class HandedBack(Event):   reason
class Finished(Event):     outcome, steps, seconds, bytes_sent
```

Renderers: `JsonlRenderer`, `LineRenderer` (Rich) and `AppRenderer` (Textual). Gate answers
and stop requests come back through one `Controls` object, so the loop does not know which
renderer is attached. This also fixes B8: model text is never interpreted as markup, because
renderers put it in `Text` objects, not format strings.

## The pieces, from `system/TUI.md`

| Piece | Casca's version |
|---|---|
| Banner | The six-row `CASCA` block from `banners/casca.txt`: rows 1 and 2 in `title` (bronze), 3 and 4 in `accent` (crimson), 5 and 6 in `border`. Interactive mode only. Below 44 columns, one line: `⬡ casca` |
| Metadata line | `dim`, `·` separated: `⬡ casca v0.2.0 · gpt-5.1 · your key: openai · macOS 27 · screen ✓ input ✓`. A local profile says `local` instead of the key. A missing permission shows `screen ✗` in `error` |
| Prompt | `❯ ` in `prompt`, under a `─` rule in `input_rule` |
| Response label | ` ⬡ Casca ` in bold `response_border` |
| Tool rows | `┊ {icon} {verb:9} {detail} {duration}`. Verbs from the direction: `read`, `locate`, `point`, `click`, `type`, `key`, `scroll`, `wait`, `verify`, plus `open` for `open_app`. Detail is the target's label from the hit test in quotes, or the point when there is no label: `click     "Save" button in TextEdit  0.1s`. Typed text shows its length only when it came from a sensitive source |
| Failed rows | Only the verb in `error`; the duration becomes the reason: `denied`, `not held`, `stuck` |
| Spinner | Braille frame in `accent`, face `⬡`/`⬢` in `label`, verb in `dim`: `reading the screen…`, `locating…`, `checking the gate…`, `pressing…`, `waiting for the app…`, `verifying…`. No kawaii |
| Gate | The one box: `╭─ approve? ─╮` in `warn`. Action line in `text`, reason in `dim`. `[y] approve once · [a] always for this task · [n/esc] deny`. Default deny, Enter alone does nothing. Secure-field typing is refused, never boxed |
| Hand-back | A box in `label`, not `warn`, because nothing is being approved: `╭─ your turn ─╮`, the reason, `[enter] I'm done · [esc] stop task` |
| Status bar | `status_bg` fill: model in `status_strong` │ locality │ step 4/30 │ cost $0.03 │ sent 412 KB │ gates 1 pending in `status_warn` │ `esc stop` |
| Errors | `error: what failed`, the fix on the next line, the cause chain in `dim`. No traceback without `-v` |
| Success | `ok done in 6 steps · 41 s · 1 approval` in `ok` |

Icons (emoji appear only in tool rows): `👁 read`, `🔎 locate`, `👉 point`, `👆 click`,
`⌨ type`, `⏎ key`, `↕ scroll`, `⏳ wait`, `✓ verify`, `▣ open`. Each is checked in JetBrains
Mono, SF Mono, Menlo and Cascadia before shipping; any that renders double-width or as tofu in
one of them is replaced, per `system/TYPOGRAPHY.md`.

## Interactive layout

```
┌ log ───────────────────────────────────────────────┬ step 4 ─────────────────┐
│ ❯ rename every file in ~/Desktop/shots by date     │ click                   │
│  ⬡ Casca                                           │ target  "Rename 14…"    │
│   ┊ 👁 read      Finder · "shots" · 1280×832  0.4s  │ role    menu item       │
│   ┊ 🔎 locate    "Rename 14 Items…"           0.1s  │ app     Finder          │
│   ╭─ approve? ───────────────────────╮             │ point   (612, 214)      │
│   │ click "Rename 14 Items…" Finder  │             │ expect  rename sheet    │
│   │ renames 14 files                 │             │ sent    121 KB          │
│   ╰─ [y] once · [a] always · [n] deny╯             │                         │
├────────────────────────────────────────────────────┴─────────────────────────┤
│ ❯                                                                            │
│ gpt-5.1 │ your key: openai │ step 4/30 │ $0.03 │ 412 KB sent │ 1 gate │ esc  │
└──────────────────────────────────────────────────────────────────────────────┘
```

- The rail is working context for the selected row; arrow keys move the selection.
- Below 100 columns the rail hides and `i` toggles it as an overlay. Below 60, the status bar
  keeps model, step and gates only.
- The terminal cannot show the frame in most emulators. The rail shows its size, bytes and path,
  and `o` opens the frame in the OS image viewer. Inline images through the kitty or iTerm
  protocol are a later option, not part of this plan.

Keys: `esc` stops (once) or closes the topmost box; `y`, `a`, `n` answer a gate; `t` expands a
collapsed run of rows; `i` toggles the rail; `o` opens the frame; `ctrl+t` lists past runs;
`?` shows every binding from the binding table.

## Library choice

- **Line mode: Rich**, already a dependency. A `Theme` built from the palette.
- **Interactive: Textual**, from the same authors as Rich, so `Text` objects and styles carry
  over. It runs the agent in a worker thread and posts events to the UI thread.
- Rejected: `prompt_toolkit` alone, which gives the prompt and key bindings but no layout or
  widgets; `curses`, which is not in Python's standard library on Windows; `urwid`, whose Windows
  support is limited.

New dependency: `textual`, pinned. It needs an entry in `docs/DECISIONS.md` on `main`.

## Colour

The palette comes from the design kit, not from hex values in Casca's code:

- Bring the kit into `main` with `node ../design-kit/scripts/kit.mjs init .`, which writes
  `design/` as on the `new` branch, then `kit use . shell`.
- The kit ships the terminal palette as Rust (`rust/palettes.rs`) and CSS (`tokens/skins.css`,
  the `--tui-*` variables) but not Python. Add a Python target to the master
  (`python/palettes.py`, generated from `src/skins.mjs` the same way `palettes.rs` is) so every
  Python project gets it through `kit update`. Rejected: copying the hex values into Casca,
  which drifts from the master on the next skin change.
- Detection follows `system/TUI.md` "Colour detection" in order: `NO_COLOR`, `CLICOLOR_FORCE`,
  not a TTY or `TERM=dumb`, `COLORTERM` for 24-bit, else 256-colour; polarity from
  `CASCA_THEME`, then `COLORFGBG`, then Apple Terminal's light default. Light terminals get the
  skin's light palette, never an inversion. `--color=auto|always|never` overrides.

## Tasks

| Id | Task | Done when |
|---|---|---|
| tui-01 | Event types and `Controls`; the agent emits instead of printing; `JsonlRenderer` | `casca run --jsonl` on the fake platform prints one valid object per event, checked by a test |
| tui-02 | Kit on `main`, the Python palette target in the master, colour detection | `NO_COLOR=1`, piped output and `--color=always` each produce the expected escape codes in tests |
| tui-03 | `LineRenderer`: metadata line, tool rows, spinner, gate and hand-back boxes, errors, success | A dry run on this Mac matches the mockup's line-mode screen, screenshot attached |
| tui-04 | `casca doctor` and `casca trace <run>` in line mode | Doctor with Screen Recording revoked shows the failing row and the fix |
| tui-05 | `AppRenderer`: banner empty state, log pane, rail, prompt, status bar, keys | Interactive run on the fixture app, screenshots in dark and light terminals |
| tui-06 | Stop, take-over and hand-back wired through `Controls` in both renderers | `esc` during a model call stops before the next input event, shown in the trace |
| tui-07 | Narrow widths, ASCII fallback (`CROSS_PLATFORM.md` xp-10), Windows Terminal | Screens at 120, 80 and 50 columns on macOS and Windows |

## Not verified

- The icon set has not been checked in Cascadia or the Windows Terminal default font.
- Textual's behaviour in legacy Windows `conhost` is unchecked; tui-07 decides whether
  interactive mode requires Windows Terminal.
- The design kit's `kit init` has not been run on `main`.
