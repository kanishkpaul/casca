# Casca bug fix plan

Scope: the Python code on `main` at `e9b3fe3`. Found on 2026-10-16 by reading every file and
reproducing each bug that could be reproduced without moving the mouse or typing. Machine:
macOS 27 on a MacBook with a Retina panel (logical screen 1470 x 956, backing scale 2), Python
3.14.8, pyautogui 0.9.54.

Each bug lists where it is, how it was shown, and the fix. "Repro" means a command was run and
the output is quoted. "Read" means the bug follows from the code and the library source, but no
run showed it. The TODO.md item each bug belongs to is given in brackets.

## Bugs

### Wrong actions on the desktop

**B1. Clicks land in the wrong place.** [TODO: coordinates]
`casca/screen.py:25-43`, `casca/agent.py:69-77`, `casca/models/hf_provider.py:40`,
`casca/desktop.py`. The model sees a screenshot resized to 1280 px wide. The prompt tells it the
screen is 1470 x 956. Its coordinates are in image pixels, and they are clicked as screen points,
so every click is off by 1470 / 1280 = 1.148 (15%). On a 1920 px screen the error is 50%. The
monitor's `left` and `top` are never added, so a second monitor gets clicks on the first. With
`CASCA_MONITOR=0` the image is every screen combined, and the error is larger still.
Read, plus `mss` monitors on this machine: `{'left': 0, 'top': 0, 'width': 1470, 'height': 956}`.
Fix: one geometry record per capture (image size, logical size, monitor offset). Tell the model
the image size. Map `x_screen = left + x_img * logical_w / img_w` in one function, used by every
pointer action.

**B2. Out-of-range coordinates are clamped onto the fail-safe corners.** [TODO: validation]
`casca/desktop.py:16-19`. A coordinate past the edge is clamped to the edge, so the click goes
somewhere the model never chose. A clamp to a corner puts the mouse on a PyAutoGUI fail-safe
point, and the next action raises `FailSafeException`.
Repro: `pyautogui.FAILSAFE_POINTS` is `[(0, 0), (0, 955), (1469, 0), (1469, 955)]`, which are
exactly the clamp targets for `x<0,y<0` and `x>=1470,y>=956`.
Fix: reject out-of-bounds coordinates at validation (B6) and send the model the error. Never clamp.

**B3. Unknown keys and non-ASCII text are dropped and reported as success.** [TODO: Unicode]
`casca/desktop.py:43-50`. On macOS, `pyautogui._pyautogui_osx._keyDown` returns without a
keypress when the key is not in its mapping. `typewrite("café")` types `caf`. `press("enterr")`
does nothing. Both return `{"status": "success"}`.
Repro: `'é' in keyboardMapping` is `False`; `'enterr' in keyboardMapping` is `False`; the source
line is `if key not in keyboardMapping or keyboardMapping[key] is None: return`.
Fix: validate key names against `pyautogui.KEYBOARD_KEYS` before execution. Type ASCII with
`typewrite`; enter anything else through the clipboard and paste, restoring the clipboard after.
That needs a clipboard dependency, which is a decision to record. Report any character that
could not be typed as a failed step.

**B4. The prompt teaches Windows shortcuts.** [TODO: coordinates, related]
`casca/prompts.py:42` uses `["ctrl","l"]`. On macOS that does not focus the address bar.
`examples/tasks.yaml` names Notepad and File Explorer. Read.
Fix: put the operating system in the prompt and use its modifier in the examples. Replace the
example tasks with ones that exist on all three systems, or keep one set per system.

**B5. Scroll units differ by platform by a factor of about 100.** [TODO: validation]
`casca/desktop.py:52-53`, `casca/prompts.py:44`. The prompt example is `amount: -650`. On macOS
PyAutoGUI scrolls in lines (`kCGScrollEventUnitLine`), so that is 650 lines. On Windows the value
is passed as wheel delta, where 120 is one notch, so that is about 5 notches.
Read, from `pyautogui._pyautogui_osx._vscroll`.
Fix: define `amount` as notches, bound it to plus or minus 20, convert per platform, and fix the
prompt example.

### Crashes and lost traces

