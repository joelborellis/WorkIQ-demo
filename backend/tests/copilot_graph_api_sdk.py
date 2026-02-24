"""
Microsoft Graph SDK — Direct M365 Data Access (Python)
=======================================================
Pulls raw emails, calendar events, Teams chats, and OneDrive files
directly via the Graph SDK. NO Copilot intelligence layer — your own
agent (Claude, GPT, etc.) reasons over the raw data.

This is architecturally different from the Copilot Chat API:
  - Copilot Chat API:  question → Microsoft's LLM → pre-digested answer
  - This script:       question → raw M365 data → YOUR agent reasons over it

Prerequisites:
  pip install msgraph-sdk azure-identity

App Registration (Entra ID):
  Same steps as the Copilot Chat API setup, but with different permissions.
  1. Create a new app registration (or reuse your existing one)
  2. Set "Allow public client flows" = Yes (for device code flow)
  3. Add these DELEGATED Microsoft Graph permissions:
     - User.Read            (user profile)
     - Mail.Read            (emails)
     - Calendars.Read       (calendar events)
     - Chat.Read            (Teams 1:1 and group chats)
     - ChannelMessage.Read.All (Teams channel messages)
     - Files.Read.All       (OneDrive / SharePoint files)
     - People.Read.All      (people / org chart)
     - Mail.Send             (send emails)
  4. Grant admin consent

Docs:
  https://learn.microsoft.com/en-us/graph/sdks/create-client?tabs=python
  https://learn.microsoft.com/en-us/graph/api/overview
"""

import asyncio
import json
import os
from datetime import datetime, timedelta, timezone

from azure.identity import DeviceCodeCredential
from msgraph import GraphServiceClient
from msgraph.generated.users.item.messages.messages_request_builder import (
    MessagesRequestBuilder,
)
from msgraph.generated.users.item.calendar_view.calendar_view_request_builder import (
    CalendarViewRequestBuilder,
)

from dotenv import load_dotenv

load_dotenv()

# ─── Configuration ──────────────────────────────────────────────────────────────

TENANT_ID = os.environ["TENANT_ID"]
CLIENT_ID = os.environ["CLIENT_ID"]

SCOPES = [
    "User.Read",
    "Mail.Read",
    "Mail.Send",
    "Calendars.Read",
    "Chat.Read",
    "ChannelMessage.Read.All",
    "Files.Read.All",
    "People.Read.All",
]


# ─── Graph Client Setup ─────────────────────────────────────────────────────────

def create_graph_client() -> GraphServiceClient:
    """Create an authenticated Graph client using device code flow."""
    credential = DeviceCodeCredential(
        tenant_id=TENANT_ID,
        client_id=CLIENT_ID,
    )
    client = GraphServiceClient(credential, SCOPES)
    print("✓ Graph client created (will prompt for login on first API call)\n")
    return client


# ─── Data Fetchers ───────────────────────────────────────────────────────────────

async def get_my_profile(client: GraphServiceClient) -> dict:
    """Get the authenticated user's profile."""
    user = await client.me.get()
    return {
        "display_name": user.display_name,
        "email": user.mail or user.user_principal_name,
        "job_title": user.job_title,
        "department": user.department,
    }


async def get_recent_emails(
    client: GraphServiceClient,
    count: int = 10,
    from_filter: str | None = None,
) -> list[dict]:
    """
    Get recent emails from the user's inbox.
    Optionally filter by sender.
    """
    query_params = MessagesRequestBuilder.MessagesRequestBuilderGetQueryParameters(
        select=["subject", "from", "receivedDateTime", "bodyPreview", "importance"],
        orderby=["receivedDateTime DESC"],
        top=count,
        filter=f"contains(from/emailAddress/address, '{from_filter}')" if from_filter else None,
    )
    config = MessagesRequestBuilder.MessagesRequestBuilderGetRequestConfiguration(
        query_parameters=query_params,
    )

    messages = await client.me.messages.get(request_configuration=config)

    results = []
    for msg in messages.value or []:
        results.append({
            "subject": msg.subject,
            "from": msg.from_.email_address.address if msg.from_ else "unknown",
            "from_name": msg.from_.email_address.name if msg.from_ else "unknown",
            "received": msg.received_date_time.isoformat() if msg.received_date_time else None,
            "preview": msg.body_preview[:200] if msg.body_preview else "",
            "importance": str(msg.importance) if msg.importance else "normal",
        })
    return results


