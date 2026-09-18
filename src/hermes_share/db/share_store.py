"""SQLite repository for hermes-share tokens and metadata."""

import secrets
import sqlite3
import time
from pathlib import Path
from typing import Any


class ShareStore:
    """Manages creation, lookup, expiry, and revocation of share tokens."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("PRAGMA journal_mode = WAL;")
        cur.execute("PRAGMA busy_timeout = 5000;")
        cur.close()
        return conn

    def _init_schema(self) -> None:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS share_links (
                    token TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL,
                    revoked INTEGER NOT NULL DEFAULT 0,
                    allow_live INTEGER NOT NULL DEFAULT 1,
                    show_reasoning INTEGER NOT NULL DEFAULT 1,
                    view_count INTEGER NOT NULL DEFAULT 0,
                    created_by TEXT
                );
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_share_session ON share_links(session_id);
                """
            )
            conn.commit()

    def create_share(
        self,
        session_id: str,
        ttl_seconds: int | None = None,
        show_reasoning: bool = True,
        allow_live: bool = True,
        created_by: str | None = None,
    ) -> dict[str, Any]:
        """Create and store a new secure share token."""
        token = f"sh_{secrets.token_urlsafe(24)}"
        now = time.time()
        expires_at = now + ttl_seconds if ttl_seconds and ttl_seconds > 0 else None

        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO share_links (
                    token, session_id, created_at, expires_at,
                    revoked, allow_live, show_reasoning, view_count, created_by
                ) VALUES (?, ?, ?, ?, 0, ?, ?, 0, ?);
                """,
                (
                    token,
                    session_id,
                    now,
                    expires_at,
                    1 if allow_live else 0,
                    1 if show_reasoning else 0,
                    created_by,
                ),
            )
            conn.commit()

        return {
            "token": token,
            "session_id": session_id,
            "created_at": now,
            "expires_at": expires_at,
            "revoked": False,
            "allow_live": allow_live,
            "show_reasoning": show_reasoning,
            "view_count": 0,
            "created_by": created_by,
        }

    def get_share(self, token: str) -> dict[str, Any] | None:
        """Fetch share link record and validate expiration and revocation status."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT token, session_id, created_at, expires_at,
                       revoked, allow_live, show_reasoning, view_count, created_by
                FROM share_links
                WHERE token = ?;
                """,
                (token,),
            )
            row = cur.fetchone()
            if not row:
                return None
            data = dict(row)
            data["revoked"] = bool(data["revoked"])
            data["allow_live"] = bool(data["allow_live"])
            data["show_reasoning"] = bool(data["show_reasoning"])

            # Check expiry
            now = time.time()
            if data["expires_at"] is not None and now > data["expires_at"]:
                data["is_expired"] = True
            else:
                data["is_expired"] = False

            return data

    def increment_view_count(self, token: str) -> None:
        """Increment view count for analytics."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE share_links
                SET view_count = view_count + 1
                WHERE token = ?;
                """,
                (token,),
            )
            conn.commit()

    def revoke_share(self, token: str) -> bool:
        """Mark a share token as revoked."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE share_links
                SET revoked = 1
                WHERE token = ? AND revoked = 0;
                """,
                (token,),
            )
            conn.commit()
            return cur.rowcount > 0

    def list_shares(
        self, session_id: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        """List active and historical shares."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            if session_id:
                cur.execute(
                    """
                    SELECT token, session_id, created_at, expires_at,
                           revoked, allow_live, show_reasoning, view_count, created_by
                    FROM share_links
                    WHERE session_id = ?
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?;
                    """,
                    (session_id, limit, offset),
                )
            else:
                cur.execute(
                    """
                    SELECT token, session_id, created_at, expires_at,
                           revoked, allow_live, show_reasoning, view_count, created_by
                    FROM share_links
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?;
                    """,
                    (limit, offset),
                )
            rows = cur.fetchall()
            now = time.time()
            results = []
            for r in rows:
                d = dict(r)
                d["revoked"] = bool(d["revoked"])
                d["allow_live"] = bool(d["allow_live"])
                d["show_reasoning"] = bool(d["show_reasoning"])
                d["is_expired"] = (
                    d["expires_at"] is not None and now > d["expires_at"]
                )
                results.append(d)
            return results
