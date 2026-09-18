"""Command line interface for hermes-share."""

import os
import re
from typing import Annotated

import httpx
import typer
import uvicorn
from rich.console import Console
from rich.table import Table

from hermes_share.config import settings
from hermes_share.db.hermes_reader import HermesReader
from hermes_share.db.share_store import ShareStore

app = typer.Typer(
    name="hermes-share",
    help="CLI for creating and managing secret, live-updating Hermes Agent chat links.",
    add_completion=False,
)
console = Console()


def parse_duration(duration_str: str | None) -> int | None:
    """Parse string duration (e.g. '1h', '24h', '30m', '7d') into seconds."""
    if not duration_str:
        return None
    cleaned = duration_str.strip().lower()
    if cleaned.isdigit():
        return int(cleaned)

    m = re.match(r"^(\d+)([smhd])$", cleaned)
    if not m:
        raise typer.BadParameter(
            f"Invalid duration '{duration_str}'. Use format like 30m, 12h, 7d."
        )

    val, unit = int(m.group(1)), m.group(2)
    multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    return val * multipliers[unit]


@app.command()
def create(
    session_id: Annotated[
        str | None,
        typer.Argument(help="Target Hermes session ID (omit for latest)"),
    ] = None,
    latest: Annotated[
        bool, typer.Option("--latest", "-l", help="Pick latest session")
    ] = False,
    telegram_topic: Annotated[
        str | None,
        typer.Option("--telegram-topic", "-t", help="Telegram topic 'chat_id:thread_id'"),
    ] = None,
    ttl: Annotated[
        str | None,
        typer.Option("--ttl", help="TTL duration e.g. '24h', '7d', '3600s'"),
    ] = None,
    show_reasoning: Annotated[
        bool, typer.Option("--reasoning/--no-reasoning", help="Include reasoning steps")
    ] = True,
    allow_live: Annotated[
        bool, typer.Option("--live/--no-live", help="Enable live SSE streaming")
    ] = True,
    api_server: Annotated[
        str | None,
        typer.Option("--server", help="Remote hermes-share server base URL"),
    ] = None,
    api_key: Annotated[
        str | None,
        typer.Option("--api-key", help="Management API Key (when using --server)"),
    ] = None,
):
    """Generate a new unguessable share link for a Hermes session."""
    ttl_seconds = parse_duration(ttl)

    target_server = (
        api_server or os.getenv("HERMES_SHARE_SERVER", "")
    ).rstrip("/")

    # Remote API client mode
    if target_server:
        server_url = target_server
        headers = {}
        key = (
            api_key
            or os.getenv("HERMES_SHARE_API_KEY")
            or settings.management_api_key
        )
        if key:
            headers["X-API-Key"] = key

        payload = {
            "session_id": session_id,
            "latest": latest or (session_id is None and telegram_topic is None),
            "telegram_topic": telegram_topic,
            "ttl_seconds": ttl_seconds,
            "show_reasoning": show_reasoning,
            "allow_live": allow_live,
            "created_by": "cli-remote",
        }
        try:
            with httpx.Client(timeout=10.0, trust_env=False) as client:
                res = client.post(
                    f"{server_url}/api/v1/shares", json=payload, headers=headers
                )
                if res.status_code != 201:
                    console.print(
                        f"[red]Error ({res.status_code}): {res.text}[/red]"
                    )
                    raise typer.Exit(code=1)
                data = res.json()
        except (httpx.HTTPError, OSError) as e:
            console.print(f"[red]Failed to connect to {server_url}: {e}[/red]")
            raise typer.Exit(code=1)

    # Local direct mode
    else:
        reader = HermesReader(
            db_path=settings.hermes_db_path,
            redact_secrets=settings.redact_secrets,
        )
        store = ShareStore(db_path=settings.share_db_path)

        target_id = session_id
        if latest or (target_id is None and telegram_topic is None):
            sess = reader.get_latest_session()
            if not sess:
                console.print("[red]No sessions found in Hermes state.db[/red]")
                raise typer.Exit(code=1)
            target_id = sess["id"]
        elif telegram_topic:
            parts = telegram_topic.split(":")
            if len(parts) != 2:
                console.print(
                    "[red]Error: telegram_topic must be formatted as 'chat_id:thread_id'[/red]"
                )
                raise typer.Exit(code=1)
            sess = reader.get_session_by_telegram_topic(parts[0], parts[1])
            if not sess:
                console.print(
                    f"[red]No session bound to Telegram topic {telegram_topic}[/red]"
                )
                raise typer.Exit(code=1)
            target_id = sess["id"]

        if not target_id:
            console.print("[red]Could not determine target session ID.[/red]")
            raise typer.Exit(code=1)

        session = reader.get_session(target_id)
        if not session:
            console.print(f"[red]Session {target_id} not found.[/red]")
            raise typer.Exit(code=1)

        share = store.create_share(
            session_id=target_id,
            ttl_seconds=ttl_seconds,
            show_reasoning=show_reasoning,
            allow_live=allow_live,
            created_by="cli-local",
        )
        data = {
            **share,
            "url": f"{settings.base_url.rstrip('/')}/s/{share['token']}",
            "session_title": session.get("title") or "Untitled Session",
            "session_model": session.get("model"),
        }

    # Display output
    console.print()
    console.print(
        f"[bold green]✔ Share Link Generated for session:[/bold green] [cyan]{data.get('session_id')}[/cyan]"
    )
    console.print(
        f"[bold]Title:[/bold] {data.get('session_title', 'Untitled')}"
    )
    console.print(
        f"[bold]Model:[/bold] {data.get('session_model', 'Hermes')}"
    )
    console.print()
    console.print(
        f"🔗 [bold underline blue]{data.get('url')}[/bold underline blue]"
    )
    console.print()
    console.print(
        f"[dim]Live sync: {'Enabled' if data.get('allow_live') else 'Disabled'} | "
        f"Reasoning: {'Included' if data.get('show_reasoning') else 'Hidden'} | "
        f"Token: {data.get('token')}[/dim]"
    )
    console.print()


