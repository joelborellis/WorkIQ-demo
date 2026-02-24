"""
RetrievalService
----------------
Thin async wrapper around the Microsoft Copilot Retrieval API.

Endpoint used:
  POST /copilot/retrieval  – retrieve semantically-relevant text chunks

Queries all three available data sources in parallel:
  sharePoint       – SharePoint document libraries
  oneDriveBusiness – OneDrive for Business files
  externalItem     – Copilot connectors (ServiceNow, Jira, etc.)

Results from all sources are merged and sorted by relevance score, then
returned as a ``CopilotChatResponse`` so the frontend comparison panel can
display both the Chat API and the Retrieval API routes without special-casing.

Key difference from CopilotService
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  Chat API:      Microsoft retrieves + Microsoft's LLM reasons → synthesised answer
  Retrieval API: Microsoft retrieves → ranked raw chunks → returned as-is

Reference:
  https://learn.microsoft.com/en-us/microsoft-365-copilot/extensibility/api/ai-services/retrieval/overview
"""
from __future__ import annotations

import asyncio
import logging
import re
import uuid

import httpx

from app.models.copilot import Attribution, CopilotChatResponse

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/beta"

# All data sources queried on every request
DATA_SOURCES = ["sharePoint", "oneDriveBusiness", "externalItem"]

# Human-readable label added to each hit's metadata line
SOURCE_LABELS: dict[str, str] = {
    "sharePoint":       "SharePoint",
    "oneDriveBusiness": "OneDrive",
    "externalItem":     "Connectors",
}

_MD_ESCAPE = re.compile(r'([\\`*_{}[\]()#+\-!|<>])')


def _escape_md(text: str) -> str:
    """Escape Markdown special characters in raw document-extracted text."""
    return _MD_ESCAPE.sub(r'\\\1', text)


async def _fetch_source(
    client: httpx.AsyncClient,
    question: str,
    data_source: str,
    max_results: int,
    filter_expression: str | None,
) -> tuple[str, list[dict]]:
    """
    Query one data source and return ``(data_source, hits)``.

    Non-200 responses are logged as warnings and treated as empty results so
    a single unavailable source (e.g. no connector permissions) does not fail
    the whole request.
    """
    body: dict = {
        "queryString": question,
        "dataSource": data_source,
        "maximumNumberOfResults": str(max_results),
        "resourceMetadata": ["title", "author"],
    }
    if filter_expression:
        body["filterExpression"] = filter_expression

    try:
        resp = await client.post("/copilot/retrieval", json=body)
    except httpx.HTTPError as exc:
        logger.warning("Retrieval API %s network error: %s", data_source, exc)
        return data_source, []

    if resp.status_code != 200:
        logger.warning(
            "Retrieval API %s returned %s: %s",
            data_source,
            resp.status_code,
            resp.text[:300],
        )
        return data_source, []

    hits = resp.json().get("retrievalHits", [])
    logger.debug("Retrieval API %s returned %d hit(s)", data_source, len(hits))
    return data_source, hits


