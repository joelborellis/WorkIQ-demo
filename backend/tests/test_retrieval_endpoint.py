"""
WorkIQ Retrieval API — End-to-End Test Script
===============================================
Tests the retrieval pipeline at three layers so you can pinpoint exactly
where a failure occurs:

  Layer 1  Direct Graph API call    (auth / network / permissions)
  Layer 2  RetrievalService format  (our backend parsing + formatting)
  Layer 3  Backend HTTP endpoint    (running server, session cookie required)

Usage
─────
  # Layers 1 + 2 only (device-code sign-in, no backend required):
  uv run python tests/test_retrieval_endpoint.py

  # All three layers (backend must be running, user must be signed in):
  uv run python tests/test_retrieval_endpoint.py --cookie "workiq_session=abc123..."

  # Custom question:
  uv run python tests/test_retrieval_endpoint.py --question "Q4 budget plans"

  # Show raw JSON only, skip the formatting layer:
  uv run python tests/test_retrieval_endpoint.py --raw-only

Getting your session cookie for Layer 3
────────────────────────────────────────
  1. Start the backend:  uv run uvicorn app.main:app --reload
  2. Open http://localhost:5173 in your browser and sign in
  3. Open DevTools → Application → Cookies → http://localhost:8000
  4. Copy the value of the "workiq_session" cookie
  5. Re-run: uv run python tests/test_retrieval_endpoint.py --cookie "workiq_session=<value>"
"""

from __future__ import annotations

import argparse
import asyncio
import http.server
import json
import os
import re
import sys
import threading
import webbrowser
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
import msal
from dotenv import load_dotenv

# Load .env from the backend root (one level above tests/)
load_dotenv(Path(__file__).parent.parent / ".env")

TENANT_ID     = os.environ["TENANT_ID"]
CLIENT_ID     = os.environ["CLIENT_ID"]
CLIENT_SECRET = os.environ["CLIENT_SECRET"]   # required — app is a confidential client
GRAPH_BASE    = "https://graph.microsoft.com/beta"

# Local redirect URI used by the auth-code flow.
# Add http://localhost:9998 as a redirect URI in your Azure AD app registration.
REDIRECT_PORT = 9998
REDIRECT_URI  = f"http://localhost:{REDIRECT_PORT}"

# Scopes needed for the Retrieval API (lighter than Chat API)
SCOPES = [
    "Files.Read.All",
    "Sites.Read.All",
    "ExternalItem.Read.All",
]

# ── ANSI colour helpers ───────────────────────────────────────────────────────
GREEN  = "\033[32m"
RED    = "\033[31m"
YELLOW = "\033[33m"
CYAN   = "\033[36m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"

def ok(msg: str)   -> None: print(f"{GREEN}✓{RESET} {msg}")
def fail(msg: str) -> None: print(f"{RED}✗{RESET} {msg}")
def info(msg: str) -> None: print(f"{CYAN}ℹ{RESET} {msg}")
def warn(msg: str) -> None: print(f"{YELLOW}⚠{RESET} {msg}")
def hdr(title: str) -> None:
    bar = "─" * max(0, 60 - len(title))
    print(f"\n{BOLD}── {title} {bar}{RESET}")


# ── Auth ─────────────────────────────────────────────────────────────────────
# The app registration is a confidential client (has a client_secret), so
# device-code flow is unavailable.  We use auth-code flow instead, catching
# the redirect with a temporary local HTTP server on REDIRECT_PORT.
#
# One-time Azure AD setup required:
#   Entra ID → App registrations → <your app> → Authentication
#   → Add platform → Web → Redirect URI → http://localhost:9998
# ─────────────────────────────────────────────────────────────────────────────

class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    """Single-use HTTP handler that captures the OAuth callback query string."""
    received: dict[str, str] = {}

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        _CallbackHandler.received = {
            k: v[0] for k, v in parse_qs(parsed.query).items()
        }
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(
            b"<h2 style='font-family:sans-serif'>Sign-in complete. "
            b"You can close this tab.</h2>"
        )

    def log_message(self, *_args) -> None:
        pass  # suppress access log noise


