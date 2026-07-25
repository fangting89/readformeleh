"""In-memory state for the webhook: language cache/preference, rate
limiting, and idempotency."""

import time


class LanguageCache:
    """Caches the last summary text per sender for the language-toggle
    re-render, so re-rendering in another language doesn't need a second
    image upload."""

    def __init__(self, ttl_seconds: float = 600):
        self._ttl = ttl_seconds
        self._entries: dict[str, tuple[str, float]] = {}

    def set(self, sender: str, summary: str) -> None:
        """Caches a summary for a sender, resetting its TTL.

        Args:
            sender: The sender's identifier (e.g. WhatsApp number).
            summary: The summary text to cache.
        """
        self._entries[sender] = (summary, time.monotonic() + self._ttl)

    def get(self, sender: str) -> str | None:
        """Returns a sender's cached summary if it hasn't expired.

        Args:
            sender: The sender's identifier.

        Returns:
            The cached summary, or None if there isn't one or it's expired
            (expired entries are also evicted from the cache here).
        """
        entry = self._entries.get(sender)
        if entry is None:
            return None
        summary, expires_at = entry
        if time.monotonic() > expires_at:
            del self._entries[sender]
            return None
        return summary


class LanguagePreference:
    """Remembers a sender's language once they've explicitly signalled
    it (replying "中文"/"English" etc.), so later summaries can be
    single-language instead of bilingual. No TTL — unlike the last-summary
    cache, a person's language doesn't go stale after 10 minutes. This is
    a deliberate, documented exception to the stateless design, same as
    LanguageCache; it doesn't persist across process restarts."""

    def __init__(self):
        self._preferences: dict[str, str] = {}

    def set(self, sender: str, lang: str) -> None:
        """Remembers a sender's language preference.

        Args:
            sender: The sender's identifier.
            lang: The language code to remember, e.g. "en" or "zh".
        """
        self._preferences[sender] = lang

    def get(self, sender: str) -> str | None:
        """Returns a sender's remembered language preference.

        Args:
            sender: The sender's identifier.

        Returns:
            The remembered language code, or None if never set.
        """
        return self._preferences.get(sender)


class RateLimiter:
    """Bounds requests per sender in a rolling time window — the cost
    guardrail against spam or a stuck retry loop."""

    def __init__(self, max_requests: int = 5, window_seconds: float = 600):
        self._max_requests = max_requests
        self._window = window_seconds
        self._requests: dict[str, list[float]] = {}

    def allow(self, sender: str) -> bool:
        """Checks whether a sender is still within their rate limit.

        Records the request's timestamp as a side effect if allowed, so
        the caller doesn't need a separate "record this request" step.

        Args:
            sender: The sender's identifier.

        Returns:
            True if the sender has made fewer than `max_requests` requests
            in the last `window_seconds`, False otherwise.
        """
        now = time.monotonic()
        cutoff = now - self._window
        timestamps = [t for t in self._requests.get(sender, []) if t > cutoff]
        if len(timestamps) >= self._max_requests:
            self._requests[sender] = timestamps
            return False
        timestamps.append(now)
        self._requests[sender] = timestamps
        return True


class ConsecutiveFailureCount:
    """Tracks consecutive unreadable/degraded outcomes per sender, so a
    string of failed photos can escalate the retry message beyond a
    generic lighting tip to suggesting in-person help (see
    docs/DESIGN.md's evidence base on staff time/stigma). TTL-bounded like
    the other stores — a failure streak from an old session shouldn't
    silently count toward a new one."""

    def __init__(self, ttl_seconds: float = 1800):
        self._ttl = ttl_seconds
        self._counts: dict[str, tuple[int, float]] = {}

    def record_failure(self, sender: str) -> int:
        """Increments a sender's consecutive-failure count.

        Starts a fresh streak of 1 if the previous one has expired or
        never existed.

        Args:
            sender: The sender's identifier.

        Returns:
            The sender's current consecutive-failure count after this one.
        """
        now = time.monotonic()
        count, expires_at = self._counts.get(sender, (0, 0.0))
        if now > expires_at:
            count = 0
        count += 1
        self._counts[sender] = (count, now + self._ttl)
        return count

    def reset(self, sender: str) -> None:
        """Clears a sender's failure streak.

        Call whenever a photo comes back legible (summarized
        successfully, or classified suspicious), not just on an outright
        success.

        Args:
            sender: The sender's identifier.
        """
        self._counts.pop(sender, None)


class SeenMessages:
    """Tracks recently-processed Twilio MessageSids so a webhook retry
    (Twilio resends if it doesn't get a fast response) doesn't trigger a
    duplicate, separately-billed pipeline run."""

    def __init__(self, ttl_seconds: float = 300):
        self._ttl = ttl_seconds
        self._seen: dict[str, float] = {}

    def seen_before(self, message_sid: str) -> bool:
        """Checks whether a message SID has already been processed.

        Records the SID as seen as a side effect, whether or not it was
        already present.

        Args:
            message_sid: Twilio's unique ID for the inbound message.

        Returns:
            True if this SID was already seen (within its TTL), False if
            this is the first time.
        """
        now = time.monotonic()
        expires_at = self._seen.get(message_sid)
        if expires_at is not None and now <= expires_at:
            return True
        self._seen[message_sid] = now + self._ttl
        return False
