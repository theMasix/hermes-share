"""Tests for SSE Event Hub."""

import json
import tempfile
from pathlib import Path

import pytest

from hermes_share.db.hermes_reader import HermesReader
from hermes_share.db.share_store import ShareStore
from hermes_share.sse.hub import SessionEventHub

from .test_hermes_reader import create_mock_hermes_db


@pytest.mark.asyncio
async def test_sse_hub_initial_and_stream():
    with tempfile.TemporaryDirectory() as tmpdir:
        hermes_db = Path(tmpdir) / "state.db"
        share_db = Path(tmpdir) / "share.db"
        create_mock_hermes_db(hermes_db)

        reader = HermesReader(hermes_db)
        store = ShareStore(share_db)
        share = store.create_share(session_id="sess_123", allow_live=False)

        hub = SessionEventHub(reader, store, poll_interval=0.1)

        events = []
        async for event in hub.stream_session(share["token"]):
            events.append(event)
            if event["event"] == "complete":
                break

        assert len(events) >= 2
        assert events[0]["event"] == "initial"
        initial_data = json.loads(events[0]["data"])
        assert initial_data["session"]["id"] == "sess_123"
        assert len(initial_data["messages"]) == 2
        assert events[1]["event"] == "complete"