def get_graph_token() -> str:
    """Acquire a delegated Graph token via auth-code flow + local redirect server."""
    app = msal.ConfidentialClientApplication(
        client_id=CLIENT_ID,
        client_credential=CLIENT_SECRET,
        authority=f"https://login.microsoftonline.com/{TENANT_ID}",
    )

    # Try silent refresh first (works on subsequent runs)
    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])
        if result and "access_token" in result:
            ok("Using cached MSAL token")
            return result["access_token"]

    # Start a one-shot local server to receive the redirect
    _CallbackHandler.received = {}
    server = http.server.HTTPServer(("localhost", REDIRECT_PORT), _CallbackHandler)
    t = threading.Thread(target=server.handle_request, daemon=True)
    t.start()

    flow = app.initiate_auth_code_flow(scopes=SCOPES, redirect_uri=REDIRECT_URI)
    if "error" in flow:
        server.server_close()
        raise RuntimeError(f"Failed to start auth flow: {flow}")

    print(f"\n{BOLD}Sign-in required:{RESET}")
    print(f"  A browser window will open — sign in with your Microsoft 365 account.")
    print(f"  If it doesn't open automatically, visit:")
    print(f"  {CYAN}{flow['auth_uri']}{RESET}\n")
    print(f"  {DIM}(Waiting up to 120 s for sign-in...){RESET}")
    webbrowser.open(flow["auth_uri"])

    t.join(timeout=120)
    server.server_close()

    if not _CallbackHandler.received:
        raise RuntimeError(
            "Sign-in timed out or was cancelled.\n"
            f"Make sure http://localhost:{REDIRECT_PORT} is registered as a redirect URI\n"
            "in your Azure AD app registration under Authentication → Web."
        )

    result = app.acquire_token_by_auth_code_flow(flow, _CallbackHandler.received)
    if "access_token" not in result:
        raise RuntimeError(
            f"Token exchange failed: {result.get('error_description', result)}"
        )

    username = result.get("id_token_claims", {}).get("preferred_username", "unknown")
    ok(f"Signed in as {username}")
    return result["access_token"]


# ── Layer 1 — Direct Graph API calls (all three sources, parallel) ───────────

DATA_SOURCES = ["sharePoint", "oneDriveBusiness", "externalItem"]


async def _query_one_source(
    client: httpx.AsyncClient,
    token: str,
    question: str,
    data_source: str,
) -> tuple[str, dict | None]:
    """Fire one POST /copilot/retrieval request; return (data_source, data_or_None)."""
    body = {
        "queryString": question,
        "dataSource": data_source,
        "maximumNumberOfResults": "10",
        "resourceMetadata": ["title", "author"],
    }
    try:
        resp = await client.post(
            "/copilot/retrieval",
            json=body,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
    except httpx.TimeoutException:
        fail(f"[{data_source}] Request timed out after 30 s")
        return data_source, None
    except httpx.ConnectError as e:
        fail(f"[{data_source}] Network error: {e}")
        return data_source, None

    if resp.status_code == 401:
        fail(f"[{data_source}] 401 Unauthorized — check scopes / Copilot license")
        print(f"  {DIM}{resp.text[:400]}{RESET}")
        return data_source, None
    if resp.status_code == 403:
        fail(f"[{data_source}] 403 Forbidden — admin consent may not be granted")
        print(f"  {DIM}{resp.text[:400]}{RESET}")
        return data_source, None
    if resp.status_code != 200:
        fail(f"[{data_source}] HTTP {resp.status_code}")
        print(f"  {DIM}{resp.text[:400]}{RESET}")
        return data_source, None

    return data_source, resp.json()


async def test_graph_direct(
    token: str, question: str
) -> dict[str, dict]:
    """Query all three data sources in parallel; return {data_source: raw_data}."""
    hdr("LAYER 1 — Direct Graph API calls (all sources in parallel)")
    info(f"Question: {question!r}")
    info(f"Sources : {', '.join(DATA_SOURCES)}\n")

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30.0) as client:
        results = await asyncio.gather(
            *[_query_one_source(client, token, question, src) for src in DATA_SOURCES]
        )

    totals: dict[str, dict] = {}
    for data_source, data in results:
        if data is None:
            continue
        hits = data.get("retrievalHits", [])
        totals[data_source] = data
        if not hits:
            warn(f"[{data_source}] 200 OK but no hits returned")
            continue
        ok(f"[{data_source}] {len(hits)} hit(s)")
        for i, hit in enumerate(hits, 1):
            meta     = hit.get("resourceMetadata", {})
            extracts = hit.get("extracts", [])
            title    = meta.get("title") or hit.get("webUrl", "(no title)")
            best_rel = max((e.get("relevanceScore", 0.0) for e in extracts), default=0.0)
            print(f"    {DIM}[{i:2}]{RESET}  {title}")
            print(f"          {DIM}{len(extracts)} extract(s) · best relevance {best_rel:.0%}{RESET}")

    if not totals:
        fail("All sources returned errors — see messages above")

    return totals


