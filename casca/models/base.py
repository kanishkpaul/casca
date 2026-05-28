from abc import ABC, abstractmethod

class VisionActionModel(ABC):
    @abstractmethod
    def propose_action(
        self,
        task: str,
        screenshot_bytes: bytes,
        step_index: int,
        history: list[dict],
        screen: dict,
    ) -> dict:
        """
        Takes task context and screenshot, and returns raw action JSON string.
        """
        pass