class RetrievalService:
    """
    Calls the M365 Copilot Retrieval API across all three data sources
    (SharePoint, OneDrive, Connectors) in parallel and packages the merged,
    relevance-sorted results in the same ``CopilotChatResponse`` shape used
    by the Chat API so the frontend comparison panel works identically for
    both routes.

    A single instance is created at application startup and stored on
    ``app.state.retrieval_service``.
    """

    async def retrieve(
        self,
        access_token: str,
        question: str,
        *,
        max_results: int = 10,
        filter_expression: str | None = None,
        timezone: str = "UTC",  # noqa: ARG002 — kept for call-site symmetry
    ) -> CopilotChatResponse:
        """
        Retrieve relevant text chunks for *question* from all three data
        sources in parallel and return them as a ``CopilotChatResponse``.

        Args:
            access_token:      A valid delegated Graph token.
            question:          The user's natural language query (max 1 500 chars).
            max_results:       Chunks to request *per source* (1–25, default 10).
            filter_expression: Optional KQL filter applied to all sources, e.g.
                               ``'path:"https://contoso.sharepoint.com/sites/HR"'``.
            timezone:          Accepted but unused — kept for call-site symmetry
                               with the Chat API route.

        Returns:
            ``CopilotChatResponse`` where:
              • ``answer``          — merged hits from all sources, sorted by
                                      relevance, rendered as Markdown
              • ``attributions``    — source document links
              • ``conversation_id`` — a new UUID (Retrieval API is stateless)
              • ``turn_count``      — always ``1``
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(
            base_url=GRAPH_BASE,
            headers=headers,
            timeout=30.0,
        ) as client:
            logger.debug("Retrieval API query=%r sources=%s", question, DATA_SOURCES)
            source_results = await asyncio.gather(
                *[
                    _fetch_source(client, question, src, max_results, filter_expression)
                    for src in DATA_SOURCES
                ]
            )

        # ── Merge hits from all sources, tagging each with its origin ─────────
        all_hits: list[tuple[str, dict]] = []
        for data_source, hits in source_results:
            for hit in hits:
                all_hits.append((data_source, hit))

        # Sort merged list by best per-hit relevance score, highest first
        def _best_relevance(pair: tuple[str, dict]) -> float:
            extracts = pair[1].get("extracts", [])
            return max((e.get("relevanceScore", 0.0) for e in extracts), default=0.0)

        all_hits.sort(key=_best_relevance, reverse=True)

        logger.debug(
            "Retrieval API merged %d hit(s) across %d source(s)",
            len(all_hits),
            sum(1 for _, hits in source_results if hits),
        )

        # ── Format hits as Markdown ───────────────────────────────────────────
        answer_parts: list[str] = []
        attributions: list[Attribution] = []

        for data_source, hit in all_hits:
            metadata = hit.get("resourceMetadata", {})
            title    = metadata.get("title") or ""
            web_url  = hit.get("webUrl", "")
            author   = metadata.get("author")
            extracts = hit.get("extracts", [])
            label    = (hit.get("sensitivityLabel") or {}).get("displayName")

            # Attribution (one per source document)
            if title or web_url:
                attributions.append(Attribution(
                    title=title or web_url,
                    url=web_url or None,
                ))

            # ── Title line ────────────────────────────────────────────────────
            safe_title = _escape_md(title) if title else web_url
            heading = (
                f"**[{safe_title}]({web_url})**" if web_url
                else f"**{safe_title}**"
            )

            # ── Metadata line: relevance · source · author · sensitivity ──────
            best_relevance = max(
                (e.get("relevanceScore", 0.0) for e in extracts),
                default=0.0,
            )
            meta_parts = [
                f"{best_relevance:.0%} match",
                SOURCE_LABELS.get(data_source, data_source),
            ]
            if author:
                meta_parts.append(_escape_md(author))
            if label:
                meta_parts.append(f"🔒 {label}")

            answer_parts.append(heading)
            answer_parts.append(f"*{' · '.join(meta_parts)}*")
            answer_parts.append("")

            # ── Extract text — all fragments joined, markdown-escaped ─────────
            # Multiple extracts per hit are fragments of the same document;
            # join them so there are no stray relevance markers mid-sentence.
            chunks = [
                _escape_md(e.get("text", "").strip())
                for e in extracts
                if e.get("text", "").strip()
            ]
            if chunks:
                answer_parts.append(" ".join(chunks))

            answer_parts.append("")
            answer_parts.append("---")
            answer_parts.append("")

        if not answer_parts:
            answer = (
                "_No results found across SharePoint, OneDrive, or Connectors "
                "for this query._"
            )
        else:
            answer = "\n".join(answer_parts).strip()

        return CopilotChatResponse(
            conversation_id=str(uuid.uuid4()),
            answer=answer,
            attributions=attributions,
            turn_count=1,
        )
