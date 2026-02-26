# Microsoft M365 API & MCP Integration Research
**Research Chat Transcript**  
*Date: February 25, 2026*  
*Topic: Code-first options for Microsoft M365 productivity APIs, MCP servers, and architectural tradeoffs*

---

## Table of Contents
1. [All Available APIs and MCP Servers](#1-all-available-apis-and-mcp-servers)
2. [Do the APIs Use the Semantic Index?](#2-do-the-apis-use-the-semantic-index)
3. [MCP Servers vs Graph API — Why Use One Over the Other?](#3-mcp-servers-vs-graph-api--why-use-one-over-the-other)

---

## 1. All Available APIs and MCP Servers

### Question
> This is an exploratory chat. I want to confirm all the various APIs and MCP servers that Microsoft has available to call and retrieve information or even create items in their ecosystem. I'm focusing on the user productivity solutions like email, SharePoint, OneDrive, Teams, Edge browser etc. I'm looking at code-first options.

### Answer

The Microsoft M365 integration landscape is layered — from lowest-level raw data access to highest-level AI abstraction.

---

### TIER 1 — Raw / Direct APIs (Maximum Control, No Black Box)

#### 1. Microsoft Graph API
The unified REST API for essentially all of M365. Single endpoint: `https://graph.microsoft.com`

**What it covers (read & write):**
- **Outlook Mail** — list, read, send, draft, move, delete messages; manage folders and rules
- **Outlook Calendar** — CRUD on events, free/busy lookup, meeting scheduling
- **Contacts** — CRUD on personal and shared contact books
- **OneDrive & SharePoint Files** — upload, download, move, copy, search across drives and document libraries
- **SharePoint Sites & Lists** — CRUD on sites, lists, list items, content types, columns
- **Teams** — create/update channels, send messages, manage membership, read chat history
- **Planner** — create plans, buckets, tasks; read assignments
- **User & Group Management** — Entra ID users, groups, directory objects
- **People & Insights** — trending, used, and shared signals per user
- **Search** — Microsoft Search across all M365 content (`/search/query`)
- **Subscriptions / Webhooks** — change notifications across mail, calendar, files, Teams

**Auth:** Entra ID (OAuth2/MSAL), delegated or application permissions  
**SDKs:** .NET, Python (`msgraph-sdk-python`), JS/TS, Java, Go, PHP  
**Key constraint:** Read-only for some resources in application mode; rate limits apply

---

#### 2. SharePoint REST API (`https://{tenant}.sharepoint.com/_api/`)
SharePoint-specific operations that Graph doesn't fully expose, particularly around:
- Fine-grained site/list administration (site columns, content types, features)
- Older-style SharePoint workflows
- Detailed permission management at item level
- CSOM (Client-Side Object Model) operations via REST
- Taxonomy/term store management

**When to use over Graph:** When you need deep SharePoint-specific control that Graph's abstraction layer loses.

---

#### 3. Exchange Web Services (EWS) *(Legacy but still functional)*
`https://outlook.office365.com/EWS/Exchange.asmx`

Microsoft is actively deprecating this in favour of Graph, but it still works for:
- Complex mailbox operations (public folders, archive mailboxes)
- Streaming notifications
- Some compliance and discovery scenarios not yet migrated to Graph

**Status:** Avoid for new builds. Migration deadline is being phased in.

---

#### 4. Teams Bot Framework / Activity Feed API
For building conversational bots that live inside Teams as first-class citizens — not just sending messages via Graph, but creating interactive, stateful agents that respond to proactive triggers.

---

### TIER 2 — AI-Layer APIs (Require M365 Copilot License)

These all live under `https://graph.microsoft.com/beta/copilot/` and are in Public Preview (2025):

| API | What it does |
|---|---|
| **Retrieval API** | Natural language query → permission-trimmed extracts from SharePoint + Copilot Connectors. Best clean RAG pattern without building a vector index |
| **Chat API** | Multi-turn Copilot conversation grounded in M365 content, callable from your own app. Currently in public preview |
| **Meeting Insights API** | AI-generated summaries, action items, decisions from Teams meeting transcripts |
| **Interactions Export API** | Export Copilot conversation history for audit, compliance, analytics |
| **Change Notifications API** | Webhooks on Copilot interaction changes |

**Licensing gate:** All require a Microsoft 365 Copilot license per user. Not available on standard E3/E5 alone.

---

### TIER 3 — MCP Servers (Agent-Oriented, Tool-Abstracted)

Microsoft's official MCP servers live under the **Agent 365** umbrella (`learn.microsoft.com/microsoft-agent-365`). These expose semantic, tool-shaped interfaces rather than raw CRUD:

| Server | Key Tools |
|---|---|
| **Outlook Mail MCP** | Create, update, delete messages; reply-all; semantic search |
| **Outlook Calendar MCP** | Create/list/update/delete events; accept/decline; conflict resolution |
| **SharePoint + OneDrive MCP** | Upload files; get metadata; search; manage document libraries |
| **SharePoint Lists MCP** | CRUD on list items specifically |
| **Microsoft Teams MCP** | Create/update chats and channels; add members; post messages |
| **Word MCP** | Read and manipulate Word documents |
| **M365 Admin Center MCP** | Tenant admin operations |
| **User Profile MCP** | Get manager, direct reports, search users |
| **M365 Copilot (Search) MCP** | Ground responses via Copilot, start/continue multi-turn conversations |
| **Dataverse + Dynamics 365 MCP** | CRUD + domain actions on business data |
| **MCP Server for Enterprise** | Converts natural language → Graph API calls (500+ pre-baked query patterns) |

**How to consume them:**
- From **Claude Desktop / VS Code** — via `mcpServers` config pointing to `sse` or `stdio` endpoints
- From **Copilot Studio** — native built-in catalog
- From **code** — via Agent 365 SDK (public preview), or any MCP client library

**Governance:** Managed via M365 Admin Center. DLP, MIP labels, and Sentinel/Defender observability built in.

---

### TIER 4 — Third-Party MCP Servers (Open Source, Graph-backed)

Two notable community/open-source options that are production-quality:

**`@softeria/ms-365-mcp-server`** (npm, GitHub)
- Covers: Mail, Calendar, Contacts, OneDrive, SharePoint, Teams, Shared Mailboxes, OneNote
- `--org-mode` flag enables full enterprise scope
- `--read-only` flag for safe exploration
- Supports device code flow and HTTP transport
- Direct Graph API under the hood — no Microsoft LLM intermediary

**`lokka`** (GitHub: merill/lokka)
- Lighter weight, similar Graph-backed approach

---

### TIER 5 — Orchestration & Extension Layers

These aren't raw APIs but are code-first:

| Approach | Description |
|---|---|
| **Microsoft Graph Connectors** | Ingest external data *into* M365 search index (Jira, Salesforce, ServiceNow, custom) so it's queryable via Graph Search and Retrieval API |
| **Power Automate (HTTP Action)** | Trigger Graph calls or custom APIs as part of automated flows — low-code but fully codeable |
| **Microsoft 365 Agents SDK** | The pro-code SDK (C#, JS, Python) for building enterprise-grade agents that publish to Teams, Copilot, web, and 15+ channels |
| **Teams SDK (McpPlugin)** | Convert any Teams bot/app into an MCP server itself, exposing tools to other agents |
| **Azure Logic Apps** | Deeper enterprise orchestration with M365 connectors at the workflow level |

---

### The Decision Framework

```
Need raw data / write ops?
└── Microsoft Graph API (primary choice)
    └── SharePoint REST API (deep SP-only ops)

Need AI reasoning over M365 data?
└── Copilot Retrieval API (clean RAG, no vector index)
└── Copilot Chat API (full multi-turn, black-box)
└── Meeting Insights API (Teams transcripts)

Building agents that "do" things?
└── Agent 365 MCP Servers (governed, enterprise)
└── @softeria/ms-365-mcp-server (open source, full Graph surface)

Need to bring external data into M365's index?
└── Graph Connectors (ingest into semantic index)

Need to expose your own logic as an MCP tool?
└── Teams SDK McpPlugin (publish from a Teams app)
└── Agent 365 custom server certification
```

---

## 2. Do the APIs Use the Semantic Index?

### Question
> Ok lets inspect the API layer APIs, do these all use the semantic layer/index when querying? Meaning they all use an LLM to query raw data and have the advantage of the semantic index layer to draw connections?

### Answer

No — definitely not all of them. They sit on a spectrum from pure raw data to full semantic+LLM reasoning. There are actually **four distinct layers** of intelligence at play, and different APIs plug into different ones.

---

### The Semantic Layer Spectrum

```
RAW DATA          LEXICAL INDEX       SEMANTIC INDEX        LLM REASONING
(structured        (keyword/full-      (vector embeddings,   (synthesis,
 objects)          text search)        intent, synonyms)     generation)
     │                  │                    │                    │
   Graph              Graph              Copilot              Copilot
   CRUD              Search API         Retrieval API         Chat API
   APIs              /search/query       /copilot/retrieval   /copilot/chat
```

---

### Layer 1 — Raw CRUD (No Index, No LLM)

**Graph API CRUD endpoints** (`/me/messages`, `/me/events`, `/drives/{id}/items`, `/sites/...`, etc.) and the **SharePoint REST API** are pure object stores. You're querying structured data models directly:

- `GET /me/messages?$filter=isRead eq false` → returns mail objects, filtered by field values
- `GET /sites/{id}/lists/{id}/items` → returns list item objects
- No ranking, no semantic understanding, no inference. It's SQL-style against structured M365 data.

**The semantic index plays zero role here.** You get back exactly what you asked for, shaped by OData filters you write yourself.

---

### Layer 2 — Lexical Index (Microsoft Search, partial semantic)

**Graph Search API** (`POST /search/query`) sits one step up. This queries the **Microsoft Search index**, which is a full-text/keyword index across M365 content. It supports:

- Full-text search across mail, files, Teams messages, SharePoint pages
- Some basic semantic proximity (word forms, stemming)
- KQL filters and relevance ranking

Critically, Microsoft Search uses keyword-based queries to return a list of files and links — it does not leverage a semantic index, use an LLM, ground in web content, or create generative responses.

The Graph Search API gives you better-than-nothing relevance ranking, but it is **not** the Copilot semantic/vector index. It won't understand synonyms, intent, or conceptual relationships the way Copilot does.

---

### Layer 3 — Full Semantic Index (No LLM, Returns Chunks)

**Copilot Retrieval API** (`POST /beta/copilot/retrieval`) is the first API that genuinely touches the Copilot semantic index — the hybrid lexical+vector index that powers M365 Copilot itself.

The API understands the user's context and intent and performs query transformations to yield the most relevant results, which is more difficult to achieve with lexical search or even basic RAG from alternate sources.

Key architectural point: **the Retrieval API does NOT invoke an LLM**. It returns permission-trimmed text chunks — the grounding context — for you to feed into your own LLM. You own the reasoning step. Microsoft handles the retrieval step. That's what makes it the cleanest RAG pattern in the ecosystem.

**Critical scope limitation:** The semantic index covers SharePoint, OneDrive, and Copilot Connectors — but notably **not** raw email, Teams chat messages, or Calendar events directly.

---

### Layer 4 — Full Semantic Index + LLM (Full Black Box)

**Copilot Chat API** (`POST /beta/copilot/chat`) and the **native M365 Copilot Chat app** both invoke the complete Copilot stack: semantic retrieval → query transformation → LLM synthesis → grounded response.

The internal flow: Copilot feeds its reasoning with the semantic index, gathers the tenant's context through Graph, and builds an enriched prompt for the LLM. The model generates a response, and then Copilot queries Graph/index again to verify, complete, and execute commands.

You don't see the chunks, you don't control the model, you just get a synthesized answer.

**Meeting Insights API** is similar — the LLM has already run over the transcript, and you receive the structured output (summaries, action items, decisions). The reasoning step already happened upstream.

---

### The Complete Matrix

| API | Raw Data | Lexical Index | Semantic Index | LLM Reasoning | You control LLM? |
|---|:---:|:---:|:---:|:---:|:---:|
| Graph CRUD endpoints | ✅ | ❌ | ❌ | ❌ | N/A |
| Graph Search API | ❌ | ✅ | ❌ | ❌ | N/A |
| Copilot Retrieval API | ❌ | ✅ | ✅ | ❌ | ✅ (you bring it) |
| Copilot Chat API | ❌ | ✅ | ✅ | ✅ | ❌ (Microsoft's) |
| Meeting Insights API | ❌ | ❌ | ❌ | ✅ (pre-run) | ❌ |
| Work IQ MCP | ❌ | ✅ | ✅ | ✅ | ❌ |

---

### The Architectural Implication

**There is no API that gives you:**
1. The full semantic index
2. Across all M365 surfaces (mail + calendar + Teams + files)
3. That returns raw chunks for your own LLM

The Retrieval API is the closest thing to a clean RAG primitive, but it's bounded to SharePoint/OneDrive/Connectors. Email and Teams chats are only accessible either as raw structured objects via Graph CRUD (no semantic layer), or as opaque LLM output via Copilot Chat (black box).

That gap — **no semantic retrieval primitive across the full M365 substrate** — is what forces every builder into either the black-box pattern or a hybrid architecture where you stitch Graph CRUD with your own embedding and indexing on top.

---

## 3. MCP Servers vs Graph API — Why Use One Over the Other?

### Question
> Ok so then distinguish between why I might use one of the MCPs that look like they have write/create access to Teams, Outlook, OneDrive etc. Versus using the Graph API which seems to also allow create on all these things.

### Answer

The capability overlap is real — both can create a Teams channel, send an email, upload a file. But they're designed for **fundamentally different callers** and **different execution contexts**.

---

### The Real Distinction: Who Is the Caller?

#### Graph API Direct — Deterministic Code is the Caller

When you write code that calls Graph directly, **you are the orchestrator**. Your code decides:
- Which endpoint to call
- What parameters to pass
- How to handle errors and retries
- How to chain multiple calls together
- How to interpret the response

```python
# You wrote this logic. The intent is hardcoded by you.
msg = {
    "message": {
        "subject": "Q3 Report",
        "body": {"contentType": "Text", "content": "Please review"},
        "toRecipients": [{"emailAddress": {"address": "jane@contoso.com"}}]
    }
}
graph_client.post("/me/sendMail", json=msg)
```

The code is **deterministic**. Given the same inputs it always does the same thing. The developer understood the intent, translated it into API calls, and hardcoded that translation. The Graph API doesn't know or care what problem you're solving — it just executes the HTTP operation.

**This is classic software engineering.** Nothing AI-specific about it.

---

#### MCP Server — An LLM Agent is the Caller

MCP servers exist because **LLMs are bad at calling raw REST APIs directly**. The problems they solve are:

**1. Parameter resolution at runtime**
When a user says "email the Q3 report to Jane", an LLM needs to:
- Figure out Jane's actual email address from her name
- Locate the Q3 report file and get its ID or content
- Understand that "email it" means `sendMail` with an attachment, not just `createMessage`
- Chain those lookups before making the write call

The MCP tool interface packages this into a **natural-language-friendly, self-describing tool** that the LLM can reason about. The tool description tells the model *when* to use it and *what* it accomplishes in human terms, not technical terms.

**2. Semantic intent → correct action mapping**
"Schedule a meeting with the product team about the roadmap for next Tuesday" requires the LLM to understand that "product team" means resolving group membership, "next Tuesday" means computing a date, and "about the roadmap" is a subject line. The MCP tool for calendar exposes a `create-event` tool with a well-described schema that the LLM can map natural language into — rather than constructing a raw JSON payload conforming to the Graph event resource type.

**3. Agentic chaining across tools**
MCP's real power is when an agent calls multiple tools in sequence based on reasoning, not predetermined code paths:

```
User: "Create a Teams channel for the new project, 
       invite the folks from last week's planning meeting, 
       and post the agenda doc from my OneDrive there"

Agent reasoning:
1. [meeting-insights-tool]  → find last week's planning meeting attendees
2. [teams-create-channel-tool] → create the channel  
3. [teams-add-members-tool] → add those attendees
4. [onedrive-search-tool]   → find the agenda doc
5. [teams-post-message-tool] → post a link/share
```

No developer pre-wired this workflow. The LLM reasoned through it dynamically. With raw Graph API, you'd have to have anticipated and hardcoded every possible permutation of this.

---

### The Governance Angle (Enterprise MCP Only)

The **Agent 365 MCP servers specifically** add a third layer of value that has nothing to do with the LLM:

| Concern | Graph API Direct | Agent 365 MCP |
|---|---|---|
| DLP policies enforced | Only if you build it | ✅ Built-in |
| MIP sensitivity labels respected | Only if you check | ✅ Automatic |
| Audit trail of agent actions | You build logging | ✅ Defender/Sentinel integrated |
| Admin can block a tool org-wide | Not possible | ✅ M365 Admin Center |
| Per-scope permission enforcement | You manage | ✅ Entra scopes enforced |

For an enterprise that has an LLM agent autonomously taking actions on behalf of users, the MCP governance layer means every tool invocation is logged, policy-checked, and controllable by IT — which you simply cannot get from direct Graph calls without building all of that yourself.

---

### The Decision Framework

```
Are you writing deterministic application logic?
└── Use Graph API directly.
    Predictable, fast, no overhead, full control.
    Examples: sync job, scheduled report, form submission handler.

Is an LLM dynamically deciding what actions to take?
└── Use MCP servers.
    The tool abstraction is designed for LLM reasoning.
    Examples: agentic assistant, natural language workflow,
              multi-step task from a single user prompt.
    
    └── Is it an enterprise deployment with governance needs?
        └── Agent 365 MCP (audit, DLP, admin control)
    
    └── Is it a personal/dev/research context?
        └── @softeria/ms-365-mcp-server or similar
            (full Graph surface, no governance overhead)
```

---

### The Architectural Summary for Thesis Framing

**Graph API + your own LLM** = you implement the orchestration, the intent-to-action mapping, and any semantic understanding yourself. The Graph API is purely the execution layer. The "intelligence" lives entirely in your agent code and your LLM.

**Agent 365 MCP servers + your LLM** = Microsoft has pre-packaged the Graph API operations into LLM-legible tools, with governance baked in. Your LLM still does the reasoning and orchestration, but you've offloaded the tool design and policy enforcement to Microsoft.

**Work IQ / Copilot Chat API** = Microsoft's LLM has already done the intent mapping, Graph traversal, and semantic reasoning for you. You get output, not raw materials.

The MCP layer is essentially Microsoft saying: *"we know you're going to put an LLM in front of Graph API anyway — here's a well-designed, governed interface for doing that, rather than everyone reinventing it."* The capability is the same. The abstraction level, caller model, and governance posture are completely different.

---

## Key Takeaways

1. **Microsoft Graph API** is the foundational raw data layer — CRUD operations, no intelligence, full developer control. The right choice for deterministic application logic.

2. **The semantic index is not universally accessible.** Only the Copilot Retrieval API and Copilot Chat API tap into it. Graph CRUD and Graph Search operate on different, lower-level indexes.

3. **The critical gap:** No single API provides semantic retrieval across the full M365 substrate (mail + calendar + Teams + files). This forces an architectural choice between black-box Copilot Chat or hybrid Graph CRUD + your own indexing.

4. **MCP servers are for LLM callers; Graph API is for code callers.** The capability overlap is real, but the caller model, abstraction level, and governance posture are fundamentally different.

5. **Agent 365 MCP adds a governance layer** (DLP, MIP, audit, admin control) that is very difficult to replicate by calling Graph directly — making it the right choice for enterprise agentic deployments where IT needs oversight of autonomous AI actions.

---

*Research context: Thesis comparing architectural approaches for integrating AI agents with Microsoft 365 data in enterprise environments. Focus on execution environments, data access models, and governance layers.*