async def get_upcoming_events(
    client: GraphServiceClient,
    days_ahead: int = 7,
) -> list[dict]:
    """Get calendar events for the next N days."""
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=days_ahead)

    query_params = CalendarViewRequestBuilder.CalendarViewRequestBuilderGetQueryParameters(
        start_date_time=now.strftime("%Y-%m-%dT%H:%M:%S.0000000"),
        end_date_time=end.strftime("%Y-%m-%dT%H:%M:%S.0000000"),
        select=["subject", "start", "end", "organizer", "location", "attendees"],
        orderby=["start/dateTime"],
        top=25,
    )
    config = CalendarViewRequestBuilder.CalendarViewRequestBuilderGetRequestConfiguration(
        query_parameters=query_params,
    )

    events = await client.me.calendar_view.get(request_configuration=config)

    results = []
    for evt in events.value or []:
        results.append({
            "subject": evt.subject,
            "start": evt.start.date_time if evt.start else None,
            "end": evt.end.date_time if evt.end else None,
            "timezone": evt.start.time_zone if evt.start else None,
            "organizer": evt.organizer.email_address.name if evt.organizer else None,
            "location": evt.location.display_name if evt.location else None,
            "attendees": [
                a.email_address.name
                for a in (evt.attendees or [])
                if a.email_address
            ],
        })
    return results


async def get_recent_chats(
    client: GraphServiceClient,
    count: int = 10,
) -> list[dict]:
    """Get the user's most recent Teams chats (metadata, not messages)."""
    chats = await client.me.chats.get()

    results = []
    for chat in (chats.value or [])[:count]:
        results.append({
            "id": chat.id,
            "topic": chat.topic or "(no topic)",
            "chat_type": str(chat.chat_type) if chat.chat_type else None,
            "last_updated": chat.last_updated_date_time.isoformat() if chat.last_updated_date_time else None,
        })
    return results


async def get_chat_messages(
    client: GraphServiceClient,
    chat_id: str,
    count: int = 10,
) -> list[dict]:
    """Get recent messages from a specific Teams chat."""
    messages = await client.me.chats.by_chat_id(chat_id).messages.get()

    results = []
    for msg in (messages.value or [])[:count]:
        results.append({
            "from": msg.from_.user.display_name if msg.from_ and msg.from_.user else "system",
            "content": msg.body.content[:300] if msg.body else "",
            "content_type": str(msg.body.content_type) if msg.body else None,
            "created": msg.created_date_time.isoformat() if msg.created_date_time else None,
        })
    return results


async def get_recent_files(
    client: GraphServiceClient,
    count: int = 10,
) -> list[dict]:
    """Get recently modified files from the user's OneDrive."""
    # Get the user's drive ID first, then call /drives/{id}/recent
    drive = await client.me.drive.get()
    items = await client.drives.by_drive_id(drive.id).recent.get()

    results = []
    for item in (items.value or [])[:count]:
        results.append({
            "name": item.name,
            "web_url": item.web_url,
            "size_bytes": item.size,
            "last_modified": item.last_modified_date_time.isoformat() if item.last_modified_date_time else None,
            "modified_by": (
                item.last_modified_by.user.display_name
                if item.last_modified_by and item.last_modified_by.user
                else None
            ),
        })
    return results


