import asyncio
import threading
from typing import Optional, Tuple

import asyncpg

from .logging_utils import _log


_pool: Optional[asyncpg.Pool] = None
_pool_key: Optional[Tuple[str, int, str, str, str]] = None
_pool_loop: Optional[asyncio.AbstractEventLoop] = None  # event loop that owns the pool
# Use threading.Lock so it works safely across different asyncio event loops
# (e.g., when each Streamlit request runs in its own daemon thread / asyncio.run()).
_pool_lock = threading.Lock()


def _build_pool_key(host: str, port: int, database: str, user: str, password: str) -> Tuple[str, int, str, str, str]:
    return (host, port, database, user, password)


def _pool_is_usable() -> bool:
    """Return True only if the cached pool exists and its event loop is still running."""
    if _pool is None:
        return False
    if _pool_loop is None or _pool_loop.is_closed():
        return False
    return True


async def get_db_pool(
    host: str,
    port: int,
    database: str,
    user: str,
    password: str,
    min_size: int = 2,
    max_size: int = 20,
    command_timeout: int = 30,
) -> asyncpg.Pool:
    """Return a reusable asyncpg pool.

    Recreates the pool whenever:
    - DB config (host/port/db/user/password) changes
    - The event loop that owns the pool has been closed
      (e.g. after asyncio.run() finishes in a Streamlit worker thread)
    """
    global _pool, _pool_key, _pool_loop

    key = _build_pool_key(host, port, database, user, password)
    current_loop = asyncio.get_running_loop()

    # Fast path: pool exists, same config, same (open) event loop
    if _pool is not None and _pool_key == key and _pool_loop is current_loop:
        return _pool

    # Check under lock to decide whether we need to create a new pool
    old_pool = None
    with _pool_lock:
        # Re-check under lock
        if _pool is not None and _pool_key == key and _pool_loop is current_loop:
            return _pool

        if _pool is not None:
            reason = "DB config changed" if _pool_key != key else "event loop changed (new asyncio.run() context)"
            _log("POOL", f"Recreating pool: {reason}")
            old_pool = _pool

        _pool = None
        _pool_key = None
        _pool_loop = None

    # Close old pool outside the threading lock (await required)
    if old_pool is not None:
        try:
            await old_pool.close()
        except Exception as e:
            _log("POOL", f"Error closing old pool: {e}")

    # Create the new pool (await outside threading lock)
    try:
        new_pool = await asyncpg.create_pool(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            min_size=min_size,
            max_size=max_size,
            command_timeout=command_timeout,
            connection_class=asyncpg.connection.Connection,
        )
    except Exception as e:
        _log("POOL", f"Failed to create pool: {e}")
        raise

    # Store under lock; close duplicate if another thread beat us
    duplicate_pool = None
    with _pool_lock:
        if _pool is None:
            _pool = new_pool
            _pool_key = key
            _pool_loop = current_loop
            _log("POOL", f"Created asyncpg pool min={min_size} max={max_size} command_timeout={command_timeout}s")
        else:
            duplicate_pool = new_pool

    if duplicate_pool is not None:
        _log("POOL", "Duplicate pool detected, closing extra")
        try:
            await duplicate_pool.close()
        except Exception:
            pass

    return _pool


async def close_db_pool() -> None:
    """Close the global pool (useful for graceful shutdown/tests)."""
    global _pool, _pool_key, _pool_loop

    pool_to_close = None
    with _pool_lock:
        if _pool is not None:
            pool_to_close = _pool
            _pool = None
            _pool_key = None
            _pool_loop = None

    if pool_to_close is not None:
        await pool_to_close.close()
        _log("POOL", "Closed asyncpg pool")
