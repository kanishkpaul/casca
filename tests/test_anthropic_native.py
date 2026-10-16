from types import SimpleNamespace

import anthropic

from casca.models.anthropic_native import AnthropicProvider


def provider(model, reply):
    p = AnthropicProvider(model=model, api_key="test")
    p.client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(
        create=lambda **kw: p.sent.append(kw) or reply)))
    p.sent = []
    return p


def text_reply(text, stop="end_turn"):
    return SimpleNamespace(stop_reason=stop, stop_details=None, content=[SimpleNamespace(type="text", text=text)])


def test_request_caches_the_system_prompt_and_asks_for_fallbacks():
    p = provider("claude-opus-5-5", text_reply('{"action": "wait"}'))
    assert p.propose_action("t", b"png", 0, [], {"width": 1280, "height": 832})["raw_output"] == '{"action": "wait"}'
    sent = p.sent[0]
    assert sent["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert sent["fallbacks"] == "default" and sent["messages"][0]["content"][0]["type"] == "image"


def test_refusal_is_an_error_not_an_action():
    p = provider("claude-haiku-5-5", text_reply("", stop="refusal"))
    result = p.propose_action("t", b"png", 0, [], {"width": 1, "height": 1})
    assert "declined" in result["error"] and "fallbacks" not in p.sent[0]