**B6. Action fields are not validated.** [TODO: validation]
`casca/actions.py`. `ms=-500` parses. `time.sleep(-0.5)` then raises `ValueError` and ends the
run. A large `ms` hangs it. Negative drag duration, an empty `hotkey` list and huge scroll
amounts all pass.
Repro: `parse wait -500: WaitAction(reason='a', action='wait', ms=-500)` and
`time.sleep(-0.5): RAISES ValueError: sleep length must be non-negative`.
Fix: `Field` bounds on every numeric field (for example `0 <= ms <= 10000`,
`0 < duration <= 5`), `min_length=1` on `keys`, and a geometry check for coordinates (B1).

**B7. Errors during execution end the run with no record.** [TODO: errors]
`casca/agent.py:111-113`, `casca/desktop.py:58-86`. `execute_action` is not inside a `try`.
`FailSafeException`, `ValueError` from B6, or any PyAutoGUI error unwinds out of `run()`. The step
is never logged and metadata never gets an outcome. Read.
Fix: catch around execution. Log the step as `failed` or, for the fail-safe, `interrupted`. Write
the outcome to metadata in a `finally`.

**B8. Model text containing `[/x]` crashes the run.** [new]
`casca/agent.py:60, 88, 92, 126, 129, 133`. Model output and the task are printed through Rich
with markup on. A closing tag in a reason or answer raises `MarkupError`. Other bracketed text is
silently eaten from the console output.
Repro: `rich print reason with [/b]: RAISES MarkupError: closing tag '[/b]' ... doesn't match any open tag`.
Fix: `rich.markup.escape()` on every piece of model or user text, or print it with `markup=False`.

**B9. A null message content crashes the parser.** [TODO: malformed output]
`casca/models/hf_provider.py:94`, `casca/agent.py:45`. `.get("content", "")` returns `None` when
the API sends `"content": null` (refusals and some tool-call replies do). `None.find` raises
`AttributeError`, which `parse_action` does not catch.
Repro: `parse None content: RAISES AttributeError: 'NoneType' object has no attribute 'find'`.
Fix: treat `None` as an empty reply and route it to the retry path (B12).

**B10. Two runs in the same second share one directory.** [TODO: run metadata]
`casca/logger.py:9`. The run id has one-second resolution. The second run overwrites
`metadata.json` and the screenshots, and appends to the first run's `steps.jsonl`.
Repro: `two loggers same second share dir: True`.
Fix: add microseconds and a short random suffix, and create the directory with `exist_ok=False`.

**B11. Several ends of a run leave no trace.** [TODO: errors, run metadata]
`casca/agent.py:79-89, 103-107, 137-138`. A model error, a parse failure, a user abort at the
confirm prompt and reaching max steps are printed and never logged. Metadata has a start time and
nothing else, so a run that crashed and a run that finished look the same. Read.
Fix: log a step record for each of these. Write `end_time`, `outcome`
(`done`, `fail`, `max_steps`, `model_error`, `parse_error`, `aborted`, `interrupted`, `crashed`),
model id, geometry and screenshot scale to metadata at the end, from a `finally`.

**B12. One malformed reply stops the run, and the error is 41 lines.** [TODO: malformed output]
`casca/agent.py:42-57, 86-89`. Two JSON objects in a reply (`{...} {...}`) span from the first
`{` to the last `}` and fail to decode. Any validation error is reported against all twelve union
members at once.
Repro: `parse two objects: None` with `Extra data: line 1 column 39`, and `41 validation errors`
for `[{"action":"wait"}]`.
Fix: decode the first object with `json.JSONDecoder().raw_decode`. Make the union discriminated
on `action` (`Field(discriminator="action")`) so a bad reply gets one error about one action.
Allow 2 retries that send that error back to the model, then stop with outcome `parse_error`.

**B13. Dry run tells the model its actions succeeded.** [new]
`casca/agent.py:109`. In a dry run `execution_log` stays `{"status": "success"}` and goes into
the history, while the screen does not change. Read.
Fix: record `{"status": "skipped"}` in dry runs and say so in the prompt.

### Model provider

