from casca.models.base import VisionActionModel
from casca.prompts import SYSTEM_PROMPT, step_prompt
from casca.utils import encode_image_base64

# Models whose safety classifiers can decline a request; "default" fallbacks let the API rerun
# a declined step on a model it picks, inside the same call.
FALLBACK_MODELS = ("claude-fable-5", "claude-opus-5", "claude-sonnet-5-5")


class AnthropicProvider(VisionActionModel):
    """Claude through the Messages API, so the system prompt is cached across steps."""

    def __init__(self, base_url: str | None = None, model: str = "claude-opus-5-5", api_key: str | None = None,
                 effort: str | None = None):
        import anthropic
        self.anthropic = anthropic
        self.client = anthropic.Anthropic(api_key=api_key, base_url=base_url or None)
        self.model, self.effort = model, effort
        self.destination = self.client.base_url.host

    def propose_action(self, task, screenshot_bytes, step_index, history, screen) -> dict:
        extra = {"output_config": {"effort": self.effort}} if self.effort else {}
        if self.model.startswith(FALLBACK_MODELS):
            extra.update(betas=["server-side-fallback-2026-07-01"], fallbacks="default")
        image = {"type": "base64", "media_type": "image/png", "data": encode_image_base64(screenshot_bytes)}
        try:
            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=16000,
                system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": [{"type": "image", "source": image},
                                                       {"type": "text", "text": step_prompt(task, step_index, history, screen)}]}],
                **extra,
            )
        except self.anthropic.APIStatusError as e:
            return {"error": f"Anthropic API returned {e.status_code}: {e.message}"}
        except self.anthropic.APIConnectionError as e:
            return {"error": f"Anthropic API unreachable: {e}"}
        if response.stop_reason == "refusal":
            return {"error": f"the model declined this step: {getattr(response.stop_details, 'category', None)}"}
        return {"raw_output": "".join(block.text for block in response.content if block.type == "text"),
                "sent_bytes": len(image["data"]) + len(SYSTEM_PROMPT)}
