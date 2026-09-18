"""Tests for ShareStore token generation, validation, expiry, and revocation."""

import tempfile
import time
from pathlib import Path

from hermes_share.db.share_store import ShareStore


def test_share_store_lifecycle():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "share.db"
        store = ShareStore(db_path)

        # Create share
        share = store.create_share(
            session_id="session_abc",
            ttl_seconds=3600,
            show_reasoning=True,
            allow_live=True,
            created_by="cli",
        )
        token = share["token"]
        assert token.startswith("sh_")
        assert len(token) > 20

        # Retrieve share
        retrieved = store.get_share(token)
        assert retrieved is not None
        assert retrieved["session_id"] == "session_abc"
        assert retrieved["is_expired"] is False
        assert retrieved["revoked"] is False

        # Increment view count
        store.increment_view_count(token)
        updated = store.get_share(token)
        assert updated["view_count"] == 1

        # Revoke share
        assert store.revoke_share(token) is True
        revoked = store.get_share(token)
        assert revoked["revoked"] is True


def test_share_store_expiry():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "share.db"
        store = ShareStore(db_path)

        # Create share with 1s TTL
        share = store.create_share(session_id="session_exp", ttl_seconds=1)
        token = share["token"]

        retrieved = store.get_share(token)
        assert retrieved["is_expired"] is False

        time.sleep(1.1)
        expired = store.get_share(token)
        assert expired["is_expired"] is True
