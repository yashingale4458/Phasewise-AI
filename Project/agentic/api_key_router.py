"""Smart API key router.

Manages a pool of API keys and routes every Gemini call to the healthiest,
least-loaded key.  Stats are persisted to database/api_key_stats.json so
they survive restarts.

Routing strategy
----------------
score(key) = tokens_this_hour * TOKEN_WEIGHT + consecutive_failures * FAILURE_WEIGHT
Lowest score wins.  Keys in cooldown are skipped; if all are in cooldown the
oldest cooldown expires first.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
_STATS_FILE = Path("database/api_key_stats.json")
_COOLDOWN_SECONDS = 65          # wait after a 429 before retrying a key
_HOUR_SECONDS = 3600
_TOKEN_WEIGHT = 1.0
_FAILURE_WEIGHT = 1_000.0
_MAX_RETRIES = 5                # how many keys to try before giving up

# API key variable names in .env  (GEMINI_API_KEY1 … GEMINI_API_KEY5)
_KEY_VARIABLE_NAMES = [
    "GEMINI_API_KEY1", "GEMINI_API_KEY2", "GEMINI_API_KEY3",
    "GEMINI_API_KEY4", "GEMINI_API_KEY5",
    # slots 6-10 are optional
    "GEMINI_API_KEY6", "GEMINI_API_KEY7", "GEMINI_API_KEY8",
    "GEMINI_API_KEY9", "GEMINI_API_KEY10",
]

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
_lock = threading.Lock()

def _empty_key_stat() -> dict[str, Any]:
    return {
        "tokens_this_hour": 0,
        "total_tokens": 0,
        "total_prompt_tokens": 0,
        "total_response_tokens": 0,
        "consecutive_failures": 0,
        "total_calls": 0,
        "total_errors": 0,
        "cooldown_until": 0.0,      # epoch seconds; 0 = not in cooldown
        "last_call_at": 0.0,
        "hour_window_start": time.time(),
        "status": "healthy",         # healthy | cooldown | failed
    }


def _load_stats() -> dict[str, dict[str, Any]]:
    """Load persisted stats from disk, filling gaps for new keys."""
    stats: dict[str, dict[str, Any]] = {}
    if _STATS_FILE.exists():
        try:
            raw = json.loads(_STATS_FILE.read_text())
            if isinstance(raw, dict):
                stats = raw
        except (json.JSONDecodeError, OSError):
            pass
    return stats


def _save_stats(stats: dict[str, dict[str, Any]]) -> None:
    try:
        _STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
        _STATS_FILE.write_text(json.dumps(stats, indent=2))
    except OSError:
        pass   # non-fatal


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class ApiKeyRouter:
    """Thread-safe router that picks the best key for each Gemini call."""

    def __init__(self) -> None:
        self._keys: list[str] = self._discover_keys()
        self._stats: dict[str, dict[str, Any]] = _load_stats()
        # Ensure every key has a stat entry
        for key in self._keys:
            if key not in self._stats:
                self._stats[key] = _empty_key_stat()
        _save_stats(self._stats)

    # ------------------------------------------------------------------
    @staticmethod
    def _discover_keys() -> list[str]:
        """Return every non-empty API key found in the environment."""
        keys: list[str] = []
        for var in _KEY_VARIABLE_NAMES:
            value = os.getenv(var, "").strip()
            if value and value not in keys:
                keys.append(value)
        # Fallback: legacy single-key variable
        legacy = os.getenv("GEMINI_API_KEY", "").strip()
        if legacy and legacy not in keys:
            keys.append(legacy)
        return keys

    # ------------------------------------------------------------------
    def _refresh_hour_window(self, key: str) -> None:
        """Reset the hourly token counter if the window has passed."""
        stat = self._stats[key]
        if time.time() - stat["hour_window_start"] >= _HOUR_SECONDS:
            stat["tokens_this_hour"] = 0
            stat["hour_window_start"] = time.time()

    def _score(self, key: str) -> float:
        stat = self._stats[key]
        self._refresh_hour_window(key)
        return (stat["tokens_this_hour"] * _TOKEN_WEIGHT
                + stat["consecutive_failures"] * _FAILURE_WEIGHT)

    def _update_status(self, key: str) -> None:
        stat = self._stats[key]
        now = time.time()
        if stat["consecutive_failures"] >= 5:
            stat["status"] = "failed"
        elif stat["cooldown_until"] > now:
            stat["status"] = "cooldown"
        else:
            stat["status"] = "healthy"

    # ------------------------------------------------------------------
    def pick_key(self) -> str:
        """Return the API key to use for the next call.

        Raises RuntimeError if no keys are configured.
        """
        with _lock:
            if not self._keys:
                raise RuntimeError(
                    "No Gemini API keys found. Add GEMINI_API_KEY1 … GEMINI_API_KEY5 to .env"
                )
            now = time.time()
            available = [k for k in self._keys if self._stats[k]["cooldown_until"] <= now]
            if not available:
                # All in cooldown — pick the one whose cooldown expires soonest
                available = sorted(self._keys, key=lambda k: self._stats[k]["cooldown_until"])
            return min(available, key=self._score)

    def record_success(self, key: str, prompt_tokens: int,
                       response_tokens: int, total_tokens: int) -> None:
        """Update stats after a successful call."""
        with _lock:
            if key not in self._stats:
                self._stats[key] = _empty_key_stat()
            stat = self._stats[key]
            self._refresh_hour_window(key)
            stat["tokens_this_hour"] += total_tokens
            stat["total_tokens"] += total_tokens
            stat["total_prompt_tokens"] += prompt_tokens
            stat["total_response_tokens"] += response_tokens
            stat["consecutive_failures"] = 0
            stat["total_calls"] += 1
            stat["last_call_at"] = time.time()
            stat["cooldown_until"] = 0.0
            self._update_status(key)
            _save_stats(self._stats)

    def record_rate_limit(self, key: str) -> None:
        """Mark a key as cooling down after a 429."""
        with _lock:
            if key not in self._stats:
                self._stats[key] = _empty_key_stat()
            stat = self._stats[key]
            stat["cooldown_until"] = time.time() + _COOLDOWN_SECONDS
            stat["consecutive_failures"] += 1
            stat["total_errors"] += 1
            self._update_status(key)
            _save_stats(self._stats)

    def record_error(self, key: str) -> None:
        """Mark a failed call that was not a rate-limit."""
        with _lock:
            if key not in self._stats:
                self._stats[key] = _empty_key_stat()
            stat = self._stats[key]
            stat["consecutive_failures"] += 1
            stat["total_errors"] += 1
            self._update_status(key)
            _save_stats(self._stats)

    # ------------------------------------------------------------------
    def get_all_stats(self) -> list[dict[str, Any]]:
        """Return a snapshot of every key's stats for the dashboard."""
        with _lock:
            now = time.time()
            result = []
            for idx, key in enumerate(self._keys, 1):
                stat = dict(self._stats.get(key, _empty_key_stat()))
                stat["key_index"] = idx
                stat["key_label"] = f"Key {idx}"
                # Mask actual key value for display
                stat["key_preview"] = key[:8] + "…" if len(key) > 8 else key
                # Recompute live status
                if stat["consecutive_failures"] >= 5:
                    stat["status"] = "failed"
                elif stat["cooldown_until"] > now:
                    stat["status"] = "cooldown"
                    stat["cooldown_remaining"] = max(0, int(stat["cooldown_until"] - now))
                else:
                    stat["status"] = "healthy"
                    stat["cooldown_remaining"] = 0
                result.append(stat)
            return result

    def key_count(self) -> int:
        return len(self._keys)

    def healthy_count(self) -> int:
        with _lock:
            now = time.time()
            return sum(
                1 for k in self._keys
                if self._stats.get(k, {}).get("cooldown_until", 0) <= now
                and self._stats.get(k, {}).get("consecutive_failures", 0) < 5
            )


# Singleton — imported by agents.py
_router: ApiKeyRouter | None = None


def get_router() -> ApiKeyRouter:
    global _router
    if _router is None:
        _router = ApiKeyRouter()
    return _router
