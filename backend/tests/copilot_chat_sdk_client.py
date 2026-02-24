"""
Microsoft 365 Copilot Chat API — Python Example
=================================================
Calls the Graph beta Copilot Chat API directly, bypassing the Work IQ MCP server.
This is the same underlying API that the Work IQ MCP wraps.

Prerequisites:
  1. pip install msal httpx
  2. An Entra ID app registration with these DELEGATED permissions:
     - Sites.Read.All
     - Mail.Read
     - People.Read.All
     - OnlineMeetingTranscript.Read.All
     - Chat.Read
     - ChannelMessage.Read.All
     - ExternalItem.Read.All
  3. A Microsoft 365 Copilot license on the authenticating user
  4. Admin consent granted for the above permissions

API Docs:
  https://learn.microsoft.com/en-us/microsoft-365-copilot/extensibility/api/ai-services/chat/overview
"""

import asyncio
import os
import json
import webbrowser
from dataclasses import dataclass

import httpx
import msal
from dotenv import load_dotenv

load_dotenv()

# ─── Configuration ──────────────────────────────────────────────────────────────

TENANT_ID = os.environ["TENANT_ID"]
CLIENT_ID = os.environ["CLIENT_ID"]

GRAPH_BASE = "https://graph.microsoft.com/beta"

# All required delegated scopes for the Chat API
SCOPES = [
    "Sites.Read.All",
    "Mail.Read",
    "People.Read.All",
    "OnlineMeetingTranscript.Read.All",
    "Chat.Read",
    "ChannelMessage.Read.All",
    "ExternalItem.Read.All",
]


# ─── Authentication ─────────────────────────────────────────────────────────────

def get_access_token() -> str:
    """
    Acquire a delegated access token via MSAL device code flow.
    (Works on headless machines; swap for interactive flow if you prefer.)
    """
    app = msal.PublicClientApplication(
        client_id=CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{TENANT_ID}",
    )

    # Try the token cache first
    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])
        if result and "access_token" in result:
            print("✓ Using cached token")
            return result["access_token"]

    # Fall back to device code flow
    flow = app.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        raise RuntimeError(f"Device flow failed: {json.dumps(flow, indent=2)}")

    print(f"\n🔐 To sign in, visit: {flow['verification_uri']}")
    print(f"   Enter code: {flow['user_code']}\n")

    # Optionally open browser automatically
    webbrowser.open(flow["verification_uri"])

    result = app.acquire_token_by_device_flow(flow)
    if "access_token" not in result:
        raise RuntimeError(f"Auth failed: {result.get('error_description', result)}")

    print(f"✓ Authenticated as {result.get('id_token_claims', {}).get('preferred_username', 'unknown')}")
    return result["access_token"]


# ─── Copilot Chat API Client ────────────────────────────────────────────────────

@dataclass
class CopilotResponse:
    conversation_id: str
    answer_text: str
    attributions: list
    turn_count: int
    raw: dict


class CopilotChatClient:
    """Thin async client for the M365 Copilot Chat API (beta)."""

    def __init__(self, access_token: str, timezone: str = "America/New_York"):
        self.timezone = timezone
        self.http = httpx.AsyncClient(
            base_url=GRAPH_BASE,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            timeout=60.0,  # Copilot can take a while to respond
        )

    async def create_conversation(self) -> str:
        """Create a new Copilot conversation. Returns the conversation ID."""
        resp = await self.http.post("/copilot/conversations", json={})
        resp.raise_for_status()
        data = resp.json()
        return data["id"]

    async def ask(
        self,
        conversation_id: str,
        question: str,
        *,
        file_uris: list[str] | None = None,
        additional_context: list[str] | None = None,
        web_search: bool = True,
    ) -> CopilotResponse:
        """
        Send a message in an existing conversation.
        Returns the Copilot response with answer text and attributions.
        """
        body: dict = {
            "message": {"text": question},
            "locationHint": {"timeZone": self.timezone},
        }

        # Attach SharePoint/OneDrive files as context
        if file_uris:
            body["contextualResources"] = {
                "files": [{"uri": uri} for uri in file_uris]
            }

        # Toggle web search grounding off if requested
        if not web_search:
            body.setdefault("contextualResources", {})
            body["contextualResources"]["webContext"] = {"isWebEnabled": False}

        # Attach additional grounding context
        if additional_context:
            body["additionalContext"] = [{"text": t} for t in additional_context]

        resp = await self.http.post(
            f"/copilot/conversations/{conversation_id}/chat",
            json=body,
        )
        resp.raise_for_status()
        data = resp.json()

        # Extract the assistant's reply (last message in the messages array)
        messages = data.get("messages", [])
        assistant_msg = messages[-1] if messages else {}

        return CopilotResponse(
            conversation_id=data["id"],
            answer_text=assistant_msg.get("text", ""),
            attributions=assistant_msg.get("attributions", []),
            turn_count=data.get("turnCount", 0),
            raw=data,
        )

    async def close(self):
        await self.http.aclose()


# ─── Example Usage ───────────────────────────────────────────────────────────────

async def main():
    # 1. Authenticate
    token = get_access_token()

    # 2. Create client
    client = CopilotChatClient(token, timezone="America/New_York")

    try:
        # 3. Start a conversation
        conv_id = await client.create_conversation()
        print(f"\n📝 Conversation: {conv_id}\n")

        # 4. Ask questions (multi-turn)
        questions = [
            "What meetings do I have tomorrow?",
            "Summarize the most recent emails from my manager.",
            "What documents did I work on last week?",
        ]

        for q in questions:
            print(f"❓ {q}")
            response = await client.ask(conv_id, q)
            print(f"💬 {response.answer_text[:500]}")
            if response.attributions:
                print(f"   📎 {len(response.attributions)} source(s) cited")
            print(f"   (turn {response.turn_count})\n")

        # 5. Example: ask with a SharePoint file as context
        # response = await client.ask(
        #     conv_id,
        #     "Summarize this document for me.",
        #     file_uris=["https://contoso.sharepoint.com/sites/Eng/Shared Documents/Q4-Plan.docx"],
        # )

        # 6. Example: enterprise-only search (no web grounding)
        # response = await client.ask(
        #     conv_id,
        #     "What is our company's PTO policy?",
        #     web_search=False,
        # )

    finally:
        await client.close()


# ─── Agent Integration Pattern ──────────────────────────────────────────────────

async def agent_tool_example():
    """
    Shows how you'd wire this into a custom agent loop (e.g., with Claude API).
    The Copilot Chat API becomes one of your agent's tools.
    """
    token = get_access_token()
    client = CopilotChatClient(token)
    conv_id = await client.create_conversation()

    async def copilot_tool(question: str) -> str:
        """Tool function your agent can call."""
        response = await client.ask(conv_id, question)
        return response.answer_text

    # ─── Your agent loop ───
    # In practice, you'd use the Anthropic SDK and define this as a tool:
    #
    #   tools = [{
    #       "name": "query_m365",
    #       "description": "Query Microsoft 365 data — emails, meetings, documents, Teams messages",
    #       "input_schema": {
    #           "type": "object",
    #           "properties": {
    #               "question": {
    #                   "type": "string",
    #                   "description": "Natural language question about the user's M365 data"
    #               }
    #           },
    #           "required": ["question"]
    #       }
    #   }]
    #
    #   When Claude calls this tool, you'd do:
    #   answer = await copilot_tool(tool_input["question"])
    #   ... then feed the answer back to Claude as a tool_result.

    # Quick demo
    answer = await copilot_tool("What's on my calendar this week?")
    print(answer)

    await client.close()


if __name__ == "__main__":
    asyncio.run(main())