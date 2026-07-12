import pytest

from pipeline.config import require_env


def test_require_env_returns_value(monkeypatch):
    monkeypatch.setenv("SOME_VAR", "value")
    assert require_env("SOME_VAR") == "value"


def test_require_env_raises_when_unset(monkeypatch):
    monkeypatch.delenv("SOME_VAR", raising=False)
    with pytest.raises(RuntimeError):
        require_env("SOME_VAR")
