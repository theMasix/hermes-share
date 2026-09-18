"""Public share routes and live SSE streaming."""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import HTMLResponse
from sse_starlette.sse import EventSourceResponse

from hermes_share.config import settings
from hermes_share.db.hermes_reader import HermesReader
from hermes_share.db.share_store import ShareStore
from hermes_share.sse.hub import SessionEventHub

router = APIRouter(tags=["public_share"])


def get_hermes_reader() -> HermesReader:
    return HermesReader(
        db_path=settings.hermes_db_path,
        redact_secrets=settings.redact_secrets,
    )


def get_share_store() -> ShareStore:
    return ShareStore(db_path=settings.share_db_path)


@router.get("/api/v1/shares/{token}")
def get_share_data(
    token: str,
    store: Annotated[ShareStore, Depends(get_share_store)],
    reader: Annotated[HermesReader, Depends(get_hermes_reader)],
):
    """Fetch complete session snapshot for a given share token."""
    share = store.get_share(token)
    if not share:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share link not found.",
        )
    if share["revoked"]:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This share link has been revoked by the owner.",
        )
    if share["is_expired"]:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This share link has expired.",
        )

    session = reader.get_session(share["session_id"])
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target conversation session was not found.",
        )

    messages = reader.get_messages(share["session_id"])
    if not share["show_reasoning"]:
        for m in messages:
            m["reasoning_content"] = None

    # Track view analytics
    store.increment_view_count(token)

    return {
        "share": {
            "token": share["token"],
            "allow_live": share["allow_live"],
            "show_reasoning": share["show_reasoning"],
            "created_at": share["created_at"],
            "expires_at": share["expires_at"],
            "view_count": share["view_count"] + 1,
        },
        "session": session,
        "messages": messages,
    }


@router.get("/api/v1/shares/{token}/stream")
async def stream_share(
    token: str,
    store: Annotated[ShareStore, Depends(get_share_store)],
    reader: Annotated[HermesReader, Depends(get_hermes_reader)],
):
    """Server-Sent Events (SSE) stream for live updates to the conversation."""
    share = store.get_share(token)
    if not share or share["revoked"] or share["is_expired"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share link not found, expired, or revoked.",
        )

    hub = SessionEventHub(hermes_reader=reader, share_store=store)
    return EventSourceResponse(
        hub.stream_session(token),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/s/{token}", response_class=HTMLResponse)
def view_share_page(
    token: str,
    response: Response,
    store: Annotated[ShareStore, Depends(get_share_store)],
    reader: Annotated[HermesReader, Depends(get_hermes_reader)],
):
    """Serve the public web page for viewing the shared conversation."""
    response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"

    share = store.get_share(token)
    if not share:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share link not found.",
        )
    if share["revoked"]:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This share link has been revoked by the owner.",
        )
    if share["is_expired"]:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This share link has expired.",
        )

    session = reader.get_session(share["session_id"])
    title = (session.get("title") if session else None) or "Hermes Session"

    # If built frontend exists, serve it
    dist_index = (
        settings.static_dir / "index.html"
        if settings.static_dir and (settings.static_dir / "index.html").exists()
        else Path("./web/dist/index.html")
    )
    if dist_index.exists():
        html = dist_index.read_text(encoding="utf-8")
        html = html.replace(
            "<title>Hermes Share</title>", f"<title>{title} - Hermes Share</title>"
        )
        return HTMLResponse(content=html)

    # Fallback to high-quality embedded standalone HTML viewer if SPA not yet compiled
    return HTMLResponse(content=get_embedded_viewer_html(token=token, title=title))