# ── Layer 2 — RetrievalService formatting ────────────────────────────────────

_MD_ESCAPE_RE = re.compile(r'([\\`*_{}[\]()#+\-!|<>])')

def _escape_md(text: str) -> str:
    return _MD_ESCAPE_RE.sub(r'\\\1', text)


def test_service_format(all_results: dict[str, dict]) -> None:
    hdr("LAYER 2 — RetrievalService formatting")

    if not all_results:
        warn("No results to format")
        return

    for data_source, raw_data in all_results.items():
        hits = raw_data.get("retrievalHits", [])
        print(f"\n  {BOLD}── {data_source}{RESET}  ({len(hits)} hit(s))")
        if not hits:
            warn(f"  No hits from {data_source}")
            continue
        _format_hits(hits)


def _format_hits(hits: list[dict]) -> None:

    parts: list[str] = []
    for hit in hits:
        meta     = hit.get("resourceMetadata", {})
        title    = meta.get("title") or ""
        web_url  = hit.get("webUrl", "")
        author   = meta.get("author")
        extracts = hit.get("extracts", [])
        label    = (hit.get("sensitivityLabel") or {}).get("displayName")

        safe_title = _escape_md(title) if title else web_url
        heading = (
            f"**[{safe_title}]({web_url})**" if web_url
            else f"**{safe_title}**"
        )

        best_rel = max((e.get("relevanceScore", 0.0) for e in extracts), default=0.0)
        meta_parts = [f"{best_rel:.0%} match"]
        if author: meta_parts.append(_escape_md(author))
        if label:  meta_parts.append(f"🔒 {label}")

        parts.append(heading)
        parts.append(f"*{' · '.join(meta_parts)}*")
        parts.append("")

        chunks = [
            _escape_md(e.get("text", "").strip())
            for e in extracts
            if e.get("text", "").strip()
        ]
        if chunks:
            parts.append(" ".join(chunks))

        parts.append("")
        parts.append("---")
        parts.append("")

    answer = "\n".join(parts).strip()
    ok(f"Formatted markdown output ({len(answer)} chars):")
    print()
    preview = answer[:2000]
    print(preview)
    if len(answer) > 2000:
        print(f"\n{DIM}  ... ({len(answer) - 2000} more chars){RESET}")


# ── Layer 3 — Backend HTTP endpoint ──────────────────────────────────────────

