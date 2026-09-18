"""Read-only SQLite reader for Hermes Agent state database."""

import json
import sqlite3
from pathlib import Path
from typing import Any

from hermes_share.redactor import SecretRedactor, default_redactor


class HermesReader:
    """Safely and concurrently reads sessions and messages from Hermes state.db."""

    def __init__(
        self,
        db_path: Path | str,
        redactor: SecretRedactor | None = None,
        redact_secrets: bool = True,
    ) -> None:
        self.db_path = Path(db_path).resolve()
        self.redactor = redactor or default_redactor
        self.redact_secrets = redact_secrets

    def _get_connection(self) -> sqlite3.Connection:
        """Create a strict read-only connection to SQLite in WAL mode."""
        if not self.db_path.exists():
            raise FileNotFoundError(f"Hermes database not found at {self.db_path}")

        # URI read-only connection
        uri = f"file:{self.db_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=5.0)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("PRAGMA query_only = ON;")
        cur.execute("PRAGMA busy_timeout = 5000;")
        cur.close()
        return conn

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Fetch session metadata by session ID."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, source, title, model, started_at, ended_at,
                       message_count, tool_call_count, chat_id, thread_id
                FROM sessions
                WHERE id = ?;
                """,
                (session_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            session = dict(row)
            if self.redact_secrets and session.get("title"):
                session["title"] = self.redactor.redact_text(session["title"])
            return session

    def get_latest_session(self) -> dict[str, Any] | None:
        """Fetch the most recently active session."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT s.id, s.source, s.title, s.model, s.started_at, s.ended_at,
                       s.message_count, s.tool_call_count, s.chat_id, s.thread_id
                FROM sessions s
                LEFT JOIN (
                    SELECT session_id, MAX(timestamp) AS last_activity
                    FROM messages
                    GROUP BY session_id
                ) m ON s.id = m.session_id
                ORDER BY COALESCE(m.last_activity, s.started_at) DESC
                LIMIT 1;
                """
            )
            row = cur.fetchone()
            if not row:
                return None
            session = dict(row)
            if self.redact_secrets and session.get("title"):
                session["title"] = self.redactor.redact_text(session["title"])
            return session

    def get_session_by_telegram_topic(
        self, chat_id: str, thread_id: str
    ) -> dict[str, Any] | None:
        """Resolve a session ID associated with a Telegram topic."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT session_id
                FROM telegram_dm_topic_bindings
                WHERE chat_id = ? AND thread_id = ?
                LIMIT 1;
                """,
                (str(chat_id), str(thread_id)),
            )
            row = cur.fetchone()
            if not row:
                return None
            session_id = row["session_id"]
        return self.get_session(session_id)

    def get_messages(
        self, session_id: str, after_id: int = 0
    ) -> list[dict[str, Any]]:
        """Fetch messages for a session, optionally after a message ID."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, session_id, role, content, tool_name, tool_calls,
                       reasoning_content, timestamp, active
                FROM messages
                WHERE session_id = ? AND id > ? AND active = 1
                ORDER BY id ASC;
                """,
                (session_id, after_id),
            )
            rows = cur.fetchall()
            messages: list[dict[str, Any]] = []
            for r in rows:
                msg = dict(r)
                # Parse tool_calls if JSON string
                if msg.get("tool_calls"):
                    try:
                        parsed_calls = json.loads(msg["tool_calls"])
                        if self.redact_secrets:
                            parsed_calls = self.redactor.redact_data(parsed_calls)
                        msg["tool_calls"] = parsed_calls
                    except (json.JSONDecodeError, TypeError):
                        if self.redact_secrets:
                            msg["tool_calls"] = self.redactor.redact_text(
                                msg["tool_calls"]
                            )
                # Redact content & reasoning
                if self.redact_secrets:
                    if msg.get("content"):
                        msg["content"] = self.redactor.redact_text(msg["content"])
                    if msg.get("reasoning_content"):
                        msg["reasoning_content"] = self.redactor.redact_text(
                            msg["reasoning_content"]
                        )
                messages.append(msg)
            return messages

    def get_session_stats(self, session_id: str) -> dict[str, Any]:
        """Fetch max message ID and head message delta stats for change detection."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT MAX(id) AS max_id, COUNT(id) AS total_messages
                FROM messages
                WHERE session_id = ? AND active = 1;
                """,
                (session_id,),
            )
            row = cur.fetchone()
            max_id = row["max_id"] or 0
            total_messages = row["total_messages"] or 0

            head_len = 0
            if max_id > 0:
                cur.execute(
                    """
                    SELECT LENGTH(COALESCE(content, '')) + LENGTH(COALESCE(reasoning_content, '')) AS content_len
                    FROM messages
                    WHERE id = ?;
                    """,
                    (max_id,),
                )
                head_row = cur.fetchone()
                if head_row:
                    head_len = head_row["content_len"] or 0

            return {
                "max_id": max_id,
                "total_messages": total_messages,
                "head_len": head_len,
            }
