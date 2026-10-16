"""Checks between a proposed act and the desktop. Each reads what the OS reports at the target,
never the model's stated reason, which text on the screen can steer."""
import re

# Words on a control that usually commit something that cannot be taken back.
COMMITTING = re.compile(r"\b(send|pay|buy|purchase|order|delete|erase|remove|post|publish|submit|install|grant|"
                        r"allow|transfer|sign out|log out)\b", re.I)
CONTROLS = {"AXButton", "AXMenuItem", "AXMenuButton", "AXLink", "AXCheckBox", "AXRadioButton", "AXPopUpButton"}
POINTER = {"click", "double_click", "right_click", "drag"}
KEYBOARD = {"type", "press", "hotkey"}


def in_scope(app: str | None, allowed: list[str]) -> bool:
    """macOS draws some panels in helper processes named "Open and Save Panel Service (TextEdit)"."""
    app = (app or "").lower()
    return not allowed or any(app == a.lower() or app.endswith(f"({a.lower()})") for a in allowed)


def check(action, target: dict | None, focused: dict | None, allowed: list[str]) -> tuple[str, str | None]:
    """Returns ("allow" | "confirm" | "refuse", reason)."""
    if action.action == "open_app" and not in_scope(action.name, allowed):
        return "refuse", f"{action.name} is not one of the allowed apps: {', '.join(allowed)}"
    if action.action in POINTER:
        if target is None:
            return "confirm", "the OS cannot say what is at this point"
        if not in_scope(target["app"], allowed):
            return "refuse", f"the target is in {target['app']}, outside the allowed apps"
        if target["role"] is None:
            return "confirm", f"the control in {target['app']} cannot be read on this OS"
        if target["role"] in CONTROLS and COMMITTING.search(target["name"]):
            return "confirm", f"\"{target['name']}\" in {target['app']} may not be undoable"
    if action.action in KEYBOARD and focused:
        if action.action == "type" and focused["secure"]:
            return "refuse", "the focused field is a password field, which Casca never types into"
        if not in_scope(focused["app"], allowed):
            return "refuse", f"keyboard focus is in {focused['app']}, outside the allowed apps"
    return "allow", None