async def test_backend_endpoint(
    question: str,
    session_cookie: str,
    base_url: str,
) -> None:
    hdr("LAYER 3 — Backend HTTP endpoint")
    info(f"Base URL : {base_url}")
    info(f"Cookie   : {session_cookie[:60]}{'...' if len(session_cookie) > 60 else ''}")

    # Parse "name=value" or bare value
    cookies: dict[str, str] = {}
    if "=" in session_cookie:
        name, _, value = session_cookie.partition("=")
        cookies[name.strip()] = value.strip()
    else:
        cookies["workiq_session"] = session_cookie.strip()

    async with httpx.AsyncClient(base_url=base_url, timeout=60.0) as client:

        # 1. Health check
        print()
        try:
            h = await client.get("/health")
            if h.status_code == 200:
                ok(f"Health check passed: {h.json()}")
            else:
                fail(f"Health check returned {h.status_code}")
                return
        except httpx.ConnectError:
            fail(f"Cannot connect to backend at {base_url}")
            info("Make sure the backend is running:  uv run uvicorn app.main:app --reload")
            return

        # 2. Verify session
        me = await client.get("/auth/me", cookies=cookies)
        if me.status_code != 200:
            fail(f"/auth/me returned {me.status_code} — session may be invalid or expired")
            print(f"  {DIM}{me.text}{RESET}")
            info("Sign in at http://localhost:5173 and copy a fresh workiq_session cookie from DevTools")
            return
        user = me.json()
        ok(f"Session valid — signed in as {user.get('name')} ({user.get('email')})")

        # 3. Call /api/v1/retrieval_api
        print()
        info(f"POST {base_url}/api/v1/retrieval_api  question={question!r}")
        resp = await client.post(
            "/api/v1/retrieval_api",
            json={"question": question},
            cookies=cookies,
        )

    print(f"  HTTP {BOLD}{resp.status_code}{RESET}")

    if resp.status_code == 200:
        data = resp.json()
        answer = data.get("answer", "")
        attrs  = data.get("attributions", [])
        ok(f"Endpoint returned 200  ({len(answer)} chars, {len(attrs)} attribution(s))")
        print(f"\n  {BOLD}answer (first 800 chars):{RESET}")
        print(f"  {answer[:800]}")
        if attrs:
            print(f"\n  {BOLD}attributions:{RESET}")
            for a in attrs[:5]:
                print(f"    • {a.get('title')}  {DIM}{a.get('url','')[:80]}{RESET}")
    else:
        fail(f"Endpoint returned {resp.status_code}")
        print(f"  {DIM}{resp.text[:1000]}{RESET}")


# ── Entry point ───────────────────────────────────────────────────────────────

async def main() -> None:
    parser = argparse.ArgumentParser(
        description="End-to-end test for the WorkIQ /api/v1/retrieval_api endpoint",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--question",
        default="project planning documents",
        help="Natural language query to test with (default: 'project planning documents')",
    )
    parser.add_argument(
        "--cookie",
        default="",
        help='Backend session cookie, e.g. "workiq_session=abc123..." (enables Layer 3)',
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Backend base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--raw-only",
        action="store_true",
        help="Skip Layer 2 formatting output (useful when inspecting raw Graph JSON)",
    )
    args = parser.parse_args()

    print(f"\n{BOLD}WorkIQ Retrieval API — End-to-End Test{RESET}")
    print(f"  Question : {CYAN}{args.question!r}{RESET}")
    print(f"  Layers   : 1 + 2{' + 3' if args.cookie or os.getenv('WORKIQ_SESSION') else ''}")

    # ── Layers 1 + 2 ─────────────────────────────────────────────────────────
    try:
        token = get_graph_token()
    except Exception as exc:
        fail(f"Authentication failed: {exc}")
        sys.exit(1)

    all_results = await test_graph_direct(token, args.question)

    if all_results and not args.raw_only:
        test_service_format(all_results)

    # ── Layer 3 (optional) ────────────────────────────────────────────────────
    session_cookie = args.cookie or os.getenv("WORKIQ_SESSION", "")
    if session_cookie:
        await test_backend_endpoint(args.question, session_cookie, args.url)
    else:
        hdr("LAYER 3 — Backend HTTP endpoint")
        warn("Skipped — no session cookie provided")
        info("To also test the backend endpoint, sign in at http://localhost:5173,")
        info("copy the workiq_session cookie from DevTools, then re-run with:")
        info('  uv run python tests/test_retrieval_endpoint.py --cookie "workiq_session=<value>"')

    print()


if __name__ == "__main__":
    asyncio.run(main())
