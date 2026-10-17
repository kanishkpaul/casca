# casca

A desktop agent that answers about your screen, finds the control you can only describe
vaguely, and operates your apps to finish a task, on macOS, Windows and Linux. It acts on the
user's real desktop, so its identity is a shell: crimson and bronze, like Hermes's `ares` skin,
with gates as the most designed part of the product.

| | |
|---|---|
| Default skin | **Shell** (`shell`): crimson `#EE6A52` with bronze `#E8C88A` titles on near-black; brick `#B5301F` on warm paper in light |
| Glyph | ⬡ |
| Kawaii | **Off.** It is pressing buttons on your computer |
| Mode | Follows the OS |
| Surfaces | The terminal only: `casca` opens the interactive TUI; `casca run`, `doctor`, `trace` and `eval` print line by line. No GUI, no screen overlay, no web viewer |
| Uses | `tokens/tokens.json`: the shell skin's `tui` palette and the casca identity, read by `casca/term.py`. The CSS files and `rust/` come with the kit and are unused here |

## Feel

- Deliberate. Every step is announced before it happens and confirmed after.
- When it hands back control (sign-ins, ambiguity), it says exactly what it needs and waits.

## Terminal (the only interface)

```
 ⬡ casca v0.1.0 · claude-sonnet · your key: anthropic · macOS 15 · a11y ✓ screen ✓
──────────────────────────────────────────────────────────────────────────────
❯ rename every file in ~/Desktop/shots to its date, then stop
 ⬡ Casca
  ┊ 👁 read      Finder · "shots" · 41 elements          0.4s
  ┊ 🔎 locate    [17] menu item "Rename 14 Items…"       0.1s
  ╭─ approve? ───────────────────────────────────────────────────╮
  │ click  [17] "Rename 14 Items…" in Finder                     │
  │ renames 14 files; undo with ⌘Z in Finder                     │
  ╰─ [y] approve once · [a] always for this task · [n/esc] deny ─╯
```

- The banner (CASCA in bronze-to-crimson) shows for `casca run` without arguments only.
  `casca run "task"` starts with the metadata line, which names the model, where it runs and
  whether the OS permissions are granted.
- Elements are always cited by their number in brackets and their accessible name in quotes:
  `[17] "Rename 14 Items…"`. The model cannot refer to an element casca did not number, and the
  output makes that visible.
- Tool verbs: `read`, `locate`, `point`, `click`, `type`, `key`, `scroll`, `wait`, `verify`.
- Spinner verbs: reading the screen, locating, checking the gate, pressing, waiting for the app,
  verifying. Glyphs `⬡ ⬢` as the face slot.
- Gates follow TUI.md exactly. Anything irreversible, anything that sends data off the machine,
  and any credential field is gated. Typing into a password field is refused, not gated.
- `casca doctor` prints one row per check with `ok`/`error` and the fix for each failure.
- `casca trace <run>` prints the run as rows.

## Past runs

`casca trace` lists runs as rows: id, outcome, steps, task. `casca trace <run>` prints one run as
tool rows with gate rows marked in `warn`, and `ctrl+t` in the TUI opens the same list. A run's
screenshots stay on disk beside its trace; `o` opens the current one in the OS image viewer.

## Words

Literal. "Clicked [17] "Rename 14 Items…"." "Waiting for you to sign in to Dropbox. Press
Enter when done." "Stopped. 4 of 6 steps finished; nothing was undone."

## Don't

- Don't animate the cursor or fake mouse movement for show.
- Don't describe an element the model guessed. If it isn't in the numbered list, it isn't there.
