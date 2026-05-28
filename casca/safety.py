from casca.actions import BaseAction, TypeAction

class SafetyPolicy:
    def __init__(self, unsafe: bool = False, allow_secret_entry: bool = False):
        self.unsafe = unsafe
        self.allow_secret_entry = allow_secret_entry

    def check_task(self, task: str) -> tuple[bool, str | None]:
        task_lower = task.lower()
        dangerous_keywords = ["password", "delete", "rm ", "format", "buy", "purchase", "bank", "crypto"]
        
        for keyword in dangerous_keywords:
            if keyword in task_lower:
                if not self.unsafe:
                    return False, f"Task contains sensitive keyword '{keyword}'. Use --unsafe to bypass."
                    
        return True, None

    def check_action(self, action: BaseAction, task: str) -> tuple[bool, str | None]:
        if isinstance(action, TypeAction) and not self.allow_secret_entry:
            # A very simplistic heuristic. A real one might check if the text looks like a secret.
            pass
            
        return True, None
