from casca.models.base import VisionActionModel
import json

class MockVisionProvider(VisionActionModel):
    def __init__(self):
        self.step_count = 0

    def propose_action(
        self,
        task: str,
        screenshot_bytes: bytes,
        step_index: int,
        history: list[dict],
        screen: dict,
    ) -> dict:
        self.step_count += 1
        
        if self.step_count == 1:
            action = {
                "action": "move_mouse",
                "x": screen["width"] // 2,
                "y": screen["height"] // 2,
                "reason": "Mock move to center.",
                "expect": "The pointer is in the centre."
            }
        elif self.step_count == 2:
            action = {
                "action": "click",
                "x": screen["width"] // 2,
                "y": screen["height"] // 2,
                "reason": "Mock click center.",
                "expect": "The centre was clicked."
            }
        else:
            action = {
                "action": "done",
                "answer": "Mock task complete.",
                "reason": "Finished mock queue."
            }
            
        return {"raw_output": json.dumps(action)}