async def search_files(
    client: GraphServiceClient,
    query: str,
) -> list[dict]:
    """Search across OneDrive and SharePoint files."""
    from msgraph.generated.search.query.query_post_request_body import (
        QueryPostRequestBody,
    )
    from msgraph.generated.models.search_request import SearchRequest
    from msgraph.generated.models.entity_type import EntityType

    search_request = SearchRequest(
        entity_types=[EntityType.DriveItem],
        query={"query_string": query},
        size=10,
    )
    body = QueryPostRequestBody(requests=[search_request])

    search_results = await client.search.query.post(body)

    results = []
    if search_results and search_results.value:
        for response in search_results.value:
            for hit_container in response.hits_containers or []:
                for hit in hit_container.hits or []:
                    resource = hit.resource
                    results.append({
                        "name": getattr(resource, "name", None) or hit.summary,
                        "web_url": getattr(resource, "web_url", None),
                        "summary": hit.summary,
                    })
    return results


async def get_people(
    client: GraphServiceClient,
    count: int = 10,
) -> list[dict]:
    """Get people relevant to the user (frequent collaborators)."""
    people = await client.me.people.get()

    results = []
    for person in (people.value or [])[:count]:
        results.append({
            "name": person.display_name,
            "job_title": person.job_title,
            "department": person.department,
            "email": (
                person.scored_email_addresses[0].address
                if person.scored_email_addresses
                else None
            ),
        })
    return results


async def send_email(
    client: GraphServiceClient,
    to_address: str,
    subject: str,
    body: str,
) -> None:
    """Send an email via Microsoft Graph."""
    from msgraph.generated.users.item.send_mail.send_mail_post_request_body import (
        SendMailPostRequestBody,
    )
    from msgraph.generated.models.message import Message
    from msgraph.generated.models.item_body import ItemBody
    from msgraph.generated.models.body_type import BodyType
    from msgraph.generated.models.recipient import Recipient
    from msgraph.generated.models.email_address import EmailAddress

    message = Message(
        subject=subject,
        body=ItemBody(content_type=BodyType.Text, content=body),
        to_recipients=[
            Recipient(email_address=EmailAddress(address=to_address)),
        ],
    )
    request_body = SendMailPostRequestBody(message=message, save_to_sent_items=True)
    await client.me.send_mail.post(request_body)


# ─── Main Demo ───────────────────────────────────────────────────────────────────

async def main():
    client = create_graph_client()

    # 1. Who am I?
    print("👤 Profile")
    profile = await get_my_profile(client)
    print(json.dumps(profile, indent=2))

    # 2. Recent emails
    print("\n📧 Recent Emails (last 5)")
    emails = await get_recent_emails(client, count=5)
    for e in emails:
        print(f"  • {e['from_name']}: {e['subject']}")
        print(f"    {e['preview'][:80]}...")

    # 3. Upcoming calendar
    print("\n📅 Upcoming Events (next 7 days)")
    events = await get_upcoming_events(client, days_ahead=7)
    for e in events:
        print(f"  • {e['start']} — {e['subject']} (organizer: {e['organizer']})")

    # 4. Recent Teams chats
    print("\n💬 Recent Teams Chats")
    chats = await get_recent_chats(client, count=5)
    for c in chats:
        print(f"  • [{c['chat_type']}] {c['topic']} (updated: {c['last_updated']})")

    # 5. Recent OneDrive files
    print("\n📁 Recent Files")
    files = await get_recent_files(client, count=5)
    for f in files:
        print(f"  • {f['name']} (modified: {f['last_modified']})")

    # 6. Relevant people
    print("\n👥 Relevant People")
    people = await get_people(client, count=5)
    for p in people:
        print(f"  • {p['name']} — {p['job_title']} ({p['email']})")

    # 7. Send an email
    print("\n✉️  Send an Email")
    to_addr = input("  To (email address): ").strip()
    subject = input("  Subject: ").strip()
    body = input("  Body: ").strip()

    if to_addr and subject:
        await send_email(client, to_addr, subject, body)
        print(f"  ✓ Email sent to {to_addr}")
    else:
        print("  ⚠ Skipped — email address and subject are required.")


