"""Management API endpoints for hermes-share."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

from hermes_share.config import settings
from hermes_share.db.hermes_reader import HermesReader
from hermes_share.db.share_store import ShareStore

router = APIRouter(prefix="/api/v1/shares", tags=["management"])


def get_hermes_reader() -> HermesReader:
    return HermesReader(
        db_path=settings.hermes_db_path,
        redact_secrets=settings.redact_secrets,
    )


def get_share_store() -> ShareStore:
    return ShareStore(db_path=settings.share_db_path)


def verify_api_key(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    """Validate management API key via X-API-Key or Bearer header."""
    expected = settings.management_api_key
    if not expected:
        # If no key configured in settings, permit local access
        return "unauthenticated"

    token = x_api_key
    if not token and authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]

    if not token or token != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing management API key.",
        )
    return token


class CreateShareRequest(BaseModel):
    session_id: str | None = Field(
        default=None, description="Hermes session ID to share"
    )
    latest: bool = Field(
        default=False, description="Share the most recent session"
    )
    telegram_topic: str | None = Field(
        default=None,
        description="Lookup session by Telegram 'chat_id:thread_id'",
    )
    ttl_seconds: int | None = Field(
        default=None, description="Time-to-live in seconds (0 or null for indefinite)"
    )
    show_reasoning: bool = Field(
        default=True, description="Whether to include reasoning / thinking steps"
    )
    allow_live: bool = Field(
        default=True, description="Whether live SSE streaming is allowed"
    )
    created_by: str | None = Field(
        default=None, description="Metadata identifier of requester"
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def create_share(
    payload: CreateShareRequest,
    _auth: Annotated[str, Depends(verify_api_key)],
    reader: Annotated[HermesReader, Depends(get_hermes_reader)],
    store: Annotated[ShareStore, Depends(get_share_store)],
):
    """Create a new secret share link for a Hermes session."""
    target_session_id = payload.session_id

    # Resolve latest session if requested or if no ID specified
    if payload.latest or (not target_session_id and not payload.telegram_topic):
        latest = reader.get_latest_session()
        if not latest:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No sessions found in Hermes database.",
            )
        target_session_id = latest["id"]

    elif payload.telegram_topic:
        parts = payload.telegram_topic.split(":")
        if len(parts) != 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="telegram_topic must be formatted as 'chat_id:thread_id'",
            )
        chat_id, thread_id = parts[0].strip(), parts[1].strip()
        topic_sess = reader.get_session_by_telegram_topic(chat_id, thread_id)
        if not topic_sess:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No Hermes session bound to Telegram topic {chat_id}:{thread_id}",
            )
        target_session_id = topic_sess["id"]

    if not target_session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not determine target session ID.",
        )

    # Verify session exists
    session = reader.get_session(target_session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {target_session_id} not found in Hermes database.",
        )

    # Use default TTL if not specified
    ttl = (
        payload.ttl_seconds
        if payload.ttl_seconds is not None
        else settings.default_ttl_seconds
    )

    share = store.create_share(
        session_id=target_session_id,
        ttl_seconds=ttl,
        show_reasoning=payload.show_reasoning,
        allow_live=payload.allow_live,
        created_by=payload.created_by,
    )

    share_url = f"{settings.base_url.rstrip('/')}/s/{share['token']}"
    return {
        **share,
        "url": share_url,
        "session_title": session.get("title") or "Untitled Session",
        "session_model": session.get("model"),
    }


@router.get("")
def list_shares(
    _auth: Annotated[str, Depends(verify_api_key)],
    store: Annotated[ShareStore, Depends(get_share_store)],
    session_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """List shares with pagination."""
    shares = store.list_shares(session_id=session_id, limit=limit, offset=offset)
    return {
        "items": [
            {
                **s,
                "url": f"{settings.base_url.rstrip('/')}/s/{s['token']}",
            }
            for s in shares
        ],
        "limit": limit,
        "offset": offset,
    }


@router.delete("/{token}")
def revoke_share(
    token: str,
    _auth: Annotated[str, Depends(verify_api_key)],
    store: Annotated[ShareStore, Depends(get_share_store)],
):
    """Revoke an existing share token."""
    success = store.revoke_share(token)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share token not found or already revoked.",
        )
    return {"status": "revoked", "token": token}
