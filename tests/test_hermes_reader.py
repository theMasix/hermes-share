"""Tests for HermesReader SQLite operations."""

import sqlite3
import tempfile
from pathlib import Path

from hermes_share.db.hermes_reader import HermesReader


def create_mock_hermes_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode = WAL;")
    cur.execute(
        """
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            title TEXT,
            model TEXT,
            started_at REAL NOT NULL,
            ended_at REAL,
            message_count INTEGER DEFAULT 0,
            tool_call_count INTEGER DEFAULT 0,
            chat_id TEXT,
            thread_id TEXT
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL REFERENCES sessions(id),
            role TEXT NOT NULL,
            content TEXT,
            tool_name TEXT,
            tool_calls TEXT,
            reasoning_content TEXT,
            timestamp REAL NOT NULL,
            active INTEGER DEFAULT 1
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE telegram_dm_topic_bindings (
            profile_name TEXT NOT NULL,
            chat_id TEXT NOT NULL,
            thread_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            PRIMARY KEY (profile_name, chat_id, thread_id)
        );
        """
    )
    cur.execute(
        """
        INSERT INTO sessions (id, source, title, model, started_at)
        VALUES ('sess_123', 'telegram', 'Deploy Kubernetes with sk-123456789012345678901234', 'claude-3-5', 1000.0);
        """
    )
    cur.execute(
        """
        INSERT INTO messages (id, session_id, role, content, reasoning_content, timestamp)
        VALUES (1, 'sess_123', 'user', 'Deploy the app with ghp_123456789012345678901234567890123456', NULL, 1001.0);
        """
    )
    cur.execute(
        """
        INSERT INTO messages (id, session_id, role, content, reasoning_content, timestamp)
        VALUES (2, 'sess_123', 'assistant', 'Deploying now...', 'Checking sk-secret12345678901234567890', 1002.0);
        """
    )
    cur.execute(
        """
        INSERT INTO telegram_dm_topic_bindings (profile_name, chat_id, thread_id, session_id)
        VALUES ('default', '87679709', '490000', 'sess_123');
        """
    )
    conn.commit()
    conn.close()


def test_hermes_reader_reads_and_redacts():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "state.db"
        create_mock_hermes_db(db_path)

        reader = HermesReader(db_path=db_path)
        session = reader.get_session("sess_123")
        assert session is not None
        assert session["id"] == "sess_123"
        # Secret in title should be redacted
        assert "[REDACTED_API_KEY]" in session["title"]

        # Test telegram topic binding lookup
        topic_sess = reader.get_session_by_telegram_topic("87679709", "490000")
        assert topic_sess is not None
        assert topic_sess["id"] == "sess_123"

        # Test message fetching and redactions
        messages = reader.get_messages("sess_123")
        assert len(messages) == 2
        assert "[REDACTED_GITHUB_TOKEN]" in messages[0]["content"]
        assert "[REDACTED_API_KEY]" in messages[1]["reasoning_content"]

        # Test delta query
        stats = reader.get_session_stats("sess_123")
        assert stats["max_id"] == 2
        assert stats["total_messages"] == 2
