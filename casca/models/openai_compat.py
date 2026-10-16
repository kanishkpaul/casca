import json
import time

import httpx

from casca.actions import ACTION_SCHEMA
from casca.config import config
from casca.models.base import VisionActionModel
from casca.prompts import SYSTEM_PROMPT, step_prompt
from casca.utils import encode_image_base64


class OpenAICompatProvider(VisionActionModel):
    """Any /chat/completions endpoint that accepts images: a hosted provider with your own key
    (OpenAI, OpenRouter, the Hugging Face router, Groq, Together) or a local server (Ollama,
    LM Studio, llama.cpp, vLLM). A key is sent only when one is set."""

    def __init__(self, base_url: str = config.BASE_URL, model: str = config.MODEL, api_key: str | None = config.API_KEY,
                 structured: bool = False):
        self.model = model
        self.url = base_url.rstrip("/").removesuffix("/chat/completions") + "/chat/completions"
        self.headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self.structured = structured
        self.destination = httpx.URL(self.url).host

    def propose_action(self, task, screenshot_bytes, step_index, history, screen) -> dict:
        prompt = step_prompt(task, step_index, history, screen)
        payload = {
            "model": self.model,
            "max_tokens": 512,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encode_image_base64(screenshot_bytes)}"}},
                ]},
            ],
        }
        if self.structured:
            # Constrained decoding: a server that supports it cannot produce an unparseable action.
            payload["response_format"] = {"type": "json_schema", "json_schema": {"name": "action", "schema": ACTION_SCHEMA}}
        for attempt in range(3):
            try:
                response = httpx.post(self.url, json=payload, headers=self.headers, timeout=60)
            except httpx.HTTPError as e:
                return {"error": f"{self.url}: {type(e).__name__}: {e}"}
            if response.status_code not in (429, 503) or attempt == 2:
                break
            time.sleep(2 ** attempt)
        if response.status_code != 200:
            return {"error": f"{self.url} returned {response.status_code}: {response.text[:300]}"}
        try:
            return {"raw_output": response.json()["choices"][0]["message"].get("content") or "",
                    "sent_bytes": len(json.dumps(payload))}
        except (ValueError, KeyError, IndexError):
            return {"error": f"unexpected response from {self.url}: {response.text[:300]}"}
