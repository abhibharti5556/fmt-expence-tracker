"""In-memory failed-login tracking and temporary lockout.

Deliberately simple (a dict guarded by a lock, not a DB table or Redis):
this app runs as a single process today, so process memory is a valid
store. It resets on restart and won't be shared across multiple worker
processes — acceptable for the current scale, but note this in
architecture.md/rules.md if the app ever moves to a multi-worker
production server, since the lockout would then be per-worker, not
global.
"""

import threading
import time

_lock = threading.Lock()
_attempts = {}  # key -> list[float] (timestamps of recent failures)
_locked_until = {}  # key -> float (epoch seconds)


def _key(scope, identifier, ip):
    return f"{scope}:{identifier.lower()}:{ip}"


def is_locked_out(scope, identifier, ip):
    """Returns remaining lockout seconds (float > 0) if locked, else None."""
    key = _key(scope, identifier, ip)
    with _lock:
        until = _locked_until.get(key)
        if until is None:
            return None
        remaining = until - time.time()
        if remaining <= 0:
            _locked_until.pop(key, None)
            _attempts.pop(key, None)
            return None
        return remaining


def record_failure(scope, identifier, ip, max_attempts, window_minutes, lockout_minutes):
    """Record a failed attempt; lock the identity out if it crosses the
    threshold within the sliding window. Returns True if now locked out."""
    key = _key(scope, identifier, ip)
    now = time.time()
    window_seconds = window_minutes * 60

    with _lock:
        recent = [t for t in _attempts.get(key, []) if now - t < window_seconds]
        recent.append(now)
        _attempts[key] = recent

        if len(recent) >= max_attempts:
            _locked_until[key] = now + lockout_minutes * 60
            _attempts.pop(key, None)
            return True
    return False


def record_success(scope, identifier, ip):
    key = _key(scope, identifier, ip)
    with _lock:
        _attempts.pop(key, None)
        _locked_until.pop(key, None)
