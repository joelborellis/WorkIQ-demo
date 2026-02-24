"""
WorkIQ Graph API — End-to-End Test Script
==========================================
Tests the /api/v1/graph_api endpoint at three layers:

  Layer 1  Direct Graph API calls   (auth / permissions / raw JSON)
  Layer 2  GraphService formatting  (our backend Markdown rendering)
  Layer 3  Backend HTTP endpoint    (running server, session cookie required)

Usage
─────
  # Layers 1 + 2 only (browser sign-in, no backend required):
  uv run python tests/test_graph_endpoint.py

  # Custom question (used as search query in Layer 1):
  uv run python tests/test_graph_endpoint.py --question "budget planning"

  # All three layers (backend must be running, user must be signed in):
  uv run python tests/test_graph_endpoint.py --cookie "workiq_session=abc..."

  # Raw JSON only (skip formatting layer):
  uv run python tests/test_graph_endpoint.py --raw-only

Getting your session cookie for Layer 3
────────────────────────────────────────
  1. Start the backend:  uv run uvicorn app.main:app --reload
  2. Open http://localhost:5173 in your browser and sign in
  3. Open DevTools → Application → Cookies → http://localhost:8000
  4. Copy the value of the "workiq_session" cookie
  5. Re-run: uv run python tests/test_graph_endpoint.py --cookie "workiq_session=<value>"

Azure AD setup (one-time)
──────────────────────────
  The app is a confidential client, so we use auth-code flow with a local
  redirect server instead of device-code flow.

  Entra ID → App registrations → <your app> → Authentication
  → Add platform → Web → Redirect URI → http://localhost:9998
"""

from __future__ import annotations

import argparse
import asyncio
import http.server
import json
import os
import sys
import threading
import webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
import msal
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

TENANT_ID     = os.environ["TENANT_ID"]
CLIENT_ID     = os.environ["CLIENT_ID"]
CLIENT_SECRET = os.environ["CLIENT_SECRET"]
GRAPH_V1      = "https://graph.microsoft.com/v1.0"

REDIRECT_PORT = 9998
REDIRECT_URI  = f"http://localhost:{REDIRECT_PORT}"

SCOPES = [
    "User.Read",
    "Mail.Read",
    "Calendars.Read",
    "Files.Read.All",
    "Sites.Read.All",
    "Chat.Read",
    "People.Read.All",
]

# ── ANSI helpers ──────────────────────────────────────────────────────────────
GREEN  = "\033[32m"
RED    = "\033[31m"
YELLOW = "\033[33m"
CYAN   = "\033[36m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"

def ok(msg: str)    -> None: print(f"{GREEN}✓{RESET} {msg}")
def fail(msg: str)  -> None: print(f"{RED}✗{RESET} {msg}")
def info(msg: str)  -> None: print(f"{CYAN}ℹ{RESET} {msg}")
def warn(msg: str)  -> None: print(f"{YELLOW}⚠{RESET} {msg}")
def hdr(title: str) -> None:
    bar = "─" * max(0, 60 - len(title))
    print(f"\n{BOLD}── {title} {bar}{RESET}")


# ── Auth (auth-code flow with local redirect server) ──────────────────────────

class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    received: dict[str, str] = {}

    def do_GET(self) -> None:
        _CallbackHandler.received = {
            k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()
        }
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<h2 style='font-family:sans-serif'>Sign-in complete. You can close this tab.</h2>")

    def log_message(self, *_args) -> None:
        pass


def get_graph_token() -> str:
    app = msal.ConfidentialClientApplication(
        client_id=CLIENT_ID,
        client_credential=CLIENT_SECRET,
        authority=f"https://login.microsoftonline.com/{TENANT_ID}",
    )

    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])
        if result and "access_token" in result:
            ok("Using cached MSAL token")
            return result["access_token"]

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
    print(f"  If it doesn't open: {CYAN}{flow['auth_uri']}{RESET}\n")
    print(f"  {DIM}(Waiting up to 120 s...){RESET}")
    webbrowser.open(flow["auth_uri"])

    t.join(timeout=120)
    server.server_close()

    if not _CallbackHandler.received:
        raise RuntimeError(
            f"Sign-in timed out. Make sure http://localhost:{REDIRECT_PORT} is "
            "registered as a redirect URI in your Azure AD app (Authentication → Web)."
        )

    result = app.acquire_token_by_auth_code_flow(flow, _CallbackHandler.received)
    if "access_token" not in result:
        raise RuntimeError(f"Token exchange failed: {result.get('error_description', result)}")

    username = result.get("id_token_claims", {}).get("preferred_username", "unknown")
    ok(f"Signed in as {username}")
    return result["access_token"]


# ── Layer 1 — Direct Graph API calls ─────────────────────────────────────────

async def _get(client: httpx.AsyncClient, label: str, url: str) -> tuple[str, dict | None]:
    try:
        resp = await client.get(url)
        if resp.status_code == 200:
            return label, resp.json()
        warn(f"[{label}] HTTP {resp.status_code}  {resp.text[:150]}")
        return label, None
    except httpx.HTTPError as exc:
        fail(f"[{label}] {exc}")
        return label, None


