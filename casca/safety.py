import re

from casca.actions import BaseAction, HotkeyAction, TypeAction

# Chords that close, quit or delete without asking. Read from the action's own arguments, never
# from the model's stated reason, which screen text can steer.
DESTRUCTIVE_CHORDS = {("command", "q"), ("command", "w"), ("alt", "f4"), ("ctrl", "w"),
                      ("command", "delete"), ("command", "backspace"), ("shift", "delete")}
API_KEY = re.compile(r"\b(?:sk-|ghp_|hf_|xox[bp]-)[A-Za-z0-9_-]{16,}")
CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")


def _luhn(digits: str) -> bool:
    total = sum(int(d) if i % 2 == 0 else sum(divmod(int(d) * 2, 10)) for i, d in enumerate(reversed(digits)))
    return total % 10 == 0

class SafetyPolicy:
    def __init__(self, unsafe: bool = False, allow_secret_entry: bool = False):
        self.unsafe = unsafe
        self.allow_secret_entry = allow_secret_entry

    def check_task(self, task: str) -> tuple[bool, str | None]:
        task_lower = task.lower()
        dangerous_keywords = ["password", "delete", "rm", "format", "buy", "purchase", "bank", "crypto"]

        for keyword in dangerous_keywords:
            if re.search(rf"\b{keyword}\b", task_lower):
                if not self.unsafe:
                    return False, f"Task contains sensitive keyword '{keyword}'. Use --unsafe to bypass."
                    
        return True, None

    def check_action(self, action: BaseAction, task: str) -> tuple[bool, str | None]:
        if self.unsafe:
            return True, None
        if isinstance(action, HotkeyAction):
            keys = tuple(k.lower().replace("cmd", "command") for k in action.keys)
            if keys in DESTRUCTIVE_CHORDS:
                return False, f"{'+'.join(keys)} can close or delete without asking. Use --unsafe to allow it."
        if isinstance(action, TypeAction) and not self.allow_secret_entry:
            cards = (re.sub(r"\D", "", m.group()) for m in CARD.finditer(action.text))
            if API_KEY.search(action.text) or any(map(_luhn, cards)):
                return False, "The text looks like an API key or a card number, which Casca does not type."
        return True, None
