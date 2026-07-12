"""Tests for app/state.py's cache, rate limiter, and idempotency logic."""

import app.state as state_module
from app.state import LanguageCache, LanguagePreference, RateLimiter, SeenMessages


def _fake_clock(monkeypatch, start=0.0):
    fake_time = [start]
    monkeypatch.setattr(state_module.time, "monotonic", lambda: fake_time[0])
    return fake_time


def test_language_cache_returns_value_before_expiry(monkeypatch):
    _fake_clock(monkeypatch)
    cache = LanguageCache(ttl_seconds=10)
    cache.set("+65123", "a summary")
    assert cache.get("+65123") == "a summary"


def test_language_cache_expires_after_ttl(monkeypatch):
    fake_time = _fake_clock(monkeypatch)
    cache = LanguageCache(ttl_seconds=10)
    cache.set("+65123", "a summary")
    fake_time[0] += 11
    assert cache.get("+65123") is None


def test_language_cache_missing_sender_returns_none():
    cache = LanguageCache()
    assert cache.get("+65999") is None


def test_language_preference_returns_none_when_unset():
    preference = LanguagePreference()
    assert preference.get("+65123") is None


def test_language_preference_remembers_set_value():
    preference = LanguagePreference()
    preference.set("+65123", "zh")
    assert preference.get("+65123") == "zh"


def test_rate_limiter_allows_up_to_max(monkeypatch):
    _fake_clock(monkeypatch)
    limiter = RateLimiter(max_requests=2, window_seconds=60)
    assert limiter.allow("+65123") is True
    assert limiter.allow("+65123") is True
    assert limiter.allow("+65123") is False


def test_rate_limiter_resets_after_window(monkeypatch):
    fake_time = _fake_clock(monkeypatch)
    limiter = RateLimiter(max_requests=1, window_seconds=60)
    assert limiter.allow("+65123") is True
    assert limiter.allow("+65123") is False
    fake_time[0] += 61
    assert limiter.allow("+65123") is True


def test_rate_limiter_tracks_senders_independently(monkeypatch):
    _fake_clock(monkeypatch)
    limiter = RateLimiter(max_requests=1, window_seconds=60)
    assert limiter.allow("+65111") is True
    assert limiter.allow("+65222") is True


def test_seen_messages_detects_duplicate(monkeypatch):
    _fake_clock(monkeypatch)
    seen = SeenMessages(ttl_seconds=60)
    assert seen.seen_before("SM123") is False
    assert seen.seen_before("SM123") is True


def test_seen_messages_expires(monkeypatch):
    fake_time = _fake_clock(monkeypatch)
    seen = SeenMessages(ttl_seconds=60)
    assert seen.seen_before("SM123") is False
    fake_time[0] += 61
    assert seen.seen_before("SM123") is False