async def _search(client: httpx.AsyncClient, question: str) -> list[dict]:
    # message and driveItem cannot be combined in one request — send separately.
    def _parse(data: dict) -> list[dict]:
        hits = []
        for result in (data.get("value") or []):
            for hc in (result.get("hitsContainers") or []):
                for hit in (hc.get("hits") or []):
                    resource = hit.get("resource") or {}
                    hits.append({
                        "name": resource.get("subject") or resource.get("name") or "(untitled)",
                        "url": resource.get("webUrl") or resource.get("webLink") or "",
                        "summary": hit.get("summary") or "",
                        "kind": (resource.get("@odata.type") or "").split(".")[-1],
                    })
        return hits

    async def _search_one(entity_type: str) -> list[dict]:
        body = {"requests": [{"entityTypes": [entity_type], "query": {"queryString": question}, "size": 5}]}
        try:
            resp = await client.post("/search/query", json=body)
            if resp.status_code != 200:
                warn(f"[Search/{entity_type}] HTTP {resp.status_code}  {resp.text[:150]}")
                return []
            return _parse(resp.json())
        except httpx.HTTPError as exc:
            fail(f"[Search/{entity_type}] {exc}")
            return []

    mail_hits, file_hits = await asyncio.gather(
        _search_one("message"),
        _search_one("driveItem"),
    )
    return mail_hits + file_hits


async def test_graph_direct(token: str, question: str) -> dict:
    hdr("LAYER 1 — Direct Graph API calls (parallel)")
    info(f"Question / search term: {question!r}\n")

    now = datetime.now(timezone.utc)
    end = now + timedelta(days=7)
    cal_start = now.strftime("%Y-%m-%dT%H:%M:%S.0000000")
    cal_end   = end.strftime("%Y-%m-%dT%H:%M:%S.0000000")

    async with httpx.AsyncClient(
        base_url=GRAPH_V1,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=30.0,
    ) as client:
        (
            (_, emails_raw),
            (_, calendar_raw),
            (_, chats_raw),
            (_, files_raw),
            (_, people_raw),
            search_hits,
        ) = await asyncio.gather(
            _get(client, "Mail",     "/me/messages?$select=subject,from,receivedDateTime,bodyPreview&$orderby=receivedDateTime DESC&$top=5"),
            _get(client, "Calendar", f"/me/calendarView?startDateTime={cal_start}&endDateTime={cal_end}&$select=subject,start,end,organizer&$top=10&$orderby=start/dateTime"),
            _get(client, "Teams",    "/me/chats?$select=id,topic,chatType,lastUpdatedDateTime&$top=5"),
            _get(client, "Files",    "/me/drive/recent?$top=5&$select=name,webUrl,lastModifiedDateTime,lastModifiedBy"),
            _get(client, "People",   "/me/people?$top=5&$select=displayName,jobTitle,scoredEmailAddresses"),
            _search(client, question),
        )

    results = {
        "emails":   emails_raw,
        "calendar": calendar_raw,
        "chats":    chats_raw,
        "files":    files_raw,
        "people":   people_raw,
        "search":   search_hits,
    }

    # Summary
    def _count(raw, key="value"):
        if isinstance(raw, dict):
            return len(raw.get(key) or [])
        if isinstance(raw, list):
            return len(raw)
        return 0

    print()
    for label, data in [
        ("Mail",     emails_raw),
        ("Calendar", calendar_raw),
        ("Teams",    chats_raw),
        ("Files",    files_raw),
        ("People",   people_raw),
    ]:
        n = _count(data)
        sym = ok if n > 0 else warn
        sym(f"[{label:8}] {n} item(s)" + ("" if n > 0 else " — check permissions or empty source"))

    n_search = len(search_hits)
    (ok if n_search > 0 else warn)(f"[Search  ] {n_search} hit(s) for {question!r}")

    return results


# ── Layer 2 — GraphService formatting ────────────────────────────────────────

def _fmt_dt(dt_str: str | None) -> str:
    if not dt_str:
        return ""
    try:
        clean = dt_str.rstrip("Z").split(".")[0]
        dt = datetime.fromisoformat(clean)
        hour = dt.hour % 12 or 12
        return dt.strftime(f"%b %d, {hour}:%M {'AM' if dt.hour < 12 else 'PM'}")
    except (ValueError, AttributeError):
        return dt_str[:16]