def get_embedded_viewer_html(token: str, title: str) -> str:
    """Embedded standalone viewer with live SSE, syntax highlighting, and dark mode."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="robots" content="noindex, nofollow, noarchive">
  <title>{title} - Hermes Share</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css">
  <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
  <style>
    pre code.hljs {{ padding: 1rem; border-radius: 0.5rem; }}
    .reasoning-block details summary {{ cursor: pointer; user-select: none; }}
  </style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen font-sans antialiased flex flex-col">
  <!-- Header -->
  <header class="sticky top-0 z-30 bg-slate-900/90 backdrop-blur border-b border-slate-800 px-4 py-3 flex items-center justify-between">
    <div class="flex items-center space-x-3">
      <div class="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center font-bold text-white shadow">H</div>
      <div>
        <h1 id="session-title" class="font-semibold text-sm sm:text-base text-slate-100 leading-tight">{title}</h1>
        <div class="flex items-center space-x-2 text-xs text-slate-400">
          <span id="session-model" class="bg-slate-800 px-2 py-0.5 rounded text-slate-300">Hermes</span>
          <span>•</span>
          <span id="live-indicator" class="flex items-center text-emerald-400 font-medium">
            <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse mr-1.5"></span> Live Sync
          </span>
        </div>
      </div>
    </div>
    <div>
      <button id="copy-link-btn" onclick="copyShareLink()" class="text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 px-3 py-1.5 rounded-md transition shadow-sm">
        Copy Link
      </button>
    </div>
  </header>

  <!-- Message Feed -->
  <main class="flex-1 max-w-4xl w-full mx-auto p-4 sm:p-6 space-y-6">
    <div id="messages-container" class="space-y-6">
      <div class="flex items-center justify-center py-12 text-slate-500 text-sm">
        Connecting to session stream...
      </div>
    </div>
  </main>

  <footer class="py-4 border-t border-slate-900 text-center text-xs text-slate-500">
    Shared via <span class="text-slate-400 font-medium">hermes-share</span> • Read-only snapshot
  </footer>

  <script>
    const token = "{token}";
    const messagesContainer = document.getElementById("messages-container");
    let messagesMap = new Map();

    function copyShareLink() {{
      navigator.clipboard.writeText(window.location.href);
      const btn = document.getElementById("copy-link-btn");
      btn.innerText = "Copied!";
      setTimeout(() => btn.innerText = "Copy Link", 2000);
    }}

    function renderMessage(msg) {{
      const div = document.createElement("div");
      div.id = "msg-" + msg.id;
      div.className = "flex flex-col space-y-2";

      const isUser = msg.role === "user";
      const isAssistant = msg.role === "assistant";
      const isTool = msg.role === "tool";

      let inner = "";
      if (isUser) {{
        inner = `
          <div class="flex justify-end">
            <div class="max-w-[85%] bg-indigo-600 text-white px-4 py-3 rounded-2xl rounded-tr-sm shadow text-sm sm:text-base whitespace-pre-wrap leading-relaxed">
              ${{escapeHtml(msg.content || "")}}
            </div>
          </div>
        `;
      }} else if (isAssistant) {{
        let reasoningHtml = "";
        if (msg.reasoning_content) {{
          reasoningHtml = `
            <div class="reasoning-block bg-slate-900/80 border border-slate-800 rounded-lg p-3 text-xs text-slate-400">
              <details>
                <summary class="font-medium text-slate-300 hover:text-slate-100 flex items-center space-x-1.5">
                  <span>🧠 Reasoning Process</span>
                </summary>
                <div class="mt-2.5 pt-2.5 border-t border-slate-800/80 whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-slate-300">
                  ${{escapeHtml(msg.reasoning_content)}}
                </div>
              </details>
            </div>
          `;
        }}

        let toolCallsHtml = "";
        if (msg.tool_calls && Array.isArray(msg.tool_calls)) {{
          toolCallsHtml = msg.tool_calls.map(call => `
            <div class="bg-slate-900 border border-slate-800 rounded-lg p-2.5 text-xs font-mono text-slate-300">
              <div class="flex items-center space-x-2 text-indigo-400 font-semibold mb-1">
                <span>⚡ Tool Request:</span> <span>${{call.function ? call.function.name : (call.name || "tool")}}</span>
              </div>
              <pre class="bg-slate-950 p-2 rounded text-[11px] text-slate-400 overflow-x-auto">${{escapeHtml(call.function ? call.function.arguments : JSON.stringify(call))}}</pre>
            </div>
          `).join("");
        }}

        const parsedContent = marked.parse(msg.content || "");
        inner = `
          <div class="flex flex-col space-y-3 max-w-full">
            <div class="flex items-center space-x-2 text-xs font-medium text-slate-400">
              <span class="w-2 h-2 rounded-full bg-indigo-400"></span>
              <span>Hermes</span>
            </div>
            ${{reasoningHtml}}
            ${{toolCallsHtml}}
            <div class="prose prose-invert prose-sm sm:prose-base max-w-none text-slate-200 leading-relaxed">
              ${{parsedContent}}
            </div>
          </div>
        `;
      }} else if (isTool) {{
        inner = `
          <div class="bg-slate-900/60 border border-slate-800/80 rounded-lg p-3 text-xs font-mono">
            <details>
              <summary class="cursor-pointer text-slate-400 hover:text-slate-200 flex items-center space-x-2">
                <span class="text-amber-400">🔧 [Tool Result]</span>
                <span>${{msg.tool_name || "output"}}</span>
              </summary>
              <pre class="mt-2 bg-slate-950 p-3 rounded text-[11px] text-slate-300 overflow-x-auto border border-slate-800">${{escapeHtml(msg.content || "")}}</pre>
            </details>
          </div>
        `;
      }}

      div.innerHTML = inner;
      div.querySelectorAll('pre code').forEach((block) => {{
        hljs.highlightElement(block);
      }});
      return div;
    }}

    function escapeHtml(str) {{
      return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
    }}

    // Connect to SSE stream
    const evtSource = new EventSource(`/api/v1/shares/${{token}}/stream`);

    evtSource.addEventListener("initial", (e) => {{
      const data = JSON.parse(e.data);
      if (data.session) {{
        document.getElementById("session-title").innerText = data.session.title || "Hermes Session";
        if (data.session.model) {{
          document.getElementById("session-model").innerText = data.session.model;
        }}
      }}
      messagesContainer.innerHTML = "";
      data.messages.forEach(msg => {{
        messagesMap.set(msg.id, msg);
        messagesContainer.appendChild(renderMessage(msg));
      }});
      window.scrollTo(0, document.body.scrollHeight);
    }});

    evtSource.addEventListener("append", (e) => {{
      const msg = JSON.parse(e.data);
      if (!messagesMap.has(msg.id)) {{
        messagesMap.set(msg.id, msg);
        messagesContainer.appendChild(renderMessage(msg));
        window.scrollTo(0, document.body.scrollHeight);
      }}
    }});

    evtSource.addEventListener("update", (e) => {{
      const msg = JSON.parse(e.data);
      messagesMap.set(msg.id, msg);
      const existing = document.getElementById("msg-" + msg.id);
      if (existing) {{
        const newEl = renderMessage(msg);
        existing.replaceWith(newEl);
      }}
    }});

    evtSource.addEventListener("complete", () => {{
      const ind = document.getElementById("live-indicator");
      ind.innerHTML = `<span class="w-2 h-2 rounded-full bg-slate-500 mr-1.5"></span> Snapshot`;
      ind.className = "flex items-center text-slate-400";
      evtSource.close();
    }});

    evtSource.addEventListener("revoked", () => {{
      alert("This share link was revoked by the owner.");
      window.location.reload();
    }});

    evtSource.onerror = () => {{
      const ind = document.getElementById("live-indicator");
      ind.innerHTML = `<span class="w-2 h-2 rounded-full bg-amber-400 mr-1.5"></span> Reconnecting...`;
      ind.className = "flex items-center text-amber-400";
    }};
  </script>
</body>
</html>
"""
