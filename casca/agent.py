import json
import sys
import threading
import time
from pyautogui import FailSafeException
from pydantic import ValidationError, TypeAdapter

from casca.screen import ScreenObserver
from casca.desktop import DesktopController
from casca.logger import RunLogger
from casca.safety import SafetyPolicy
from casca.models.base import VisionActionModel
from casca.actions import ActionType
from casca.config import config
from casca import gates
from casca.coords import POINT_FIELDS, to_screen
from casca.ui import UI

ACTIONS = TypeAdapter(ActionType)
PARSE_ATTEMPTS = 3
STUCK_REPEATS = 3


def signature(action: dict) -> tuple:
    """An act with its target rounded to 10 px, so repeating "the same click" is detectable."""
    return tuple((k, v // 10 if k in POINT_FIELDS else v) for k, v in sorted(action.items())
                 if k not in ("reason", "expect", "previous"))

class CascaAgent:
    def __init__(
        self,
        model: VisionActionModel,
        max_steps: int = config.MAX_STEPS,
        max_seconds: float = config.MAX_SECONDS,
        settle_timeout: float = 2.0,
        unsafe: bool = False,
        confirm_each_step: bool = False,
        dry_run: bool = False,
        coords: str = config.COORDS,
        apps: list[str] | None = None,
        log_dir: str = config.LOG_DIR,
        screen=None,
        desktop=None,
        ui: UI | None = None,
    ):
        self.model = model
        self.max_steps = max_steps
        self.max_seconds = max_seconds
        self.settle_timeout = settle_timeout
        self.unsafe = unsafe
        self.confirm_each_step = confirm_each_step
        self.dry_run = dry_run
        self.coords = coords
        self.apps = apps or []
        
        self.screen = screen or ScreenObserver()
        screen_size = self.screen.get_screen_size()
        self.desktop = desktop or DesktopController(screen_size["width"], screen_size["height"])
        self.safety = SafetyPolicy(unsafe=self.unsafe)
        self.log_dir = log_dir
        self.history = []
        self.ui = ui or UI()

    def parse_action(self, raw_output: str | None) -> tuple[ActionType | None, str | None]:
        """Reads the first JSON object in the reply. Returns the action, or None and why not."""
        text = raw_output or ""
        start = text.find("{")
        if start == -1:
            return None, "the reply has no JSON object"
        try:
            data, _ = json.JSONDecoder().raw_decode(text, start)
            return ACTIONS.validate_python(data), None
        except json.JSONDecodeError as e:
            return None, f"invalid JSON: {e}"
        except ValidationError as e:
            return None, "; ".join(f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors())

    def _gate(self, action, size, monitor) -> tuple[str, str | None, dict | None]:
        target = focused = None
        if action.action in gates.POINTER:
            try:
                mapped = to_screen(action, size, monitor)
            except ValueError:
                return "allow", None, None  # execution reports the point as outside the screenshot
            target = self.desktop.element_at(*((mapped.x, mapped.y) if hasattr(mapped, "x") else (mapped.x1, mapped.y1)))
        elif action.action in gates.KEYBOARD:
            focused = self.desktop.focused_element()
        decision, reason = gates.check(action, target, focused, self.apps)
        return decision, reason, target or focused

    @staticmethod
    def _moved(a: tuple[int, int], b: tuple[int, int]) -> bool:
        return abs(a[0] - b[0]) > 5 or abs(a[1] - b[1]) > 5

    def _watch_stop(self) -> None:
        while not self.finished.is_set():
            if self.desktop.stop_pressed():
                self.stop_requested.set()
                return
            time.sleep(0.05)

    def _settle(self, before: bytes, every: float = 0.15) -> dict:
        """Waits until the screen has changed and stopped changing, instead of a fixed sleep."""
        start, last = time.monotonic(), before
        while time.monotonic() - start < self.settle_timeout and not self.stop_requested.is_set():
            time.sleep(every)
            frame = self.screen.screenshot()
            if frame == last != before:
                break
            last = frame
        return {"settle_s": round(time.monotonic() - start, 2), "changed": last != before}

    def run(self, task: str) -> str:
        self.ui.emit("start", task=task, model=getattr(self.model, "model", self.model.__class__.__name__),
                     destination=getattr(self.model, "destination", "none"), dry_run=self.dry_run, apps=self.apps)
        started, self.end_message, self.sent_bytes = time.monotonic(), None, 0

        is_safe, reason = self.safety.check_task(task)
        if not is_safe:
            self.ui.emit("end", outcome="rejected", message=reason, steps=0, seconds=0, sent_bytes=0)
            return "rejected"

        self.logger = RunLogger(log_dir=self.log_dir)
        self.logger.log_metadata(
            task, self.max_steps, getattr(self.model, "model", self.model.__class__.__name__),
            destination=getattr(self.model, "destination", "none"), coords=self.coords, apps=self.apps,
            monitor=self.screen.get_screen_size(), max_seconds=self.max_seconds, dry_run=self.dry_run)
        outcome = "crashed"
        self.stop_requested, self.finished = threading.Event(), threading.Event()
        if not self.dry_run:
            threading.Thread(target=self._watch_stop, daemon=True).start()
        try:
            outcome = self._loop(task)
        except (KeyboardInterrupt, FailSafeException):
            outcome, self.end_message = "interrupted", "interrupted; nothing was undone"
        finally:
            self.finished.set()
            self.logger.finish(outcome)
            self.ui.emit("end", outcome=outcome, message=self.end_message, steps=len(self.history),
                         seconds=time.monotonic() - started, sent_bytes=self.sent_bytes, run_id=self.logger.run_id)
        return outcome

    def _loop(self, task: str) -> str:
        monitor = self.screen.get_screen_size()
        if not self.dry_run and (problem := self.desktop.input_problem()):
            self.end_message = f"cannot send input: {problem}"
            return "no_input"

        started, self.left_at = time.monotonic(), None
        for step in range(self.max_steps):
            if time.monotonic() - started > self.max_seconds:
                self.end_message = f"the {self.max_seconds} s time budget is used up"
                return "time_budget"
            screenshot = self.screen.screenshot()
            width, height = (1000, 1000) if self.coords == "norm1000" else self.screen.image_size

            trace = {"image_size": list(self.screen.image_size)}

            def log(action, safety, execution, raw=None):
                self.logger.log_step(step, task, screenshot, raw, action, safety, execution, **trace)

            # Checked every step: a frame that turns black mid-run can be the Windows UAC prompt,
            # which sits on a secure desktop Casca cannot capture or click.
            if problem := self.screen.capture_problem():
                self.end_message = f"cannot see the screen: {problem}"
                log(None, None, {"status": "blank_screen", "error": problem})
                return "blank_screen"

            self.ui.emit("observe", step=step, image_size=list(self.screen.image_size))
            self.ui.emit("think", step=step)
            feedback = []
            for _ in range(PARSE_ATTEMPTS):
                result = self.model.propose_action(task, screenshot, step, self.history + feedback, {"width": width, "height": height})
                if "error" in result:
                    self.end_message = f"the model did not answer: {result['error']}"
                    log(None, None, {"status": "model_error", "error": result["error"]})
                    return "model_error"
                trace["sent_bytes"] = trace.get("sent_bytes", 0) + result.get("sent_bytes", 0)
                self.sent_bytes += result.get("sent_bytes", 0)
                raw_output = result["raw_output"]
                action, problem = self.parse_action(raw_output)
                if action:
                    break
                self.ui.emit("invalid_reply", step=step, problem=problem)
                feedback = [{"step": step, "action": "invalid reply", "execution": {"status": "error", "error": problem}}]
            else:
                self.end_message = f"three replies in a row could not be read; the last: {problem}"
                log(None, None, {"status": "parse_error", "error": problem}, raw_output)
                return "parse_error"

            if action.previous and self.history and isinstance(self.history[-1]["action"], dict):
                self.ui.emit("verify", step=step, expect=self.history[-1]["action"].get("expect", ""), verdict=action.previous)

            action_is_safe, safety_reason = self.safety.check_action(action, task)
            safety_log = {"allowed": action_is_safe, "reason": safety_reason}

            if not action_is_safe:
                self.end_message = f"blocked: {safety_reason}"
                log(action.model_dump(), safety_log, {"status": "blocked"}, raw_output)
                return "blocked"

            decision, gate_reason, element = self._gate(action, (width, height), monitor)
            safety_log.update(gate=decision, gate_reason=gate_reason, element=element)
            refused = decision == "refuse" or (decision == "confirm" and not self.dry_run
                                               and not self.ui.approve(action.model_dump(), gate_reason, element))

            if self.confirm_each_step and not self.dry_run:
                if not refused and not self.ui.approve(action.model_dump(), "you asked to confirm each step", element):
                    self.end_message = "you declined the step"
                    log(action.model_dump(), safety_log, {"status": "aborted"}, raw_output)
                    return "aborted"

            if refused:
                self.ui.emit("refused", step=step, action=action.model_dump(), reason=gate_reason, element=element)
                execution_log = {"status": "refused", "error": gate_reason}
            elif self.dry_run:
                execution_log = {"status": "skipped"}
            else:
                if self.stop_requested.is_set():
                    self.end_message = "stopped by the stop keys; nothing was undone"
                    log(action.model_dump(), safety_log, {"status": "stopped"}, raw_output)
                    return "stopped"
                if self.left_at and self._moved(self.desktop.cursor(), self.left_at):
                    if not self.ui.pause("You moved the mouse, so Casca paused."):
                        log(action.model_dump(), safety_log, {"status": "taken_over"}, raw_output)
                        return "taken_over"
                    self.left_at = None
                    continue
                if problem := self.desktop.input_problem():
                    self.end_message = f"cannot send input: {problem}"
                    log(action.model_dump(), safety_log, {"status": "no_input", "error": problem}, raw_output)
                    return "no_input"
                try:
                    mapped = to_screen(action, (width, height), monitor)
                    trace["screen_point"] = {k: v for k, v in mapped.model_dump().items() if k in POINT_FIELDS}
                    execution_log = self.desktop.execute_action(mapped)
                except FailSafeException:
                    log(action.model_dump(), safety_log, {"status": "interrupted"}, raw_output)
                    raise
                except Exception as e:
                    execution_log = {"status": "error", "error": f"{type(e).__name__}: {e}"}

            if execution_log["status"] == "success" and action.action not in ("done", "fail", "handback", "wait"):
                execution_log.update(self._settle(screenshot))
            if execution_log["status"] == "success" and action.action in gates.POINTER | {"move_mouse"}:
                self.left_at = self.desktop.cursor()
            if action.previous and self.history:
                self.history[-1]["verified"] = action.previous
            log(action.model_dump(), safety_log, execution_log, raw_output)
            self.history.append({"step": step, "action": action.model_dump(), "execution": execution_log})
            if not refused:
                self.ui.emit("act", step=step, action=action.model_dump(), result=execution_log, element=element)
            recent = [signature(h["action"]) for h in self.history[-STUCK_REPEATS:] if isinstance(h["action"], dict)]
            if len(recent) == STUCK_REPEATS and len(set(recent)) == 1 and action.action not in ("wait", "done"):
                self.end_message = f"the same {action.action} {STUCK_REPEATS} times in a row"
                return "stuck"

            if action.action == "done":
                self.end_message = action.answer
                return "done"
            if action.action == "handback":
                if self.dry_run or not self.ui.pause(action.reason):
                    self.end_message = f"handed back: {action.reason}"
                    return "handed_back"
                self.history[-1]["execution"] = {"status": "user_done", "note": "the user finished this and said to carry on"}
                continue
            if action.action == "fail":
                self.end_message = f"the model gave up: {action.reason}"
                return "fail"

        self.end_message = f"{self.max_steps} steps used without finishing"
        return "max_steps"
