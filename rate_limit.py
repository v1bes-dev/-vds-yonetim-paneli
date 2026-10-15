# rate_limit.py — Redis ile sabit pencereli (fixed-window) hiz sinirlama.
# Redis yoksa process-ici bir fallback'e duser (tek instance icin calisir,
# birden fazla sunucu/instance'da GERCEK limit icin Redis zorunludur).
import os
import time
import threading

MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX", "10"))
WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW", "60"))

_redis_client = None
try:
    import redis
    _redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), socket_connect_timeout=1)
    _redis_client.ping()
except Exception:
    _redis_client = None

_mem_lock = threading.Lock()
_mem_counters: dict[str, tuple[int, float]] = {}  # key -> (count, window_start)


class RateLimitExceeded(Exception):
    pass


def _check_redis(key: str) -> None:
    rkey = f"ratelimit:{key}:{int(time.time()) // WINDOW_SECONDS}"
    count = _redis_client.incr(rkey)
    if count == 1:
        _redis_client.expire(rkey, WINDOW_SECONDS)
    if count > MAX_REQUESTS:
        raise RateLimitExceeded(f"{key} icin istek siniri asildi ({MAX_REQUESTS}/{WINDOW_SECONDS}s)")


def _check_memory(key: str) -> None:
    now = time.time()
    window = now // WINDOW_SECONDS
    with _mem_lock:
        count, stored_window = _mem_counters.get(key, (0, window))
        if stored_window != window:
            count, stored_window = 0, window
        count += 1
        _mem_counters[key] = (count, stored_window)
        if count > MAX_REQUESTS:
            raise RateLimitExceeded(f"{key} icin istek siniri asildi ({MAX_REQUESTS}/{WINDOW_SECONDS}s)")


def check_rate_limit(key: str) -> None:
    """key: genelde chat_id. Limit asildiysa RateLimitExceeded firlatir."""
    if _redis_client is not None:
        _check_redis(key)
    else:
        _check_memory(key)
