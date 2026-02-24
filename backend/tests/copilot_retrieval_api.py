"""
Microsoft 365 Copilot Retrieval API — Python Example
======================================================
Retrieves permission-trimmed text chunks from SharePoint, OneDrive, and
Copilot connectors using Microsoft's semantic index. Returns raw extracts
with relevance scores — NO LLM reasoning on Microsoft's side.

This is the "clean RAG" pattern:
  - Microsoft's semantic index handles retrieval (vector search, permission trimming)
  - YOUR agent handles generation (reasoning over the raw chunks)

Compared to the other approaches:
  - Copilot Chat API:  Microsoft retrieves + Microsoft reasons → synthesized answer
  - Retrieval API:     Microsoft retrieves → raw chunks → YOUR agent reasons
  - Graph SDK direct:  YOUR code retrieves (explicit queries) → YOUR agent reasons

Prerequisites:
  pip install msal httpx

App Registration (Entra ID):
  1. Same app registration setup as before (public client, device code flow)
  2. Add these DELEGATED Microsoft Graph permissions:
     - Files.Read.All       (required for SharePoint/OneDrive content)
     - Sites.Read.All       (required for SharePoint/OneDrive content)
     - ExternalItem.Read.All (optional — for Copilot connectors / external data)
  3. Grant admin consent

Licensing:
  - Users WITH a Microsoft 365 Copilot license: included at no extra cost
  - Users WITHOUT a Copilot license: available via pay-as-you-go consumption (preview)

API Docs:
  https://learn.microsoft.com/en-us/microsoft-365-copilot/extensibility/api/ai-services/retrieval/overview
  https://learn.microsoft.com/en-us/microsoft-365-copilot/extensibility/api/ai-services/retrieval/copilotroot-retrieval
"""

import asyncio
import json
import os
import webbrowser
from dataclasses import dataclass, field

import httpx
import msal
from dotenv import load_dotenv

load_dotenv()

# ─── Configuration ──────────────────────────────────────────────────────────────

TENANT_ID = os.environ["TENANT_ID"]
CLIENT_ID = os.environ["CLIENT_ID"]

# Lighter permission set than the Chat API — only file/site access needed
SCOPES = [
    "Files.Read.All",
    "Sites.Read.All",
    "ExternalItem.Read.All",  # Only needed if querying Copilot connectors
]

GRAPH_BASE = "https://graph.microsoft.com/beta"
# Also available on v1.0:
# GRAPH_BASE = "https://graph.microsoft.com/v1.0"


# ─── Authentication ─────────────────────────────────────────────────────────────

def get_access_token() -> str:
    """Acquire a delegated access token via MSAL device code flow."""
    app = msal.PublicClientApplication(
        client_id=CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{TENANT_ID}",
    )

    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])
        if result and "access_token" in result:
            print("✓ Using cached token")
            return result["access_token"]

    flow = app.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        raise RuntimeError(f"Device flow failed: {json.dumps(flow, indent=2)}")

    print(f"\n🔐 To sign in, visit: {flow['verification_uri']}")
    print(f"   Enter code: {flow['user_code']}\n")
    webbrowser.open(flow["verification_uri"])

    result = app.acquire_token_by_device_flow(flow)
    if "access_token" not in result:
        raise RuntimeError(f"Auth failed: {result.get('error_description', result)}")

    print(f"✓ Authenticated as {result.get('id_token_claims', {}).get('preferred_username', 'unknown')}")
    return result["access_token"]


# ─── Data Models ─────────────────────────────────────────────────────────────────

@dataclass
class TextExtract:
    text: str
    relevance_score: float


@dataclass
class RetrievalHit:
    web_url: str
    resource_type: str
    extracts: list[TextExtract]
    title: str | None = None
    author: str | None = None
    sensitivity_label: str | None = None


