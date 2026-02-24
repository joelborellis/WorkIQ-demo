"""
GraphService
------------
Direct Microsoft Graph API integration covering the full M365 surface.

Queries multiple Graph endpoints in parallel to build a structured snapshot
of the user's M365 data relevant to the question, then returns it in the
same ``CopilotChatResponse`` shape used by the other routes so the frontend
comparison panel works identically for all three routes.

Data sources (all fetched in parallel):
  Mail        – 5 most recent inbox emails
  Calendar    – Upcoming events (next 7 days)
  Teams       – 5 most recent chat conversations
  Files       – 5 recently modified OneDrive files
  People      – 5 frequent collaborators
  Search      – Cross-M365 content search using the question text

Key difference from the other routes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  Copilot Chat API  question → Microsoft's LLM → synthesised answer
  Retrieval API     question → semantic doc chunks (SharePoint/OneDrive)
  Graph API         question → raw structured M365 data, no LLM involved

Required Graph delegated scopes (on top of the base set):
  Calendars.Read     — /me/calendarView
  Files.Read.All     — /me/drive/recent, /search/query (driveItem)
  Mail.Read          — /me/messages, /search/query (message)
  Chat.Read          — /me/chats
  People.Read.All    — /me/people

Reference:
  https://learn.microsoft.com/en-us/graph/use-the-api
"""
from __future__ import annotations

import asyncio
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone

import httpx

from app.models.copilot import Attribution, CopilotChatResponse

logger = logging.getLogger(__name__)

GRAPH_V1 = "https://graph.microsoft.com/v1.0"

_MD_ESCAPE = re.compile(r'([\\`*_{}[\]()#+\-!|<>])')


def _esc(text: str | None) -> str:
    """Escape Markdown special characters in user-generated text."""
    return _MD_ESCAPE.sub(r'\\\1', text) if text else ""


def _fmt_dt(dt_str: str | None) -> str:
    """Format a Graph ISO datetime string to 'Mon DD, H:MM AM/PM'."""
    if not dt_str:
        return ""
    try:
        clean = dt_str.rstrip("Z").split(".")[0]
        dt = datetime.fromisoformat(clean)
        hour = dt.hour % 12 or 12
        minute = dt.strftime("%M")
        ampm = "AM" if dt.hour < 12 else "PM"
        return dt.strftime(f"%b %d, {hour}:{minute} {ampm}")
    except (ValueError, AttributeError):
        return dt_str[:16]


async def _get(client: httpx.AsyncClient, url: str) -> dict | None:
    """GET a Graph endpoint; returns parsed JSON or None on any error."""
    try:
        resp = await client.get(url)
        if resp.status_code != 200:
            logger.warning("Graph GET %s → %s  %s", url, resp.status_code, resp.text[:200])
            return None
        return resp.json()
    except httpx.HTTPError as exc:
        logger.warning("Graph GET %s error: %s", url, exc)
        return None


async def _search(client: httpx.AsyncClient, question: str) -> list[dict]:
    """
    POST /search/query for emails and files matching *question*.
    Returns a flat list of {name, url, summary, kind} dicts.
    Non-200 responses are silently swallowed.
    """
    # The Graph Search API does not allow mixing message and driveItem in a
    # single request — send them separately and combine the results.
    def _build_body(entity_type: str) -> dict:
        return {
            "requests": [{
                "entityTypes": [entity_type],
                "query": {"queryString": question},
                "size": 5,
            }]
        }

    def _parse_hits(data: dict) -> list[dict]:
        hits: list[dict] = []
        for result in data.get("value") or []:
            for hc in result.get("hitsContainers") or []:
                for hit in hc.get("hits") or []:
                    resource = hit.get("resource") or {}
                    odata_type = resource.get("@odata.type", "")
                    kind = odata_type.split(".")[-1] if odata_type else "item"
                    url  = resource.get("webUrl") or resource.get("webLink") or ""
                    name = resource.get("subject") or resource.get("name") or "(untitled)"
                    hits.append({
                        "name": name,
                        "url": url,
                        "summary": hit.get("summary") or "",
                        "kind": kind,
                    })
        return hits

    async def _search_one(entity_type: str) -> list[dict]:
        try:
            resp = await client.post("/search/query", json=_build_body(entity_type))
            if resp.status_code != 200:
                logger.warning("Graph search [%s] → %s: %s", entity_type, resp.status_code, resp.text[:200])
                return []
            return _parse_hits(resp.json())
        except httpx.HTTPError as exc:
            logger.warning("Graph search [%s] error: %s", entity_type, exc)
            return []

    mail_hits, file_hits = await asyncio.gather(
        _search_one("message"),
        _search_one("driveItem"),
    )
    return mail_hits + file_hits


