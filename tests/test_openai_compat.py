import httpx
import pytest

from casca.models.openai_compat import OpenAICompatProvider

SCREEN = {"width": 1280, "height": 832}


@pytest.mark.parametrize("base", ["https://router.huggingface.co/v1", "https://router.huggingface.co/v1/",
                                  "https://router.huggingface.co/v1/chat/completions"])
def test_url_is_built_once(base):
    assert OpenAICompatProvider(base, "m").url == "https://router.huggingface.co/v1/chat/completions"


def test_local_endpoint_sends_no_key():
    assert OpenAICompatProvider("http://localhost:11434/v1", "qwen3-vl:8b", None).headers == {}


def reply(monkeypatch, *responses):
    calls = iter(responses)
    monkeypatch.setattr(httpx, "post", lambda *a, **k: next(calls))
    monkeypatch.setattr("time.sleep", lambda s: None)
    return OpenAICompatProvider("http://x/v1", "m").propose_action("t", b"png", 0, [], SCREEN)


def test_rate_limit_is_retried(monkeypatch):
    ok = httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})
    assert reply(monkeypatch, httpx.Response(429), ok)["raw_output"] == "{}"


def test_http_error_names_status_and_body(monkeypatch):
    assert reply(monkeypatch, httpx.Response(400, text="no images"))["error"] == "http://x/v1/chat/completions returned 400: no images"


def test_structured_profile_sends_the_action_schema(monkeypatch):
    sent = {}
    ok = httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})
    monkeypatch.setattr(httpx, "post", lambda url, json, **k: sent.update(json) or ok)
    OpenAICompatProvider("http://x/v1", "m", None, structured=True).propose_action("t", b"png", 0, [], SCREEN)
    assert "click" in str(sent["response_format"]["json_schema"]["schema"])
