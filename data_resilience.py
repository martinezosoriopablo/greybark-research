# -*- coding: utf-8 -*-
"""
Greybark Research - Data Resilience
=====================================

Infrastructure for robust data collection:
- @retry_with_backoff: exponential retry (3 attempts default)
- @timeout_call: per-call timeout (30s default)
- ResponseCache: disk-backed cache with per-source TTL

Used by council_data_collector.py to make data collection fault-tolerant.
"""

import os
import json
import time
import hashlib
import functools
import threading
import traceback
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Optional, Tuple


# =============================================================================
# CACHE DIRECTORY
# =============================================================================

CACHE_DIR = Path(__file__).parent / "cache" / "data_resilience"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


# =============================================================================
# DEFAULT TTLs (seconds)
# =============================================================================

SOURCE_TTL: Dict[str, int] = {
    'fred':          4 * 3600,     # 4 hours
    'bcch':          4 * 3600,     # 4 hours
    'bcch_extended': 4 * 3600,     # 4 hours
    'yfinance':      1 * 3600,     # 1 hour
    'bea':          24 * 3600,     # 24 hours
    'imf':           7 * 24 * 3600,  # 7 days
    'oecd':         24 * 3600,     # 24 hours
    'nyfed':         4 * 3600,     # 4 hours
    'ecb':           4 * 3600,     # 4 hours
    'bcrp':          4 * 3600,     # 4 hours
    'akshare':      24 * 3600,     # 24 hours
    'alphavantage':  1 * 3600,     # 1 hour
    'bloomberg':     1 * 3600,     # 1 hour (local Excel, fast)
    'sovereign':     4 * 3600,     # 4 hours
    'regime':        1 * 3600,     # 1 hour
    'inflation':     4 * 3600,     # 4 hours
    'chile':         4 * 3600,     # 4 hours
    'china':         4 * 3600,     # 4 hours
    'risk':          1 * 3600,     # 1 hour
    'breadth':       1 * 3600,     # 1 hour
    'leading':       4 * 3600,     # 4 hours
    'cpi_fiscal':    4 * 3600,     # 4 hours
    'default':       2 * 3600,     # 2 hours fallback
}


def get_ttl(source: str) -> int:
    """Get TTL for a data source."""
    return SOURCE_TTL.get(source, SOURCE_TTL['default'])


# =============================================================================
# RETRY DECORATOR
# =============================================================================

