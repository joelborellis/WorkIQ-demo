from __future__ import annotations

from pydantic import BaseModel, Field


class CopilotChatRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=1,
        description="Natural language question about the user's Microsoft 365 data.",
    )
    conversation_id: str | None = Field(
        None,
        description=(
            "ID of an existing conversation to continue (multi-turn chat). "
            "Omit to start a new conversation."
        ),
    )
    file_uris: list[str] | None = Field(
        None,
        description="SharePoint or OneDrive file URIs to include as grounding context.",
    )
    additional_context: list[str] | None = Field(
        None,
        description="Extra text snippets to ground the answer.",
    )
    web_search: bool = Field(
        True,
        description="Toggle web search grounding. Note: this is a per-turn setting.",
    )
    timezone: str = Field(
        "UTC",
        description="IANA timezone identifier used as the locationHint (e.g. 'America/New_York').",
    )


class Attribution(BaseModel):
    title: str
    url: str | None = None


class CopilotChatResponse(BaseModel):
    conversation_id: str = Field(..., description="Use this in subsequent requests for multi-turn chat.")
    answer: str
    attributions: list[Attribution] = []
    turn_count: int