@app.command()
def list(
    api_server: Annotated[
        str | None,
        typer.Option("--server", help="Remote hermes-share server base URL"),
    ] = None,
    api_key: Annotated[
        str | None,
        typer.Option("--api-key", help="Management API Key (when using --server)"),
    ] = None,
):
    """List all created share links."""
    target_server = (
        api_server or os.getenv("HERMES_SHARE_SERVER", "")
    ).rstrip("/")

    if target_server:
        headers = {}
        key = (
            api_key
            or os.getenv("HERMES_SHARE_API_KEY")
            or settings.management_api_key
        )
        if key:
            headers["X-API-Key"] = key
        try:
            with httpx.Client(timeout=10.0, trust_env=False) as client:
                res = client.get(f"{target_server}/api/v1/shares", headers=headers)
                if res.status_code != 200:
                    console.print(f"[red]Error ({res.status_code}): {res.text}[/red]")
                    raise typer.Exit(code=1)
                shares = res.json().get("items", [])
        except (httpx.HTTPError, OSError) as e:
            console.print(f"[red]Failed to connect to {target_server}: {e}[/red]")
            raise typer.Exit(code=1)
    else:
        store = ShareStore(db_path=settings.share_db_path)
        shares = store.list_shares(limit=50)

    if not shares:
        console.print("[dim]No share links created yet.[/dim]")
        return

    table = Table(title="Hermes Share Links", show_header=True, header_style="bold magenta")
    table.add_column("Token", style="cyan", no_wrap=True)
    table.add_column("Session ID", style="dim")
    table.add_column("Views", justify="right")
    table.add_column("Status")
    table.add_column("URL", style="blue")

    for s in shares:
        if s.get("revoked"):
            status_str = "[red]Revoked[/red]"
        elif s.get("is_expired"):
            status_str = "[yellow]Expired[/yellow]"
        else:
            status_str = "[green]Active[/green]"

        url = s.get("url") or f"{settings.base_url.rstrip('/')}/s/{s['token']}"
        table.add_row(
            s["token"][:16] + "...",
            s.get("session_id", "unknown"),
            str(s.get("view_count", 0)),
            status_str,
            url,
        )

    console.print(table)


@app.command()
def revoke(
    token: Annotated[str, typer.Argument(help="Share token to revoke")],
    api_server: Annotated[
        str | None,
        typer.Option("--server", help="Remote hermes-share server base URL"),
    ] = None,
    api_key: Annotated[
        str | None,
        typer.Option("--api-key", help="Management API Key (when using --server)"),
    ] = None,
):
    """Revoke a share link so it can no longer be accessed."""
    target_server = (
        api_server or os.getenv("HERMES_SHARE_SERVER", "")
    ).rstrip("/")

    if target_server:
        headers = {}
        key = (
            api_key
            or os.getenv("HERMES_SHARE_API_KEY")
            or settings.management_api_key
        )
        if key:
            headers["X-API-Key"] = key
        try:
            with httpx.Client(timeout=10.0, trust_env=False) as client:
                res = client.delete(f"{target_server}/api/v1/shares/{token}", headers=headers)
                if res.status_code == 200:
                    console.print(f"[green]✔ Successfully revoked share token:[/green] [cyan]{token}[/cyan]")
                    return
                console.print(f"[red]Error ({res.status_code}): {res.text}[/red]")
                raise typer.Exit(code=1)
        except (httpx.HTTPError, OSError) as e:
            console.print(f"[red]Failed to connect to {target_server}: {e}[/red]")
            raise typer.Exit(code=1)
    else:
        store = ShareStore(db_path=settings.share_db_path)
        if store.revoke_share(token):
            console.print(f"[green]✔ Successfully revoked share token:[/green] [cyan]{token}[/cyan]")
        else:
            console.print(f"[red]Share token not found or already revoked:[/red] [yellow]{token}[/yellow]")
            raise typer.Exit(code=1)


@app.command()
def serve(
    host: Annotated[
        str, typer.Option("--host", "-h", help="Bind host")
    ] = settings.host,
    port: Annotated[
        int, typer.Option("--port", "-p", help="Bind port")
    ] = settings.port,
):
    """Start the hermes-share web server."""
    console.print(f"[bold green]Starting hermes-share server on {host}:{port}...[/bold green]")
    uvicorn.run("hermes_share.main:app", host=host, port=port, reload=False)


def main():
    app()


if __name__ == "__main__":
    main()