def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exceptions: Tuple = (Exception,),
    on_retry: Optional[Callable] = None,
):
    """
    Decorator: retry a function with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts (total calls = max_retries + 1)
        base_delay: Initial delay in seconds (doubles each retry)
        max_delay: Maximum delay cap
        exceptions: Tuple of exception types to catch
        on_retry: Optional callback(attempt, exception, delay) called before each retry
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        if on_retry:
                            on_retry(attempt + 1, e, delay)
                        time.sleep(delay)
                    # else: all retries exhausted, fall through
            raise last_exception
        return wrapper
    return decorator


# =============================================================================
# TIMEOUT WRAPPER
# =============================================================================

class _TimeoutError(Exception):
    """Raised when a function call exceeds its timeout."""
    pass


def timeout_call(func: Callable, timeout_sec: float = 30.0, *args, **kwargs) -> Any:
    """
    Run a function with a timeout.

    Uses threading to enforce timeout on Windows (signal.alarm not available).

    Args:
        func: Function to call
        timeout_sec: Maximum seconds to wait
        *args, **kwargs: Arguments to pass to func

    Returns:
        The function's return value

    Raises:
        _TimeoutError: If the function doesn't complete in time
        Exception: Any exception raised by the function
    """
    result = [None]
    error = [None]

    def target():
        try:
            result[0] = func(*args, **kwargs)
        except Exception as e:
            error[0] = e

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout=timeout_sec)

    if thread.is_alive():
        raise _TimeoutError(
            f"{func.__name__} timed out after {timeout_sec}s"
        )

    if error[0] is not None:
        raise error[0]

    return result[0]


# =============================================================================
# RESPONSE CACHE
# =============================================================================

class ResponseCache:
    """
    Disk-backed JSON cache with per-key TTL.

    Each cache entry is stored as a separate JSON file in CACHE_DIR.
    Structure: { "timestamp": ISO, "ttl": seconds, "data": ... }
    """

    def __init__(self, cache_dir: Path = CACHE_DIR):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._memory_cache: Dict[str, Tuple[float, Any]] = {}

    def _key_to_path(self, key: str) -> Path:
        """Convert a cache key to a file path."""
        safe = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{safe}.json"

    def get(self, key: str) -> Optional[Any]:
        """
        Get a cached value if it exists and hasn't expired.

        Returns None if not cached or expired.
        """
        # Check memory cache first (faster than disk)
        if key in self._memory_cache:
            expiry, data = self._memory_cache[key]
            if time.time() < expiry:
                return data
            else:
                del self._memory_cache[key]

        # Check disk cache
        path = self._key_to_path(key)
        if not path.exists():
            return None

        try:
            with open(path, 'r', encoding='utf-8') as f:
                entry = json.load(f)

            ts = datetime.fromisoformat(entry['timestamp'])
            ttl = entry.get('ttl', SOURCE_TTL['default'])
            age = (datetime.now() - ts).total_seconds()

            if age > ttl:
                # Expired
                path.unlink(missing_ok=True)
                return None

            data = entry['data']
            # Store in memory for faster subsequent access
            self._memory_cache[key] = (time.time() + (ttl - age), data)
            return data

        except (json.JSONDecodeError, KeyError, OSError):
            path.unlink(missing_ok=True)
            return None

    def set(self, key: str, data: Any, ttl: Optional[int] = None) -> None:
        """
        Store a value in the cache.

        Args:
            key: Cache key (e.g., "fred_macro_usa")
            data: JSON-serializable data
            ttl: Time-to-live in seconds (uses source default if None)
        """
        if ttl is None:
            ttl = SOURCE_TTL['default']

        entry = {
            'timestamp': datetime.now().isoformat(),
            'ttl': ttl,
            'data': data,
        }

        path = self._key_to_path(key)
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(entry, f, ensure_ascii=False, default=str)

            # Also store in memory
            self._memory_cache[key] = (time.time() + ttl, data)
        except (OSError, TypeError) as e:
            # Cache write failure is non-fatal
            pass

    def invalidate(self, key: str) -> None:
        """Remove a specific cache entry."""
        self._memory_cache.pop(key, None)
        path = self._key_to_path(key)
        path.unlink(missing_ok=True)

    def clear(self) -> int:
        """Clear all cache entries. Returns count of entries removed."""
        count = 0
        self._memory_cache.clear()
        for f in self.cache_dir.glob("*.json"):
            f.unlink(missing_ok=True)
            count += 1
        return count

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        files = list(self.cache_dir.glob("*.json"))
        total_size = sum(f.stat().st_size for f in files)
        expired = 0
        valid = 0

        for f in files:
            try:
                with open(f, 'r', encoding='utf-8') as fh:
                    entry = json.load(fh)
                ts = datetime.fromisoformat(entry['timestamp'])
                ttl = entry.get('ttl', SOURCE_TTL['default'])
                if (datetime.now() - ts).total_seconds() > ttl:
                    expired += 1
                else:
                    valid += 1
            except Exception:
                expired += 1

        return {
            'total_entries': len(files),
            'valid': valid,
            'expired': expired,
            'memory_entries': len(self._memory_cache),
            'disk_size_kb': round(total_size / 1024, 1),
        }


# =============================================================================
# RESILIENT FETCH HELPER
# =============================================================================

# Module-level cache instance (shared across collector)
_cache = ResponseCache()


def resilient_fetch(
    source_name: str,
    fetch_fn: Callable,
    *args,
    cache_key: Optional[str] = None,
    ttl: Optional[int] = None,
    timeout_sec: float = 90.0,
    max_retries: int = 3,
    verbose_fn: Optional[Callable] = None,
    **kwargs,
) -> Any:
    """
    Fetch data with caching, retry, and timeout.

    This is the main entry point for resilient data fetching.

    Args:
        source_name: Source identifier (for TTL lookup and logging)
        fetch_fn: The actual data-fetching function
        *args: Positional args for fetch_fn
        cache_key: Cache key (auto-generated from source_name if None)
        ttl: Cache TTL override (uses SOURCE_TTL[source_name] if None)
        timeout_sec: Timeout per attempt in seconds
        max_retries: Number of retries on failure
        verbose_fn: Optional print function for logging
        **kwargs: Keyword args for fetch_fn

    Returns:
        The fetched data (from cache or fresh)

    Raises:
        Exception: If all retries fail and no cache is available
    """
    if cache_key is None:
        cache_key = source_name

    if ttl is None:
        ttl = get_ttl(source_name)

    # 1. Check cache
    cached = _cache.get(cache_key)
    if cached is not None:
        if verbose_fn:
            verbose_fn(f"  [CACHE] {source_name}: usando datos en cache")
        return cached

    # 2. Fetch with retry + timeout
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            data = timeout_call(fetch_fn, timeout_sec, *args, **kwargs)

            # Validate: reject error dicts
            if isinstance(data, dict) and 'error' in data and len(data) == 1:
                raise ValueError(f"Source returned error: {data['error']}")

            # 3. Store in cache
            _cache.set(cache_key, data, ttl=ttl)
            return data

        except _TimeoutError as e:
            last_error = e
            if verbose_fn:
                verbose_fn(f"  [TIMEOUT] {source_name} attempt {attempt+1}/{max_retries+1}: {e}")
            if attempt < max_retries:
                delay = min(1.0 * (2 ** attempt), 15.0)
                time.sleep(delay)

        except Exception as e:
            last_error = e
            if verbose_fn:
                verbose_fn(f"  [RETRY] {source_name} attempt {attempt+1}/{max_retries+1}: {type(e).__name__}: {e}")
            if attempt < max_retries:
                delay = min(1.0 * (2 ** attempt), 15.0)
                time.sleep(delay)

    # 4. All retries failed — check for stale cache as last resort
    stale = _cache_get_stale(cache_key)
    if stale is not None:
        if verbose_fn:
            verbose_fn(f"  [STALE] {source_name}: usando cache expirado como fallback")
        return stale

    # 5. No cache, no success — raise
    raise last_error


def _cache_get_stale(key: str) -> Optional[Any]:
    """Get a cache entry even if expired (stale data as last resort)."""
    path = _cache._key_to_path(key)
    if not path.exists():
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            entry = json.load(f)
        return entry.get('data')
    except Exception:
        return None


def get_cache() -> ResponseCache:
    """Get the module-level cache instance."""
    return _cache