def test_service_format(results: dict, question: str) -> None:
    hdr("LAYER 2 — GraphService formatting")

    parts: list[str] = []

    emails = (results.get("emails") or {}).get("value") or []
    if emails:
        parts.append(f"  {BOLD}📧 Emails ({len(emails)}){RESET}")
        for m in emails[:3]:
            subj = m.get("subject") or "(no subject)"
            sender = (m.get("from") or {}).get("emailAddress") or {}
            parts.append(f"    • {subj[:60]}  {DIM}from {sender.get('name','')}{RESET}")

    events = (results.get("calendar") or {}).get("value") or []
    if events:
        parts.append(f"  {BOLD}📅 Calendar ({len(events)}){RESET}")
        for e in events[:3]:
            parts.append(f"    • {e.get('subject','')[:60]}  {DIM}{_fmt_dt((e.get('start') or {}).get('dateTime'))}{RESET}")

    chats = (results.get("chats") or {}).get("value") or []
    if chats:
        parts.append(f"  {BOLD}💬 Teams ({len(chats)}){RESET}")
        for c in chats[:3]:
            parts.append(f"    • {c.get('topic') or '(unnamed)'}")

    files = (results.get("files") or {}).get("value") or []
    if files:
        parts.append(f"  {BOLD}📁 Files ({len(files)}){RESET}")
        for f in files[:3]:
            parts.append(f"    • {f.get('name','')[:60]}")

    people = (results.get("people") or {}).get("value") or []
    if people:
        parts.append(f"  {BOLD}👥 People ({len(people)}){RESET}")
        for p in people[:3]:
            parts.append(f"    • {p.get('displayName','')}  {DIM}{p.get('jobTitle','')}{RESET}")

    search_hits = results.get("search") or []
    if search_hits:
        parts.append(f"  {BOLD}🔍 Search hits ({len(search_hits)}){RESET}")
        for h in search_hits[:3]:
            parts.append(f"    • [{h.get('kind','')}] {h.get('name','')[:60]}")

    if parts:
        ok("Data preview:")
        print()
        print("\n".join(parts))
    else:
        warn("No data to format — all endpoints returned empty")


# ── Layer 3 — Backend HTTP endpoint ──────────────────────────────────────────

async def test_backend_endpoint(question: str, session_cookie: str, base_url: str) -> None:
    hdr("LAYER 3 — Backend HTTP endpoint")
    info(f"Base URL : {base_url}")
    info(f"Cookie   : {session_cookie[:60]}{'...' if len(session_cookie) > 60 else ''}")

    cookies: dict[str, str] = {}
    if "=" in session_cookie:
        name, _, value = session_cookie.partition("=")
        cookies[name.strip()] = value.strip()
    else:
        cookies["workiq_session"] = session_cookie.strip()

    async with httpx.AsyncClient(base_url=base_url, timeout=60.0) as client:
        print()
        try:
            h = await client.get("/health")
            if h.status_code == 200:
                ok(f"Health check passed: {h.json()}")
            else:
                fail(f"Health check returned {h.status_code}")
                return
        except httpx.ConnectError:
            fail(f"Cannot connect to {base_url}")
            info("Start the backend:  uv run uvicorn app.main:app --reload")
            return

        me = await client.get("/auth/me", cookies=cookies)
        if me.status_code != 200:
            fail(f"/auth/me returned {me.status_code} — session may be invalid or expired")
            print(f"  {DIM}{me.text}{RESET}")
            info("Sign in at http://localhost:5173 and copy a fresh workiq_session cookie")
            return
        user = me.json()
        ok(f"Session valid — signed in as {user.get('name')} ({user.get('email')})")

        print()
        info(f"POST {base_url}/api/v1/graph_api  question={question!r}")
        resp = await client.post(
            "/api/v1/graph_api",
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
        description="End-to-end test for the WorkIQ /api/v1/graph_api endpoint",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--question", default="project planning",
                        help="Question / search term (default: 'project planning')")
    parser.add_argument("--cookie",   default="",
                        help='Backend session cookie, e.g. "workiq_session=abc..." (enables Layer 3)')
    parser.add_argument("--url",      default="http://localhost:8000",
                        help="Backend base URL (default: http://localhost:8000)")
    parser.add_argument("--raw-only", action="store_true",
                        help="Skip Layer 2 formatting preview")
    args = parser.parse_args()

    print(f"\n{BOLD}WorkIQ Graph API — End-to-End Test{RESET}")
    print(f"  Question : {CYAN}{args.question!r}{RESET}")
    session_cookie = args.cookie or os.getenv("WORKIQ_SESSION", "")
    print(f"  Layers   : 1 + 2{' + 3' if session_cookie else ''}")

    try:
        token = get_graph_token()
    except Exception as exc:
        fail(f"Authentication failed: {exc}")
        sys.exit(1)

    results = await test_graph_direct(token, args.question)

    if not args.raw_only:
        test_service_format(results, args.question)

    if session_cookie:
        await test_backend_endpoint(args.question, session_cookie, args.url)
    else:
        hdr("LAYER 3 — Backend HTTP endpoint")
        warn("Skipped — no session cookie provided")
        info("Sign in at http://localhost:5173, copy the workiq_session cookie, then re-run:")
        info('  uv run python tests/test_graph_endpoint.py --cookie "workiq_session=<value>"')

    print()


if __name__ == "__main__":
    asyncio.run(main())
