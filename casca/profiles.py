"""Profiles name one model each in casca.toml, so a model's quirks live in data, not code:

    [profiles.local-qwen]
    adapter = "openai_compat"          # or "anthropic" (pip install "casca[anthropic]")
    base_url = "http://127.0.0.1:8080/v1"
    model = "qwen3-vl-8b"
    key = "none"                       # or "env:OPENAI_API_KEY", or "keychain:casca/openrouter"
    coords = "norm1000"                # or "image_px"
"""
import os
import tomllib
from pathlib import Path

from platformdirs import user_config_dir

CONFIG = Path(os.getenv("CASCA_CONFIG") or Path(user_config_dir("casca")) / "casca.toml")


def load_profile(name: str, path: Path = CONFIG) -> dict:
    profiles = tomllib.loads(path.read_text()).get("profiles", {}) if path.exists() else {}
    if name not in profiles:
        raise ValueError(f"no profile {name!r} in {path}; known: {', '.join(profiles) or 'none'}")
    return profiles[name]


def resolve_key(ref: str | None) -> str | None:
    """Keys are named by reference so casca.toml never holds one."""
    if not ref or ref == "none":
        return None
    kind, _, where = ref.partition(":")
    if kind == "env":
        return os.getenv(where)
    if kind == "keychain":
        import keyring
        service, _, account = where.partition("/")
        return keyring.get_password(service, account)
    raise ValueError(f"key {ref!r} must be env:NAME, keychain:service/account or none")


def make_model(profile: dict):
    key = resolve_key(profile.get("key"))
    adapter = profile.get("adapter", "openai_compat")
    if adapter == "openai_compat":
        from casca.models.openai_compat import OpenAICompatProvider
        return OpenAICompatProvider(profile["base_url"], profile["model"], key)
    if adapter == "anthropic":
        from casca.models.anthropic_native import AnthropicProvider
        return AnthropicProvider(profile.get("base_url"), profile["model"], key, profile.get("effort"))
    raise ValueError(f"unknown adapter {adapter!r}; known: openai_compat, anthropic")