# ─── Agent Integration Pattern ──────────────────────────────────────────────────

async def agent_tool_example():
    """
    Shows how you'd wire these as tools for a Claude-based agent.
    Each Graph data source becomes a separate tool, giving your agent
    fine-grained control over what data to fetch.

    Key difference from Copilot Chat API approach:
      - Copilot Chat API: 1 tool ("ask anything") → Microsoft's LLM decides what to search
      - Graph SDK direct:  N tools (emails, calendar, files, etc.) → YOUR agent decides
    """
    client = create_graph_client()

    # Define these as tool functions for the Anthropic SDK:
    tools = [
        {
            "name": "get_emails",
            "description": "Get the user's recent emails. Optionally filter by sender.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "count": {"type": "integer", "description": "Number of emails to fetch", "default": 10},
                    "from_filter": {"type": "string", "description": "Filter by sender email (partial match)"},
                },
            },
        },
        {
            "name": "get_calendar",
            "description": "Get upcoming calendar events for the next N days.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "days_ahead": {"type": "integer", "description": "Number of days to look ahead", "default": 7},
                },
            },
        },
        {
            "name": "get_teams_chats",
            "description": "Get recent Teams chat conversations and their messages.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "count": {"type": "integer", "default": 10},
                },
            },
        },
        {
            "name": "get_files",
            "description": "Get recently modified OneDrive/SharePoint files.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "count": {"type": "integer", "default": 10},
                },
            },
        },
        {
            "name": "search_files",
            "description": "Search across OneDrive and SharePoint for files matching a query.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                },
                "required": ["query"],
            },
        },
        {
            "name": "get_people",
            "description": "Get people the user frequently collaborates with.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "count": {"type": "integer", "default": 10},
                },
            },
        },
    ]

    # Tool dispatcher — map tool calls to Graph SDK functions
    async def dispatch_tool(tool_name: str, tool_input: dict) -> str:
        if tool_name == "get_emails":
            data = await get_recent_emails(
                client,
                count=tool_input.get("count", 10),
                from_filter=tool_input.get("from_filter"),
            )
        elif tool_name == "get_calendar":
            data = await get_upcoming_events(
                client,
                days_ahead=tool_input.get("days_ahead", 7),
            )
        elif tool_name == "get_teams_chats":
            data = await get_recent_chats(client, count=tool_input.get("count", 10))
        elif tool_name == "get_files":
            data = await get_recent_files(client, count=tool_input.get("count", 10))
        elif tool_name == "search_files":
            data = await search_files(client, query=tool_input["query"])
        elif tool_name == "get_people":
            data = await get_people(client, count=tool_input.get("count", 10))
        else:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})

        return json.dumps(data, indent=2, default=str)

    # ─── Example agent loop (pseudocode with Anthropic SDK) ───
    #
    # import anthropic
    # client = anthropic.Anthropic()
    #
    # messages = [{"role": "user", "content": "What meetings do I have this week?"}]
    #
    # while True:
    #     response = client.messages.create(
    #         model="claude-sonnet-4-20250514",
    #         max_tokens=4096,
    #         tools=tools,
    #         messages=messages,
    #     )
    #
    #     # Check if Claude wants to use a tool
    #     if response.stop_reason == "tool_use":
    #         for block in response.content:
    #             if block.type == "tool_use":
    #                 result = await dispatch_tool(block.name, block.input)
    #                 messages.append({"role": "assistant", "content": response.content})
    #                 messages.append({
    #                     "role": "user",
    #                     "content": [{
    #                         "type": "tool_result",
    #                         "tool_use_id": block.id,
    #                         "content": result,
    #                     }],
    #                 })
    #     else:
    #         # Claude gave a final text response
    #         print(response.content[0].text)
    #         break

    # Quick standalone demo
    print("📧 Fetching emails via dispatch...")
    result = await dispatch_tool("get_emails", {"count": 3})
    print(result)


if __name__ == "__main__":
    asyncio.run(main())