@dataclass
class RetrievalResponse:
    hits: list[RetrievalHit]
    raw: dict = field(default_factory=dict)

    def to_context_string(self, max_chunks: int | None = None) -> str:
        """
        Format retrieval hits as a context string suitable for injecting
        into an LLM prompt. This is how you'd use the results in a RAG pipeline.
        """
        lines = []
        chunk_count = 0
        for hit in self.hits:
            for extract in hit.extracts:
                if max_chunks and chunk_count >= max_chunks:
                    break
                source = hit.title or hit.web_url
                lines.append(
                    f"[Source: {source} | Relevance: {extract.relevance_score:.2f}]\n"
                    f"{extract.text}\n"
                )
                chunk_count += 1
        return "\n".join(lines)


# ─── Retrieval API Client ───────────────────────────────────────────────────────

class RetrievalClient:
    """Client for the M365 Copilot Retrieval API."""

    def __init__(self, access_token: str):
        self.http = httpx.AsyncClient(
            base_url=GRAPH_BASE,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    async def retrieve(
        self,
        query: str,
        data_source: str = "sharePoint",
        *,
        max_results: int = 10,
        filter_expression: str | None = None,
        metadata_fields: list[str] | None = None,
        connector_ids: list[str] | None = None,
    ) -> RetrievalResponse:
        """
        Retrieve relevant text chunks from Microsoft's semantic index.

        Args:
            query: Natural language query (max 1500 chars)
            data_source: "sharePoint", "oneDriveBusiness", or "externalItem"
            max_results: Number of results (1-25, default 10)
            filter_expression: KQL filter to scope results (e.g., by site, author, date)
            metadata_fields: Metadata to return (e.g., ["title", "author"])
            connector_ids: Specific Copilot connector IDs (only for externalItem)
        """
        body: dict = {
            "queryString": query,
            "dataSource": data_source,
            "maximumNumberOfResults": str(max_results),
        }

        if metadata_fields:
            body["resourceMetadata"] = metadata_fields

        if filter_expression:
            body["filterExpression"] = filter_expression

        if connector_ids and data_source == "externalItem":
            body["dataSourceConfiguration"] = {
                "externalItem": {
                    "connections": [{"connectionId": cid} for cid in connector_ids]
                }
            }

        resp = await self.http.post("/copilot/retrieval", json=body)
        resp.raise_for_status()
        data = resp.json()

        hits = []
        for hit in data.get("retrievalHits", []):
            metadata = hit.get("resourceMetadata", {})
            label_info = hit.get("sensitivityLabel", {})

            hits.append(RetrievalHit(
                web_url=hit.get("webUrl", ""),
                resource_type=hit.get("resourceType", ""),
                extracts=[
                    TextExtract(
                        text=e.get("text", ""),
                        relevance_score=e.get("relevanceScore", 0.0),
                    )
                    for e in hit.get("extracts", [])
                ],
                title=metadata.get("title"),
                author=metadata.get("author"),
                sensitivity_label=label_info.get("displayName"),
            ))

        return RetrievalResponse(hits=hits, raw=data)

    async def retrieve_from_sharepoint(
        self,
        query: str,
        *,
        site_urls: list[str] | None = None,
        author: str | None = None,
        file_types: list[str] | None = None,
        max_results: int = 10,
    ) -> RetrievalResponse:
        """
        Convenience method for SharePoint retrieval with common filters.
        Builds KQL filter expressions from friendly parameters.
        """
        filters = []
        if site_urls:
            path_filters = " OR ".join(f'path:"{url}"' for url in site_urls)
            filters.append(f"({path_filters})")
        if author:
            filters.append(f'Author:"{author}"')
        if file_types:
            type_filters = " OR ".join(f'FileExtension:"{ft}"' for ft in file_types)
            filters.append(f"({type_filters})")

        filter_expr = " AND ".join(filters) if filters else None

        return await self.retrieve(
            query,
            data_source="sharePoint",
            max_results=max_results,
            filter_expression=filter_expr,
            metadata_fields=["title", "author"],
        )

    async def retrieve_from_onedrive(
        self,
        query: str,
        *,
        max_results: int = 10,
    ) -> RetrievalResponse:
        """Convenience method for OneDrive retrieval."""
        return await self.retrieve(
            query,
            data_source="oneDriveBusiness",
            max_results=max_results,
            metadata_fields=["title", "author"],
        )

    async def retrieve_from_connectors(
        self,
        query: str,
        *,
        connector_ids: list[str] | None = None,
        max_results: int = 10,
    ) -> RetrievalResponse:
        """Convenience method for Copilot connector retrieval (ServiceNow, Jira, etc.)."""
        return await self.retrieve(
            query,
            data_source="externalItem",
            max_results=max_results,
            connector_ids=connector_ids,
            metadata_fields=["title", "author"],
        )

    async def batch_retrieve(
        self,
        queries: list[dict],
    ) -> list[RetrievalResponse]:
        """
        Batch multiple retrieval requests in a single API call (up to 20).
        Each query dict should have: queryString, dataSource, and optionally other params.
        """
        requests = []
        for i, q in enumerate(queries):
            requests.append({
                "id": str(i + 1),
                "method": "POST",
                "url": "/copilot/retrieval",
                "body": q,
                "headers": {"Content-Type": "application/json"},
            })

        resp = await self.http.post(
            f"{GRAPH_BASE}/$batch",
            json={"requests": requests},
        )
        resp.raise_for_status()
        data = resp.json()

        results = []
        for response in sorted(data.get("responses", []), key=lambda r: r["id"]):
            body = response.get("body", {})
            hits = []
            for hit in body.get("retrievalHits", []):
                metadata = hit.get("resourceMetadata", {})
                hits.append(RetrievalHit(
                    web_url=hit.get("webUrl", ""),
                    resource_type=hit.get("resourceType", ""),
                    extracts=[
                        TextExtract(
                            text=e.get("text", ""),
                            relevance_score=e.get("relevanceScore", 0.0),
                        )
                        for e in hit.get("extracts", [])
                    ],
                    title=metadata.get("title"),
                    author=metadata.get("author"),
                ))
            results.append(RetrievalResponse(hits=hits, raw=body))

        return results

    async def close(self):
        await self.http.aclose()


# ─── Main Demo ───────────────────────────────────────────────────────────────────

async def main():
    token = get_access_token()
    client = RetrievalClient(token)

    try:
        # 1. Basic SharePoint retrieval
        print("🔍 Retrieving from SharePoint: 'Q4 planning documents'\n")
        result = await client.retrieve_from_sharepoint(
            "Q4 planning documents",
            max_results=5,
        )
        for hit in result.hits:
            print(f"  📄 {hit.title or hit.web_url}")
            if hit.author:
                print(f"     Author: {hit.author}")
            if hit.sensitivity_label:
                print(f"     Label: {hit.sensitivity_label}")
            for extract in hit.extracts:
                print(f"     [{extract.relevance_score:.2f}] {extract.text[:120]}...")
            print()

        # 2. Filtered retrieval — specific site, only PDFs
        print("🔍 Filtered retrieval: PDFs about 'budget' from HR site\n")
        result = await client.retrieve_from_sharepoint(
            "annual budget allocation",
            site_urls=["https://contoso.sharepoint.com/sites/HR/"],
            file_types=["pdf"],
            max_results=3,
        )
        for hit in result.hits:
            print(f"  📄 {hit.title or hit.web_url}")
            for extract in hit.extracts:
                print(f"     [{extract.relevance_score:.2f}] {extract.text[:120]}...")
            print()

        # 3. OneDrive retrieval
        print("🔍 Retrieving from OneDrive: 'project status updates'\n")
        result = await client.retrieve_from_onedrive(
            "project status updates",
            max_results=5,
        )
        for hit in result.hits:
            print(f"  📄 {hit.title or hit.web_url}")
            for extract in hit.extracts:
                print(f"     [{extract.relevance_score:.2f}] {extract.text[:120]}...")
            print()

        # 4. Show RAG context formatting
        print("=" * 60)
        print("📋 RAG Context String (ready to inject into LLM prompt):\n")
        print(result.to_context_string(max_chunks=5))

    finally:
        await client.close()


# ─── Agent Integration Pattern ──────────────────────────────────────────────────

async def agent_rag_example():
    """
    The Retrieval API is purpose-built for RAG. Here's how you'd wire it
    into a Claude-based agent as a grounding tool.

    Key difference from Copilot Chat API:
      - Chat API: 1 call → Microsoft's LLM reasons → you get a finished answer
      - Retrieval API: 1 call → you get raw chunks → YOUR LLM reasons over them

    This means:
      - You control the system prompt and reasoning
      - You can combine M365 chunks with other data sources
      - You can use any LLM (Claude, GPT, Llama, etc.)
      - No "double inference" — only one LLM in the loop
    """
    token = get_access_token()
    client = RetrievalClient(token)

    # Step 1: User asks a question
    user_question = "What is our company's remote work policy?"

    # Step 2: Retrieve relevant chunks from M365
    result = await client.retrieve_from_sharepoint(
        user_question,
        max_results=10,
    )
    context = result.to_context_string(max_chunks=8)

    # Step 3: Build a grounded prompt for your LLM
    system_prompt = """You are a helpful enterprise assistant. Answer the user's 
question based ONLY on the provided context from company documents. 
Cite your sources. If the context doesn't contain enough information, say so."""

    grounded_prompt = f"""Context from company documents:
---
{context}
---

User question: {user_question}

Please answer based on the context above."""

    print("📋 Grounded prompt ready for your LLM:\n")
    print(grounded_prompt)

    # Step 4: Send to your LLM (pseudocode with Anthropic SDK)
    #
    # import anthropic
    # anthropic_client = anthropic.Anthropic()
    #
    # response = anthropic_client.messages.create(
    #     model="claude-sonnet-4-20250514",
    #     max_tokens=2048,
    #     system=system_prompt,
    #     messages=[{"role": "user", "content": grounded_prompt}],
    # )
    # print(response.content[0].text)

    # As a tool definition for an agentic loop:
    tools = [
        {
            "name": "search_company_documents",
            "description": (
                "Search company SharePoint and OneDrive for documents relevant to a query. "
                "Returns text extracts with relevance scores and source links. "
                "Use this to ground answers in company knowledge."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language search query (max 1500 chars)",
                    },
                    "source": {
                        "type": "string",
                        "enum": ["sharePoint", "oneDriveBusiness", "externalItem"],
                        "description": "Which data source to search",
                        "default": "sharePoint",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Number of documents to retrieve (1-25)",
                        "default": 10,
                    },
                    "site_filter": {
                        "type": "string",
                        "description": "Optional SharePoint site URL to scope the search",
                    },
                },
                "required": ["query"],
            },
        },
    ]

    # Tool dispatcher
    async def dispatch_tool(tool_name: str, tool_input: dict) -> str:
        if tool_name == "search_company_documents":
            filter_expr = None
            if tool_input.get("site_filter"):
                filter_expr = f'path:"{tool_input["site_filter"]}"'

            r = await client.retrieve(
                query=tool_input["query"],
                data_source=tool_input.get("source", "sharePoint"),
                max_results=tool_input.get("max_results", 10),
                filter_expression=filter_expr,
                metadata_fields=["title", "author"],
            )
            return r.to_context_string()
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    # Demo
    result_str = await dispatch_tool(
        "search_company_documents",
        {"query": "remote work policy", "source": "sharePoint", "max_results": 5},
    )
    print("\n🔧 Tool result:\n", result_str)

    await client.close()


if __name__ == "__main__":
    asyncio.run(main())