**B14. The default Hugging Face endpoint does not exist.** [new]
`casca/models/hf_provider.py:15`. With `HF_API_URL` unset, requests go to
`api-inference.huggingface.co`, and that host does not resolve.
Repro: `curl: (6) Could not resolve host: api-inference.huggingface.co`. The router endpoint
`https://router.huggingface.co/v1/chat/completions` answers `401` without a token, so it is live.
Fix: default to the router URL and send the model id in the body, which the code already does.

**B15. A base URL ending in `/v1` gets `/v1` twice.** [new]
`casca/models/hf_provider.py:17-18`.
Repro: `HF_API_URL=https://router.huggingface.co/v1` becomes
`https://router.huggingface.co/v1/v1/chat/completions`.
Fix: strip a trailing `/v1` before appending, or require the full URL and document it.

**B16. HTTP errors are reported wrongly.** [new]
`casca/models/hf_provider.py:82-105`. A 400 raises `RuntimeError` inside the `try`, which the
catch-all turns into "Unexpected error". A 404 always says the model was not found, including
when the URL is wrong (B15). 429 and 503 are not retried. Read.
Fix: return the status and body for each case, and retry 429 and 503 twice with backoff.

**B17. The model's history has no coordinates, text, reasons or errors.** [TODO: history]
`casca/models/hf_provider.py:36-37`, `casca/agent.py:119-123`. The model sees
`Action: click, Result: success` and cannot tell where it clicked or why a step failed. Read.
Fix: put the full action, the reason and the execution error in history. Replace typed text with
its length when the step is marked sensitive.

### Safety

**B18. The task filter blocks ordinary tasks.** [TODO: safety]
`casca/safety.py:8-17`. It checks substrings of the task.
Repro: "Open the form and fill in my name" is blocked on `'rm '`; "Show information about the
weather" on `'format'`; "Open the riverbank photo" on `'bank'`.
Fix: replace the substring list with checks on the proposed action (B19). If a task check stays,
match whole words.

**B19. Every action is approved.** [TODO: safety]
`casca/safety.py:19-24`. `check_action` returns `(True, None)` for everything, and
`allow_secret_entry` is never read. `--unsafe` turns off the only check that exists.
Repro: `check_action type password: (True, None)`.
Fix: a per-action policy with configured task permissions: allowed apps, whether typing is
allowed, a confirm step for send, submit, delete and purchase. This is the TODO's feature work,
so it is listed here and sized there.

### Screen capture

**B20. A blank screenshot is sent to the model as if it were the screen.** [TODO: blank screenshots]
`casca/screen.py:32-43`. Without Screen Recording permission on macOS the capture is the desktop
wallpaper or black, and the run carries on. Read; reported as reproduced in PR
kanishkpaul/casca#1.
Fix: check pixel variance with `PIL.ImageStat` on the first capture, and stop with the steps to
grant permission.

**B21. A negative monitor index is accepted.** [new]
`casca/screen.py:15`. `CASCA_MONITOR=-1` passes the `>= len` check and selects the last monitor.
`0` selects all monitors combined, which B1 cannot map. Read.
Fix: require `1 <= index < len(monitors)`.

**B22. `mss.mss()` is deprecated in the installed mss.** [new]
`casca/screen.py:12`. Repro: `DeprecationWarning: mss.mss is deprecated and will be removed in a
future release; use mss.MSS instead`. `pyproject.toml` pins no versions, so a fresh install will
break when it is removed.
Fix: use `mss.MSS()` and pin lower and upper bounds for every dependency.

### Replay viewer and packaging

**B23. `casca web` does not work from an installed package.** [TODO: packaging]
`casca/cli.py:54-56`, `pyproject.toml`. The command looks for `web/` next to the package. The
wheel contains only `casca/`.
Repro: `pip wheel . --no-deps` lists 16 files under `casca/` and none under `web/`.
Fix: move the viewer to `casca/web/` with its templates and static files, and start the Flask app
in process instead of running `flask run` from `PATH`, which may be another environment's Flask.

**B24. `FLASK_ENV` does nothing.** [new]
`casca/cli.py:60`. Flask 2.3 removed it. Read.
Fix: drop it; pass `debug=False` explicitly.

