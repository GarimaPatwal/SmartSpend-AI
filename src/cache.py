"""
cache.py — Simple file-based cache for NL→SQL results.

Saves generated SQL to a JSON file keyed by a hash of the question.
Benefits:
  - Identical questions never hit the API twice (saves quota + latency)
  - Works offline for previously seen questions
  - Survives app restarts

Day 4 focus: rate limit handling + latency optimization.
"""

import json
import hashlib
from pathlib import Path

CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / "sql_cache.json"


def _load() -> dict:
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2), encoding="utf-8")


def _key(question: str) -> str:
    """Normalise + hash the question so minor whitespace differences still hit cache."""
    normalised = " ".join(question.strip().lower().split())
    return hashlib.sha256(normalised.encode()).hexdigest()[:16]


def get(question: str) -> str | None:
    """Returns cached SQL for this question, or None if not cached."""
    return _load().get(_key(question))


def set(question: str, sql: str) -> None:
    """Stores SQL in the cache for this question."""
    cache = _load()
    cache[_key(question)] = sql
    _save(cache)


def clear() -> None:
    """Wipes the entire cache (useful for testing)."""
    if CACHE_PATH.exists():
        CACHE_PATH.unlink()
