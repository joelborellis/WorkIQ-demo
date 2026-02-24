"""
CopilotService
--------------
Thin async wrapper around the Microsoft Graph beta Copilot Chat API.

Endpoints used:
  POST /copilot/conversations              – create a new conversation
  POST /copilot/conversations/{id}/chat   – send a message and get the reply

Reference:
  https://learn.microsoft.com/en-us/microsoft-365-copilot/extensibility/api/ai-services/chat/overview
"""
from __future__ import annotations

import logging

import httpx

from app.models.copilot import Attribution, CopilotChatResponse

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/beta"


class CopilotService:
    """
    Provides ``chat()`` to forward a question to the M365 Copilot Chat API
    and return a structured response.

    Conversation lifecycle
    ~~~~~~~~~~~~~~~~~~~~~~
    - If ``conversation_id`` is ``None``, a new conversation is created first.
    - The returned ``CopilotChatResponse.conversation_id`` should be stored by
      the caller and passed back on the next turn for multi-turn conversations.

    A single instance is created at application startup and stored on
    ``app.state.copilot_service``.
    """

    async def chat(
        self,
        access_token: str,
        question: str,
        conversation_id: str | None,
        *,
        file_uris: list[str] | None = None,
        additional_context: list[str] | None = None,
        web_search: bool = True,
        timezone: str = "UTC",
    ) -> CopilotChatResponse:
        """
        Send *question* to the Copilot Chat API and return the answer.

        Args:
            access_token:       A valid delegated Graph API token (from OBO flow).
            question:           The user's natural language prompt.
            conversation_id:    Existing conversation to continue, or ``None`` to start fresh.
            file_uris:          SharePoint/OneDrive URIs to use as grounding context.
            additional_context: Extra text snippets added to ``additionalContext``.
            web_search:         Toggle web search grounding (per-turn setting).
            timezone:           IANA timezone for the ``locationHint``.

        Returns:
            A ``CopilotChatResponse`` with the answer, attributions, and conversation ID.

        Raises:
            ``httpx.HTTPStatusError`` on a non-2xx response from Graph.
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(
            base_url=GRAPH_BASE,
            headers=headers,
            timeout=120.0,  # Copilot can be slow; 120 s gives plenty of headroom
        ) as client:

            # ── 1. Create a conversation if none supplied ─────────────────────
            if not conversation_id:
                resp = await client.post("/copilot/conversations", json={})
                resp.raise_for_status()
                conversation_id = resp.json()["id"]
                logger.debug("Created Copilot conversation %s", conversation_id)

            # ── 2. Build the chat request body ────────────────────────────────
            body: dict = {
                "message": {"text": question},
                "locationHint": {"timeZone": timezone},
            }

            contextual: dict = {}
            if file_uris:
                contextual["files"] = [{"uri": uri} for uri in file_uris]

            # web_search is a per-turn toggle; only send when explicitly disabled
            if not web_search:
                contextual["webContext"] = {"isWebEnabled": False}

            if contextual:
                body["contextualResources"] = contextual

            if additional_context:
                body["additionalContext"] = [{"text": t} for t in additional_context]

            # ── 3. Send message ───────────────────────────────────────────────
            resp = await client.post(
                f"/copilot/conversations/{conversation_id}/chat",
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()

        # ── 4. Extract the assistant reply (last message with role=assistant) ─
        messages: list[dict] = data.get("messages", [])
        assistant_msg = next(
            (m for m in reversed(messages) if m.get("role") == "assistant"),
            messages[-1] if messages else {},
        )

        raw_attrs = assistant_msg.get("attributions") or []

        attributions = [
            Attribution(
                title=a.get("providerDisplayName") or "",
                url=a.get("seeMoreWebUrl") or None,
            )
            for a in raw_attrs
            if a.get("attributionSource") == "grounding"
            and (a.get("providerDisplayName") or a.get("seeMoreWebUrl"))
        ]

        return CopilotChatResponse(
            conversation_id=data["id"],
            answer=assistant_msg.get("text", ""),
            attributions=attributions,
            turn_count=data.get("turnCount", 0),
        )
