"""Server-Sent Events (SSE) hub for live-syncing Hermes sessions."""

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

from hermes_share.db.hermes_reader import HermesReader
from hermes_share.db.share_store import ShareStore

logger = logging.getLogger(__name__)


class SessionEventHub:
    """Manages SSE generation and change detection for live-shared sessions."""

    def __init__(
        self,
        hermes_reader: HermesReader,
        share_store: ShareStore,
        poll_interval: float = 1.0,
    ) -> None:
        self.reader = hermes_reader
        self.store = share_store
        self.poll_interval = poll_interval

    async def stream_session(
        self, token: str
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream real-time updates for a given share token as SSE dict events."""
        share = self.store.get_share(token)
        if not share or share["revoked"] or share["is_expired"]:
            yield {
                "event": "error",
                "data": json.dumps(
                    {"error": "Share link is revoked, expired, or invalid."}
                ),
            }
            return

        session_id = share["session_id"]
        session = self.reader.get_session(session_id)
        if not session:
            yield {
                "event": "error",
                "data": json.dumps({"error": "Target Hermes session not found."}),
            }
            return

        # Fetch initial state
        messages = self.reader.get_messages(session_id)
        if not share["show_reasoning"]:
            for m in messages:
                m["reasoning_content"] = None

        last_seen_id = messages[-1]["id"] if messages else 0
        stats = self.reader.get_session_stats(session_id)
        last_head_len = stats["head_len"]

        # 1. Send initial snapshot
        yield {
            "event": "initial",
            "data": json.dumps(
                {
                    "session": session,
                    "messages": messages,
                    "share": {
                        "token": share["token"],
                        "allow_live": share["allow_live"],
                        "show_reasoning": share["show_reasoning"],
                        "created_at": share["created_at"],
                        "expires_at": share["expires_at"],
                    },
                }
            ),
        }

        # If live stream not allowed, terminate after initial load
        if not share["allow_live"]:
            yield {
                "event": "complete",
                "data": json.dumps({"status": "live_sync_disabled"}),
            }
            return

        ping_counter = 0
        try:
            while True:
                await asyncio.sleep(self.poll_interval)
                ping_counter += 1

                # Periodic validation of share status
                if ping_counter % 10 == 0:
                    current_share = self.store.get_share(token)
                    if (
                        not current_share
                        or current_share["revoked"]
                        or current_share["is_expired"]
                    ):
                        yield {
                            "event": "revoked",
                            "data": json.dumps(
                                {"message": "Share link revoked or expired"}
                            ),
                        }
                        break

                # Send keep-alive ping every 15 polls
                if ping_counter % 15 == 0:
                    yield {"event": "ping", "data": "keepalive"}

                # Check for updates in Hermes session
                current_stats = self.reader.get_session_stats(session_id)

                # Scenario A: New messages added
                if current_stats["max_id"] > last_seen_id:
                    new_msgs = self.reader.get_messages(
                        session_id, after_id=last_seen_id
                    )
                    for m in new_msgs:
                        if not share["show_reasoning"]:
                            m["reasoning_content"] = None
                        yield {
                            "event": "append",
                            "data": json.dumps(m),
                        }
                    last_seen_id = current_stats["max_id"]
                    last_head_len = current_stats["head_len"]

                # Scenario B: Current turn is streaming/growing
                elif (
                    current_stats["max_id"] == last_seen_id
                    and last_seen_id > 0
                    and current_stats["head_len"] != last_head_len
                ):
                    head_msgs = self.reader.get_messages(
                        session_id, after_id=last_seen_id - 1
                    )
                    if head_msgs:
                        head_msg = head_msgs[0]
                        if not share["show_reasoning"]:
                            head_msg["reasoning_content"] = None
                        yield {
                            "event": "update",
                            "data": json.dumps(head_msg),
                        }
                    last_head_len = current_stats["head_len"]

        except asyncio.CancelledError:
            # Client disconnected
            pass
