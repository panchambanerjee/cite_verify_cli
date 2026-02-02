"""SQLite caching for verification results to avoid re-querying APIs."""

import sqlite3
import json
import hashlib
import os
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta
from .models import VerificationResult, VerificationStatus


class VerificationCache:
    """Cache verification results in SQLite database."""

    def __init__(self, cache_dir: str = None, ttl_days: int = 7):
        """
        Initialize cache.

        Args:
            cache_dir: Directory to store cache database. Defaults to ./.citeverify/
            ttl_days: Time-to-live for cache entries in days
        """
        if cache_dir is None:
            # Try home directory first, fall back to current directory
            home_cache = os.path.join(Path.home(), ".citeverify")
            try:
                Path(home_cache).mkdir(parents=True, exist_ok=True)
                cache_dir = home_cache
            except (PermissionError, OSError):
                # Fall back to current directory
                cache_dir = os.path.join(os.getcwd(), ".citeverify")

        Path(cache_dir).mkdir(parents=True, exist_ok=True)
        self.db_path = os.path.join(cache_dir, "cache.db")
        self.ttl_days = ttl_days
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS verification_cache (
                    cache_key TEXT PRIMARY KEY,
                    result_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    query_type TEXT,
                    query_value TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_created_at 
                ON verification_cache(created_at)
            """)
            conn.commit()

    def _make_key(self, query_type: str, query_value: str) -> str:
        """Create cache key from query type and value."""
        key_str = f"{query_type}:{query_value.lower().strip()}"
        return hashlib.sha256(key_str.encode()).hexdigest()[:32]

    def get(self, query_type: str, query_value: str) -> Optional[VerificationResult]:
        """
        Get cached verification result.

        Args:
            query_type: Type of query ('doi', 'arxiv', 'title')
            query_value: The query value

        Returns:
            VerificationResult if found and not expired, None otherwise
        """
        cache_key = self._make_key(query_type, query_value)
        cutoff = datetime.now() - timedelta(days=self.ttl_days)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT result_json, created_at FROM verification_cache
                WHERE cache_key = ? AND created_at > ?
                """,
                (cache_key, cutoff.isoformat()),
            )
            row = cursor.fetchone()

            if row:
                result_data = json.loads(row[0])
                # Convert status string back to enum
                result_data["status"] = VerificationStatus(result_data["status"])
                return VerificationResult(**result_data)

        return None

    def set(
        self, query_type: str, query_value: str, result: VerificationResult
    ) -> None:
        """
        Store verification result in cache.

        Args:
            query_type: Type of query ('doi', 'arxiv', 'title')
            query_value: The query value
            result: VerificationResult to cache
        """
        cache_key = self._make_key(query_type, query_value)

        # Convert result to JSON-serializable dict
        result_dict = result.model_dump()
        result_dict["status"] = result_dict["status"].value  # Convert enum to string
        result_json = json.dumps(result_dict, default=str)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO verification_cache 
                (cache_key, result_json, created_at, query_type, query_value)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    cache_key,
                    result_json,
                    datetime.now().isoformat(),
                    query_type,
                    query_value[:500],  # Truncate long values
                ),
            )
            conn.commit()

    def clear(self) -> int:
        """
        Clear all cache entries.

        Returns:
            Number of entries cleared
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM verification_cache")
            count = cursor.fetchone()[0]
            conn.execute("DELETE FROM verification_cache")
            conn.commit()
            return count

    def clear_expired(self) -> int:
        """
        Clear expired cache entries.

        Returns:
            Number of entries cleared
        """
        cutoff = datetime.now() - timedelta(days=self.ttl_days)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM verification_cache WHERE created_at <= ?",
                (cutoff.isoformat(),),
            )
            count = cursor.fetchone()[0]
            conn.execute(
                "DELETE FROM verification_cache WHERE created_at <= ?",
                (cutoff.isoformat(),),
            )
            conn.commit()
            return count

    def stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM verification_cache")
            total = cursor.fetchone()[0]

            cutoff = datetime.now() - timedelta(days=self.ttl_days)
            cursor = conn.execute(
                "SELECT COUNT(*) FROM verification_cache WHERE created_at > ?",
                (cutoff.isoformat(),),
            )
            valid = cursor.fetchone()[0]

            cursor = conn.execute(
                """
                SELECT query_type, COUNT(*) FROM verification_cache 
                GROUP BY query_type
                """
            )
            by_type = dict(cursor.fetchall())

        return {
            "total_entries": total,
            "valid_entries": valid,
            "expired_entries": total - valid,
            "by_type": by_type,
            "db_path": self.db_path,
            "ttl_days": self.ttl_days,
        }
