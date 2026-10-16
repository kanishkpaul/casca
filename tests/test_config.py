import importlib

import pytest


def test_bad_number_names_the_variable(monkeypatch):
    monkeypatch.setenv("CASCA_MAX_STEPS", "twenty")
    with pytest.raises(ValueError, match="CASCA_MAX_STEPS='twenty'"):
        importlib.reload(importlib.import_module("casca.config"))
    monkeypatch.delenv("CASCA_MAX_STEPS")
    importlib.reload(importlib.import_module("casca.config"))
