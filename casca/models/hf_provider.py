import httpx
import base64
from casca.models.base import VisionActionModel
from casca.prompts import SYSTEM_PROMPT
from casca.config import config

class HFVisionProvider(VisionActionModel):
    def __init__(self):
        self.token = config.HF_API_TOKEN
        self.model_id = config.HF_MODEL_ID
        
        if not self.token:
            raise ValueError("HF_API_TOKEN is not set. Please set it in your .env file.")
            
        self.api_url = config.HF_API_URL or f"https://api-inference.huggingface.co/models/{self.model_id}"

        if not self.api_url.endswith("/v1/chat/completions"):
            self.api_url = self.api_url.rstrip("/") + "/v1/chat/completions"

    def _encode_image(self, screenshot_bytes: bytes) -> str:
        return base64.b64encode(screenshot_bytes).decode("utf-8")

    def propose_action(
        self,
        task: str,
        screenshot_bytes: bytes,
        step_index: int,
        history: list[dict],
        screen: dict,
    ) -> dict:
        
        img_b64 = self._encode_image(screenshot_bytes)
        
        # Build prompt
        history_str = ""
        for h in history[-5:]: # last 5 actions
            history_str += f"- Step {h['step']}: Action: {h['action']}, Result: {h['execution'].get('status')}\n"
            
        user_prompt = f"""Task: {task}
Screen size: width={screen['width']}, height={screen['height']}
Step index: {step_index}
Recent history:
{history_str if history_str else "None"}

Please provide the next action in JSON format.
"""
        
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"{SYSTEM_PROMPT}\n\n{user_prompt}"
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{img_b64}"
                        }
                    }
                ]
            }
        ]
        
        payload = {
            "model": self.model_id,
            "messages": messages,
            "max_tokens": 512,
            "stream": False
        }
        
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(self.api_url, json=payload, headers=headers)
                
            if response.status_code == 401:
                return {"error": "Unauthorized. Check HF_API_TOKEN."}
            elif response.status_code == 404:
                return {"error": f"Model {self.model_id} not found."}
            elif response.status_code == 400:
                # Often image format issues or model doesn't support images
                raise RuntimeError(f"The selected Hugging Face endpoint did not accept the request. Error: {response.text}")
            
            response.raise_for_status()
            
            result = response.json()
            if "choices" in result and len(result["choices"]) > 0:
                output = result["choices"][0].get("message", {}).get("content", "")
            else:
                return {"error": f"Unexpected response format from HF API: {result}"}
                
            return {"raw_output": output}
            
        except httpx.TimeoutException:
            return {"error": "Request timed out."}
        except httpx.HTTPStatusError as e:
            return {"error": f"HTTP Error: {e}"}
        except Exception as e:
            return {"error": f"Unexpected error: {e}"}