class GraphService:
    """
    Fetches M365 data from multiple Graph endpoints in parallel and formats
    the results as Markdown inside a ``CopilotChatResponse``.

    A single instance is created at application startup and stored on
    ``app.state.graph_service``.
    """

    async def query(
        self,
        access_token: str,
        question: str,
        *,
        timezone_name: str = "UTC",  # noqa: ARG002 — kept for call-site symmetry
    ) -> CopilotChatResponse:
        """
        Fetch a snapshot of the user's M365 data and return it as a
        ``CopilotChatResponse``.

        All Graph endpoints are called in parallel; a failure on any single
        endpoint (e.g. missing permission) is logged and treated as empty
        so the others still succeed.

        Args:
            access_token:   A valid delegated Graph token.
            question:       Used as the search query for the Search endpoint.
            timezone_name:  Accepted but unused — kept for call-site symmetry.

        Returns:
            ``CopilotChatResponse`` with structured Markdown covering all
            available M365 data sources.
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        now = datetime.now(timezone.utc)
        end = now + timedelta(days=7)
        cal_start = now.strftime("%Y-%m-%dT%H:%M:%S.0000000")
        cal_end   = end.strftime("%Y-%m-%dT%H:%M:%S.0000000")

        async with httpx.AsyncClient(
            base_url=GRAPH_V1,
            headers=headers,
            timeout=30.0,
        ) as client:
            logger.debug("Graph API parallel fetch  question=%r", question)
            (
                emails_raw,
                calendar_raw,
                chats_raw,
                files_raw,
                people_raw,
                search_hits,
            ) = await asyncio.gather(
                _get(client, (
                    "/me/messages"
                    "?$select=subject,from,receivedDateTime,bodyPreview,importance"
                    "&$orderby=receivedDateTime DESC"
                    "&$top=5"
                )),
                _get(client, (
                    f"/me/calendarView"
                    f"?startDateTime={cal_start}&endDateTime={cal_end}"
                    f"&$select=subject,start,end,organizer,location"
                    f"&$top=10"
                    f"&$orderby=start/dateTime"
                )),
                _get(client, (
                    "/me/chats"
                    "?$select=id,topic,chatType,lastUpdatedDateTime"
                    "&$top=5"
                )),
                _get(client, (
                    "/me/drive/recent"
                    "?$top=5"
                    "&$select=name,webUrl,lastModifiedDateTime,lastModifiedBy,size"
                )),
                _get(client, (
                    "/me/people"
                    "?$top=5"
                    "&$select=displayName,jobTitle,department,scoredEmailAddresses"
                )),
                _search(client, question),
            )

        # ── Build Markdown sections ───────────────────────────────────────────
        parts: list[str] = []
        attributions: list[Attribution] = []

        # ── Emails ───────────────────────────────────────────────────────────
        emails = (emails_raw or {}).get("value") or []
        if emails:
            parts.append("## 📧 Recent Emails")
            parts.append("")
            for msg in emails:
                subject   = _esc(msg.get("subject") or "(no subject)")
                sender    = (msg.get("from") or {}).get("emailAddress") or {}
                from_name = _esc(sender.get("name") or "")
                from_addr = _esc(sender.get("address") or "")
                received  = _fmt_dt(msg.get("receivedDateTime"))
                preview   = _esc((msg.get("bodyPreview") or "")[:180])
                parts.append(f"**{subject}**")
                parts.append(f"*From: {from_name} \\<{from_addr}\\> · {received}*")
                if preview:
                    parts.append(preview)
                parts.append("")

        # ── Calendar ─────────────────────────────────────────────────────────
        events = (calendar_raw or {}).get("value") or []
        if events:
            parts.append("## 📅 Upcoming Calendar (next 7 days)")
            parts.append("")
            for evt in events:
                subject   = _esc(evt.get("subject") or "(no title)")
                start     = _fmt_dt((evt.get("start") or {}).get("dateTime"))
                end_dt    = _fmt_dt((evt.get("end") or {}).get("dateTime"))
                organizer = _esc(((evt.get("organizer") or {}).get("emailAddress") or {}).get("name") or "")
                location  = _esc(((evt.get("location") or {}).get("displayName")) or "")
                meta_parts = []
                if organizer: meta_parts.append(f"Organizer: {organizer}")
                if location:  meta_parts.append(f"📍 {location}")
                parts.append(f"**{subject}**")
                time_line = f"*{start} – {end_dt}*"
                if meta_parts:
                    time_line += f"  ·  {' · '.join(meta_parts)}"
                parts.append(time_line)
                parts.append("")

        # ── Teams chats ───────────────────────────────────────────────────────
        chats = (chats_raw or {}).get("value") or []
        if chats:
            parts.append("## 💬 Teams Chats")
            parts.append("")
            for chat in chats:
                topic     = _esc(chat.get("topic") or "(unnamed chat)")
                chat_type = (chat.get("chatType") or "").replace("ChatType.", "")
                updated   = _fmt_dt(chat.get("lastUpdatedDateTime"))
                parts.append(f"**{topic}**")
                parts.append(f"*{chat_type} · last active {updated}*")
                parts.append("")

        # ── Recent files ──────────────────────────────────────────────────────
        files = (files_raw or {}).get("value") or []
        if files:
            parts.append("## 📁 Recent OneDrive Files")
            parts.append("")
            for f in files:
                name       = _esc(f.get("name") or "")
                url        = f.get("webUrl") or ""
                modified   = _fmt_dt(f.get("lastModifiedDateTime"))
                modifier   = _esc(((f.get("lastModifiedBy") or {}).get("user") or {}).get("displayName") or "")
                if url:
                    parts.append(f"**[{name}]({url})**")
                    attributions.append(Attribution(title=name, url=url))
                else:
                    parts.append(f"**{name}**")
                meta = f"Modified {modified}"
                if modifier:
                    meta += f" by {modifier}"
                parts.append(f"*{meta}*")
                parts.append("")

        # ── People ────────────────────────────────────────────────────────────
        people = (people_raw or {}).get("value") or []
        if people:
            parts.append("## 👥 Frequent Collaborators")
            parts.append("")
            for person in people:
                name         = _esc(person.get("displayName") or "")
                job_title    = _esc(person.get("jobTitle") or "")
                department   = _esc(person.get("department") or "")
                scored_emails = person.get("scoredEmailAddresses") or []
                email        = _esc(scored_emails[0].get("address") if scored_emails else "")
                meta = " · ".join(filter(None, [job_title, department, email]))
                parts.append(f"**{name}**" + (f"  —  {meta}" if meta else ""))
                parts.append("")

        # ── Search results ────────────────────────────────────────────────────
        if search_hits:
            parts.append(f"## 🔍 Search: \"{_esc(question)}\"")
            parts.append("")
            for hit in search_hits:
                name    = _esc(hit["name"])
                url     = hit["url"]
                summary = _esc(hit["summary"][:180])
                kind    = _esc(hit["kind"])
                if url:
                    parts.append(f"**[{name}]({url})**  *{kind}*")
                    attributions.append(Attribution(title=name, url=url))
                else:
                    parts.append(f"**{name}**  *{kind}*")
                if summary:
                    parts.append(summary)
                parts.append("")

        if not parts:
            answer = (
                "_No data returned from Microsoft Graph. "
                "Verify that Calendars.Read, Files.Read.All, Mail.Read, "
                "Chat.Read, and People.Read.All permissions are granted._"
            )
        else:
            answer = "\n".join(parts).strip()

        return CopilotChatResponse(
            conversation_id=str(uuid.uuid4()),
            answer=answer,
            attributions=attributions,
            turn_count=1,
        )
