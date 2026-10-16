import pytest

from casca.models.openai_compat import OpenAICompatProvider
from casca.profiles import load_profile, make_model, resolve_key


def test_profile_builds_a_keyless_local_model(tmp_path):
    path = tmp_path / "casca.toml"
    path.write_text('[profiles.local]\nbase_url = "http://127.0.0.1:8080/v1"\nmodel = "qwen3-vl-8b"\nkey = "none"\n')
    model = make_model(load_profile("local", path))
    assert isinstance(model, OpenAICompatProvider) and model.headers == {}


def test_missing_profile_lists_the_known_ones(tmp_path):
    path = tmp_path / "casca.toml"
    path.write_text('[profiles.a]\nbase_url = "x"\nmodel = "m"\n')
    with pytest.raises(ValueError, match="known: a"):
        load_profile("b", path)


def test_key_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv("MY_KEY", "sk-test")
    assert resolve_key("env:MY_KEY") == "sk-test"
    with pytest.raises(ValueError):
        resolve_key("sk-literal-key")