**B25. The viewer serves files outside the logs directory.** [new]
`web/app.py:22-39`. `run_id` is not checked. `/run/../screenshots/<file>` serves files from a
`screenshots` folder next to the logs directory, and `/run/..` returns a 500 with the absolute
path in the body.
Repro: `/run/../screenshots/leak.txt -> 200 b'secret\n'` and `/run/.. -> 500 b'Run /private/tmp/...'`.
Low severity because the server binds to localhost.
Fix: accept only run ids matching the logger's format and check the resolved path is inside the
logs directory.

**B26. Corrupt runs disappear from the index without a word.** [new]
`web/app.py:15-19`. Any exception while loading a run is swallowed, and the run page returns the
raw exception text.
Repro: a run with a bad `steps.jsonl` is missing from `/` and `/run/run_x` returns
`500 Expecting value: line 1 column 1`.
Fix: list it with a "could not load" marker and the reason.

**B27. The logs directory depends on the current directory.** [TODO: packaging]
`casca/config.py:16`. `logs` is relative, so `casca run` in one folder and `casca web` in another
see different runs. `platformdirs` is a dependency and is never imported. Read.
Fix: default to `platformdirs.user_data_dir("casca") / "logs"`, still overridable.

### Small

**B28.** `casca/config.py:11-14`: a non-numeric `CASCA_MAX_STEPS` or similar raises a traceback at
import. Fix: parse in one function that names the variable in the error.
**B29.** `casca/agent.py:39`: the run directory is created before the task check, so a rejected
task leaves an empty directory. Fix: create it after the check.
**B30.** `examples/tasks.yaml` is not read by any code and there is no YAML dependency. Fix: either
add the runner from the TODO's "consistent task definitions" item, or delete the file.
**B31.** There are no tests. Every fix above needs one.

## Order of work

Each phase is one branch and one pull request. A phase is done when its tests pass and its
"Verify" step has been run and the output pasted into the pull request.

### Phase 0: a test harness that never touches the desktop
- Add `pytest` as a dev dependency.
- `FakeDesktop`: records the calls `DesktopController` would make, and can be told to raise.
- `FakeScreen`: returns fixed images and fixed geometry, including a 2940 x 1912 capture of a
  1470 x 956 screen.
- A test that runs `CascaAgent` with the mock provider, `FakeScreen` and `FakeDesktop` end to end.
- Verify: `pytest -q` passes on a clean clone.

### Phase 1: stop crashes and lost traces
B7, B8, B9, B10, B11, B6, B13, B29.
- Verify: tests for each repro above, now passing. A fake desktop that raises
  `FailSafeException` produces a run with outcome `interrupted` and every step logged.

### Phase 2: actions do what the model asked
B1, B2, B3, B4, B5.
- Verify in tests: the mapping function on the 2940 / 1470 / 1280 case and on a monitor with
  `left=1470`. Unknown keys and a `café` string are rejected or pasted, never reported as typed.
- Verify on the real desktop: click targets on a local HTML page with numbered boxes, and report
  the pixel error per box. This moves the mouse and types into one browser window. Say so before
  running it.

### Phase 3: the model loop recovers
B12, B14, B15, B16, B17.
- Verify: tests with canned replies (two objects, fenced JSON, null content, a bad field) show
  one retry with one error each. One live call to the router endpoint with a real token returns
  a parsed action.

### Phase 4: safety checks the action, not the task text
B18, B19.
- Verify: the three false-positive tasks above are allowed. A `type` action into a password field
  and a click on a "Send" button are blocked or sent for confirmation.

### Phase 5: capture checks
B20, B21, B22.
- Verify: a black image and a single-colour image stop the run with the permission steps.

### Phase 6: viewer and packaging
B23, B24, B25, B26, B27.
- Verify: `pip install dist/casca-*.whl` into a fresh venv, then `casca web` from `/tmp` shows the
  runs. The two traversal URLs return 404.

### Phase 7: cleanup
B28, B30, B31 (any gaps left).

## Not verified

- B1's 15% figure is computed from the capture and screen sizes on this machine, and matches the
  number in PR kanishkpaul/casca#1. No click was made today.
- B3 and B5 were read from PyAutoGUI's macOS backend. The Windows and Linux behaviour was read
  from the library, not run.
- B20 was not reproduced today; it relies on the report in PR kanishkpaul/casca#1.
- Nothing was run on Windows or Linux.
