"""
Copilot routes
--------------
  POST /api/v1/copilot_chat   – ask a question via the M365 Copilot Chat API
  POST /api/v1/retrieval_api  – retrieve raw chunks via the M365 Retrieval API
"""
from __future__ import annotations

import logging
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.dependencies import get_graph_token
from app.models.copilot import CopilotChatRequest, CopilotChatResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/copilot_chat",
    response_model=CopilotChatResponse,
    summary="Ask Microsoft 365 Copilot",
    description=(
        "Forwards a natural language question to the Microsoft 365 Copilot Chat API "
        "and returns an answer grounded in the authenticated user's enterprise data "
        "(emails, meetings, documents, Teams messages, etc.).\n\n"
        "Pass `conversation_id` from a previous response to continue a multi-turn "
        "conversation. Omit it to start a new one."
    ),
    responses={
        401: {"description": "Missing or invalid bearer token / OBO flow failed"},
        502: {"description": "Upstream Graph API error"},
    },
)
async def copilot_chat(
    body: CopilotChatRequest,
    request: Request,
    graph_token: Annotated[str, Depends(get_graph_token)],
) -> CopilotChatResponse:
    """
    Protected endpoint — requires a valid Entra ID bearer token with the
    ``api://<CLIENT_ID>/access_as_user`` scope.

    The backend performs the OBO flow automatically; the frontend only needs to
    send its own API-scoped token, not a Graph token directly.
    """
    copilot_service = request.app.state.copilot_service
    try:
        return await copilot_service.chat(
            access_token=graph_token,
            question=body.question,
            conversation_id=body.conversation_id,
            file_uris=body.file_uris,
            additional_context=body.additional_context,
            web_search=body.web_search,
            timezone=body.timezone,
        )
    except httpx.HTTPStatusError as exc:
        logger.error(
            "Graph API returned %s: %s",
            exc.response.status_code,
            exc.response.text[:500],
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Graph API error ({exc.response.status_code}): {exc.response.text}",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error in copilot_chat")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Copilot service error: {exc}",
        ) from exc


@router.post(
    "/graph_api",
    response_model=CopilotChatResponse,
    summary="Query Microsoft 365 via the Graph API directly",
    description=(
        "Fetches raw M365 data from multiple Graph endpoints in parallel "
        "(emails, calendar, Teams chats, OneDrive files, people, and a "
        "cross-M365 content search) and returns the results as structured "
        "Markdown.\n\n"
        "Unlike the Chat API route, **no LLM is involved** — this is a "
        "direct read of the user's M365 data, making it useful for comparing "
        "raw Graph data against Copilot's synthesised answer and the "
        "Retrieval API's semantic chunks."
    ),
    responses={
        401: {"description": "Missing or invalid session / token refresh failed"},
        502: {"description": "Upstream Graph API error"},
    },
)
async def graph_api(
    body: CopilotChatRequest,
    request: Request,
    graph_token: Annotated[str, Depends(get_graph_token)],
) -> CopilotChatResponse:
    """
    Protected endpoint — session cookie required (same auth flow as copilot_chat).

    Uses the question text as a search query for the Graph Search endpoint;
    all other endpoints (mail, calendar, files, etc.) return a fixed-size
    snapshot regardless of the question.
    """
    graph_service = request.app.state.graph_service
    try:
        return await graph_service.query(
            access_token=graph_token,
            question=body.question,
            timezone_name=body.timezone,
        )
    except httpx.HTTPStatusError as exc:
        logger.error(
            "Graph API returned %s: %s",
            exc.response.status_code,
            exc.response.text[:500],
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Graph API error ({exc.response.status_code}): {exc.response.text}",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error in graph_api")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Graph service error: {exc}",
        ) from exc


@router.post(
    "/retrieval_api",
    response_model=CopilotChatResponse,
    summary="Retrieve from Microsoft 365 via the Retrieval API",
    description=(
        "Queries Microsoft's semantic index (SharePoint and OneDrive by default) "
        "using the M365 Copilot Retrieval API and returns ranked text extracts "
        "formatted as Markdown.\n\n"
        "Unlike the Chat API route, Microsoft's LLM is **not** involved — this "
        "is a pure retrieval step that returns the raw grounding chunks, making "
        "it useful for comparing retrieval quality against a fully-synthesised "
        "Copilot answer side-by-side."
    ),
    responses={
        401: {"description": "Missing or invalid session / token refresh failed"},
        502: {"description": "Upstream Graph API error"},
    },
)
async def retrieval_api(
    body: CopilotChatRequest,
    request: Request,
    graph_token: Annotated[str, Depends(get_graph_token)],
) -> CopilotChatResponse:
    """
    Protected endpoint — session cookie required (same auth flow as copilot_chat).

    Accepts the same ``CopilotChatRequest`` body; only ``question`` and
    ``timezone`` are forwarded to the Retrieval API.  The response is a
    ``CopilotChatResponse`` with retrieved content as the ``answer`` field,
    so the frontend comparison panel works identically for both routes.
    """
    retrieval_service = request.app.state.retrieval_service
    try:
        return await retrieval_service.retrieve(
            access_token=graph_token,
            question=body.question,
            timezone=body.timezone,
        )
    except httpx.HTTPStatusError as exc:
        logger.error(
            "Graph API returned %s: %s",
            exc.response.status_code,
            exc.response.text[:500],
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Graph API error ({exc.response.status_code}): {exc.response.text}",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error in retrieval_api")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Retrieval service error: {exc}",
        ) from exc
