"""Intelligent caching system with SQLite backend."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional


class CacheManager:
    """SQLite-based cache manager for API responses."""

    def __init__(self, db_path: Path | str = "data/cache.db") -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _init_database(self) -> None:
        """Initialize the cache database schema."""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    expires_at REAL NOT NULL,
                    created_at REAL NOT NULL
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_expires_at 
                ON cache(expires_at)
            """)
            
            conn.commit()

    def get(self, key: str) -> Optional[Any]:
        """Retrieve cached value if not expired.
        
        Parameters
        ----------
        key : str
            Cache key
            
        Returns
        -------
        Optional[Any] : Cached value or None if expired/missing
        """
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute(
                "SELECT value, expires_at FROM cache WHERE key = ?",
                (key,)
            )
            row = cursor.fetchone()
            
            if not row:
                return None
            
            value_json, expires_at = row
            
            # Check if expired
            if time.time() > expires_at:
                self.delete(key)
                return None
            
            try:
                return json.loads(value_json)
            except json.JSONDecodeError:
                return None

    def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        """Store value in cache with TTL.
        
        Parameters
        ----------
        key : str
            Cache key
        value : Any
            Value to cache (must be JSON serializable)
        ttl : int
            Time to live in seconds (default: 1 hour)
        """
        now = time.time()
        expires_at = now + ttl
        
        try:
            value_json = json.dumps(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Value must be JSON serializable: {exc}") from exc
        
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO cache (key, value, expires_at, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (key, value_json, expires_at, now)
            )
            conn.commit()

    def delete(self, key: str) -> None:
        """Delete a cached value.
        
        Parameters
        ----------
        key : str
            Cache key to delete
        """
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("DELETE FROM cache WHERE key = ?", (key,))
            conn.commit()

    def clear_expired(self) -> int:
        """Remove all expired cache entries.
        
        Returns
        -------
        int : Number of entries deleted
        """
        now = time.time()
        
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM cache WHERE expires_at < ?",
                (now,)
            )
            deleted = cursor.rowcount
            conn.commit()
        
        return deleted

    def clear_all(self) -> None:
        """Clear all cache entries."""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("DELETE FROM cache")
            conn.commit()

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.
        
        Returns
        -------
        Dict containing cache statistics
        """
        now = time.time()
        
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM cache")
            total = cursor.fetchone()[0]
            
            cursor = conn.execute(
                "SELECT COUNT(*) FROM cache WHERE expires_at > ?",
                (now,)
            )
            valid = cursor.fetchone()[0]
            
            cursor = conn.execute(
                "SELECT COUNT(*) FROM cache WHERE expires_at <= ?",
                (now,)
            )
            expired = cursor.fetchone()[0]
            
            cursor = conn.execute(
                "SELECT SUM(LENGTH(value)) FROM cache WHERE expires_at > ?",
                (now,)
            )
            size_bytes = cursor.fetchone()[0] or 0
        
        return {
            "total_entries": total,
            "valid_entries": valid,
            "expired_entries": expired,
            "size_bytes": size_bytes,
            "size_mb": round(size_bytes / (1024 * 1024), 2),
        }


__all__ = ["CacheManager"]

