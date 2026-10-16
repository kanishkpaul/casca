# Casca MVP TODO

MVP: finish short desktop tasks in a controlled environment, with accurate actions and replayable evidence.

This checklist applies to the code on `main`. Fix correctness before expanding features. Existing archive/rebuild notices may describe the previous branch layout; do not treat them as instructions to switch branches. Mark an item complete only after implementing it and verifying its behavior.

## What needs fixing

- [ ] Translate screenshot coordinates to desktop coordinates correctly, including image resizing, display scaling, and monitor offsets.
- [ ] Detect blank or unusable screenshots and provide actionable guidance for missing capture or accessibility permissions.
- [ ] Include coordinates, entered text, action reasons, and execution results in model history, with appropriate handling of sensitive values.
- [ ] Support reliable Unicode text entry and avoid reporting silently dropped characters as successful input.
- [ ] Validate key names, coordinate bounds, drag durations, scroll amounts, and wait durations before execution.
- [ ] Record execution errors and fail-safe interruptions as failed or interrupted steps, then finalize run metadata.
- [ ] Recover from malformed model output with bounded retries and useful validation feedback.
- [ ] Replace task-substring filtering and permissive per-action checks with checks on the proposed action and configured task permissions.
- [ ] Record model identity, display geometry, screenshot scale, start/end times, and final outcome so runs can be compared.
- [ ] Include the replay viewer and its assets in packaged installations so it works outside an editable checkout.

## What features to add

- [ ] Capture before-and-after screenshots and verify whether each action produced the expected visible change.
- [ ] Add application restrictions and per-action approval controls for consequential operations.
- [ ] Add pause, resume, and emergency-stop controls that work during execution and preserve the trace.
- [ ] Detect loops and add bounded retries with a clear terminal failure state.
- [ ] Add consistent task definitions and a run-comparison view for evaluating models on the same tasks.
- [ ] Add an installation check covering screenshot capture, input permissions, coordinate mapping, and model connectivity.
