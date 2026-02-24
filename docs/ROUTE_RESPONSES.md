# Backend Route Responses — WorkIQ

This document describes the request body, the upstream API calls made, and the
exact shape of the response for every route in the WorkIQ backend.

All three routes share the same request body model and the same response body
model. The differences are in what the backend does internally with the request
and how it builds the `answer` field.

---

## Table of contents

1. [Authentication](#authentication)
2. [Shared request body](#shared-request-body)
3. [Shared response body](#shared-response-body)
4. [POST /api/v1/copilot_chat](#post-apiv1copilot_chat)
5. [POST /api/v1/retrieval_api](#post-apiv1retrieval_api)
6. [POST /api/v1/graph_api](#post-apiv1graph_api)
7. [Error responses](#error-responses)

---

## Authentication

All three routes are protected by the server-side session. The browser must
send the `workiq_session` cookie with every request
(`credentials: 'include'` in the frontend fetch).

There is no bearer token in the request — the backend reads the MSAL token
cache from the server-side store (keyed by the session), silently refreshes it
if necessary, and uses the resulting Graph access token internally. The client
never sees or handles Graph tokens directly.

| Failure condition | HTTP status | Detail |
|---|:---:|---|
| No session cookie | `401` | "Not authenticated. Please sign in at /auth/login." |
| Session has no cache key | `401` | "Session has no token cache. Please sign in again." |
| Cache key not found in server store | `401` | "Token cache not found. Please sign in again." |
| Token refresh failed | `401` | "Token refresh failed — please sign in again." |

---

## Shared request body

All three routes accept a `CopilotChatRequest` JSON body.

```json
{
  "question": "What did I discuss with Sarah last week?",
  "conversation_id": null,
  "file_uris": null,
  "additional_context": null,
  "web_search": true,
  "timezone": "UTC"
}
```

| Field | Type | Required | Default | Used by |
|---|---|:---:|---|---|
| `question` | `string` (min 1 char) | Yes | — | All routes |
| `conversation_id` | `string \| null` | No | `null` | Copilot Chat only |
| `file_uris` | `string[] \| null` | No | `null` | Copilot Chat only |
| `additional_context` | `string[] \| null` | No | `null` | Copilot Chat only |
| `web_search` | `boolean` | No | `true` | Copilot Chat only |
| `timezone` | `string` (IANA) | No | `"UTC"` | Copilot Chat (locationHint); accepted but ignored by the other two routes |

Fields other than `question` and `timezone` are silently ignored by the
Retrieval API and Graph API routes.

---

## Shared response body

All three routes return a `CopilotChatResponse` JSON body.

```json
{
  "conversation_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "answer": "...",
  "attributions": [
    { "title": "Q3 Budget Plan.docx", "url": "https://..." }
  ],
  "turn_count": 1
}
```

| Field | Type | Notes |
|---|---|---|
| `conversation_id` | `string` | For Copilot Chat: real conversation ID from Microsoft, pass back for multi-turn. For Retrieval and Graph: a freshly generated UUID on every call (those routes are stateless). |
| `answer` | `string` | Markdown-formatted content. See per-route sections for exact structure. |
| `attributions` | `Attribution[]` | Source documents linked from the answer. May be empty. |
| `turn_count` | `integer` | For Copilot Chat: the turn counter from Microsoft's conversation object. For Retrieval and Graph: always `1`. |

**`Attribution` object:**

| Field | Type | Notes |
|---|---|---|
| `title` | `string` | Display name of the source document or provider. |
| `url` | `string \| null` | Web URL to the source. Null if the source has no URL. |

---

## POST /api/v1/copilot_chat

**What this route does:** Forwards the question to Microsoft's LLM via the
Graph beta Copilot Chat API. Microsoft retrieves relevant M365 content
internally and synthesises a natural-language answer. No raw document content
is ever returned to the backend — only the finished answer text and source
attributions.

### Upstream calls

Two sequential Graph beta calls are made per request:

**Step 1** — Create a conversation (only when `conversation_id` is not
provided):
```
POST https://graph.microsoft.com/beta/copilot/conversations
Body: {}
```
Returns a conversation object; the `id` is used in step 2.

**Step 2** — Send the user's message and get the reply:
```
POST https://graph.microsoft.com/beta/copilot/conversations/{id}/chat
```
Request body sent to Graph:
```json
{
  "message": { "text": "<question>" },
  "locationHint": { "timeZone": "<timezone>" },
  "contextualResources": {
    "files": [{ "uri": "..." }],
    "webContext": { "isWebEnabled": false }
  },
  "additionalContext": [{ "text": "..." }]
}
```
`contextualResources` is omitted entirely if neither `file_uris` nor
`web_search=false` applies. `webContext` is only sent when `web_search` is
explicitly set to `false` — the default is to leave web search on.

**Timeout:** 120 seconds (Copilot can be slow on first turn).

### What Graph returns

The Graph response is a conversation object with a `messages` array. The
backend picks the last message with `"role": "assistant"`:

```json
{
  "id": "<conversation_id>",
  "turnCount": 2,
  "messages": [
    { "role": "user", "text": "..." },
    {
      "role": "assistant",
      "text": "<synthesised Markdown answer>",
      "attributions": [
        {
          "attributionSource": "grounding",
          "providerDisplayName": "Q3 Budget.docx",
          "seeMoreWebUrl": "https://..."
        }
      ]
    }
  ]
}
```

### What the backend extracts and returns

| Response field | Source in Graph reply | Notes |
|---|---|---|
| `answer` | `messages[-1].text` (last assistant message) | Full LLM-synthesised answer. May contain Markdown, bullet lists, tables, footnote-style citations. No truncation applied. |
| `conversation_id` | `data["id"]` | The conversation object's ID — pass this back for the next turn. |
| `turn_count` | `data["turnCount"]` | Integer turn counter maintained by Microsoft. |
| `attributions` | `messages[-1].attributions` where `attributionSource == "grounding"` | Only grounding attributions are kept. Title comes from `providerDisplayName`; URL comes from `seeMoreWebUrl`. Attributions with neither field are dropped. |

**Important:** The backend never sees the raw source documents. Microsoft
retrieves and reads them internally; only the finished answer and attribution
metadata are returned.

---

## POST /api/v1/retrieval_api

**What this route does:** Queries Microsoft's semantic index directly via the
Graph beta Copilot Retrieval API. Returns ranked text *extracts* (snippets)
from matching documents — not full document content. Microsoft's LLM is not
involved; this is a pure retrieval step.

### Upstream calls

Three parallel calls are made, one per data source:
```
POST https://graph.microsoft.com/beta/copilot/retrieval   (×3, concurrent)
```

Request body per call:
```json
{
  "queryString": "<question>",
  "dataSource": "sharePoint",
  "maximumNumberOfResults": "10",
  "resourceMetadata": ["title", "author"]
}
```

`dataSource` cycles through `sharePoint`, `oneDriveBusiness`, `externalItem`.
If any source returns a non-200 response (e.g. missing permissions), it is
treated as empty and the other sources still succeed.

**Timeout:** 30 seconds per call.

### What Graph returns per source

```json
{
  "retrievalHits": [
    {
      "webUrl": "https://contoso.sharepoint.com/.../document.docx",
      "resourceMetadata": {
        "title": "Quarterly Budget Plan",
        "author": "Jane Smith"
      },
      "sensitivityLabel": {
        "displayName": "Confidential"
      },
      "extracts": [
        {
          "text": "...relevant passage from the document...",
          "relevanceScore": 0.87
        },
        {
          "text": "...another passage from the same document...",
          "relevanceScore": 0.74
        }
      ]
    }
  ]
}
```

`extracts` contains text snippets — fragments of the document that are
semantically relevant to the query. They are not the full document. A single
document hit may have multiple extract fragments from different parts of the
file.

### Processing applied by the backend

1. All hits from all three sources are merged into a single list.
2. Each hit's relevance score is computed as the **maximum** `relevanceScore`
   across all its extracts.
3. The merged list is sorted by that best-relevance score, highest first.
4. All extract `text` fragments for a hit are joined with a space into one
   continuous block. This prevents relevance scores from appearing
   mid-sentence when there are multiple extracts.
5. All text from Graph is Markdown-escaped before insertion (special characters
   like `*`, `_`, `[`, `#` are backslash-escaped).

### `answer` field structure

The `answer` string is Markdown. Each document hit produces this block:

```
**[Quarterly Budget Plan](https://...)**
*87% match · SharePoint · Jane Smith · 🔒 Confidential*

...joined extract text from all fragments of this document...

---
```

- Title is a hyperlink if `webUrl` is present, plain bold text otherwise.
- Metadata line contains: relevance percentage, data source label
  (`SharePoint`, `OneDrive`, or `Connectors`), author (if returned), and
  sensitivity label (if returned).
- Extract text is the joined snippet content — **not the full document**.
  Typical snippets are a few sentences to a paragraph.

If no results are found across all three sources, `answer` is:
```
_No results found across SharePoint, OneDrive, or Connectors for this query._
```

### What the backend extracts and returns

| Response field | Source | Notes |
|---|---|---|
| `answer` | Formatted Markdown from merged retrieval hits | See structure above. Raw document text, Markdown-escaped and snippet-only. |
| `conversation_id` | Freshly generated UUID | Retrieval API is stateless — there is no conversation concept. A new UUID is generated every call. |
| `turn_count` | Always `1` | Fixed. |
| `attributions` | One per document hit | `title` from `resourceMetadata.title` (falls back to `webUrl`); `url` from `webUrl`. |

---

## POST /api/v1/graph_api

**What this route does:** Calls six Microsoft Graph v1.0 endpoints in parallel
to assemble a snapshot of the user's current M365 state. The question is used
only as a search query string for the search endpoint; the other five endpoints
return a fixed-size data snapshot regardless of the question. No LLM is
involved — all content is raw data from Graph.

### Upstream calls

Six concurrent calls are made per request:

| # | Method | Endpoint | `$select` / params | Returns |
|---|---|---|---|---|
| 1 | `GET` | `/me/messages` | `subject, from, receivedDateTime, bodyPreview, importance` · top 5 · ordered by `receivedDateTime DESC` | 5 most recent inbox emails |
| 2 | `GET` | `/me/calendarView` | `subject, start, end, organizer, location` · top 10 · ordered by `start/dateTime` · window = now → now+7 days | Upcoming calendar events |
| 3 | `GET` | `/me/chats` | `id, topic, chatType, lastUpdatedDateTime` · top 5 | 5 most recently active Teams chats |
| 4 | `GET` | `/me/drive/recent` | `name, webUrl, lastModifiedDateTime, lastModifiedBy, size` · top 5 | 5 recently modified OneDrive files |
| 5 | `GET` | `/me/people` | `displayName, jobTitle, department, scoredEmailAddresses` · top 5 | 5 frequent collaborators |
| 6a | `POST` | `/search/query` | `entityTypes: ["message"]` · query = question · size 5 | Email search hits |
| 6b | `POST` | `/search/query` | `entityTypes: ["driveItem"]` · query = question · size 5 | File search hits |

Calls 6a and 6b are also concurrent with each other and with calls 1–5.
The Graph Search API does not allow `message` and `driveItem` in the same
request — they must be two separate calls.

Any individual endpoint returning a non-200 is logged as a warning and treated
as empty; the remaining endpoints still succeed.

**Timeout:** 30 seconds.

### What is and is not returned per data source

This is the most important thing to understand about this route: **the backend
does not return full document or email content.** Only the fields listed below
are fetched and only selected metadata and short previews are included in the
response.

**Emails** (from `/me/messages`):

| Field fetched | What is included in `answer` | What is NOT returned |
|---|---|---|
| `subject` | Full subject | — |
| `from.emailAddress.name` | Sender display name | — |
| `from.emailAddress.address` | Sender email address | — |
| `receivedDateTime` | Formatted as "Mon DD, H:MM AM/PM" | — |
| `bodyPreview` | First **180 characters** only | Full email body |
| `importance` | Fetched but not currently rendered | — |

**Calendar events** (from `/me/calendarView`):

| Field fetched | What is included in `answer` |
|---|---|
| `subject` | Full event title |
| `start.dateTime` | Formatted start time |
| `end.dateTime` | Formatted end time |
| `organizer.emailAddress.name` | Organizer display name |
| `location.displayName` | Location name |

**Teams chats** (from `/me/chats`):

| Field fetched | What is included in `answer` | What is NOT returned |
|---|---|---|
| `topic` | Chat topic / title | — |
| `chatType` | Chat type string | — |
| `lastUpdatedDateTime` | Formatted timestamp | — |
| — | — | Message content (not fetched) |

**OneDrive files** (from `/me/drive/recent`):

| Field fetched | What is included in `answer` | What is NOT returned |
|---|---|---|
| `name` | Filename | — |
| `webUrl` | Link to file | — |
| `lastModifiedDateTime` | Formatted timestamp | — |
| `lastModifiedBy.user.displayName` | Modifier name | — |
| `size` | Fetched but not rendered | File content |

**People** (from `/me/people`):

| Field fetched | What is included in `answer` |
|---|---|
| `displayName` | Full name |
| `jobTitle` | Job title |
| `department` | Department |
| `scoredEmailAddresses[0].address` | Primary email address |

**Search hits** (from `/search/query`):

| Field fetched | What is included in `answer` | What is NOT returned |
|---|---|---|
| `resource.subject` or `resource.name` | Item name / subject | — |
| `resource.webUrl` or `resource.webLink` | Link to item | — |
| `resource.@odata.type` | Item kind (e.g. `message`, `driveItem`) | — |
| `hit.summary` | First **180 characters** of search summary snippet | Full item content |

### `answer` field structure

The `answer` string is Markdown divided into up to six sections. Sections with
no data are omitted entirely.

```markdown
## 📧 Recent Emails

**[subject]**
*From: Name \<address\> · Mon DD, H:MM AM/PM*
First 180 chars of bodyPreview…

## 📅 Upcoming Calendar (next 7 days)

**[event subject]**
*Mon DD, H:MM AM – Mon DD, H:MM PM  ·  Organizer: Name · 📍 Location*

## 💬 Teams Chats

**[chat topic]**
*chatType · last active Mon DD, H:MM AM/PM*

## 📁 Recent OneDrive Files

**[[filename](https://...)]**
*Modified Mon DD, H:MM AM by Display Name*

## 👥 Frequent Collaborators

**Display Name**  —  Job Title · Department · email@contoso.com

## 🔍 Search: "query text"

**[[item name](https://...)]**  *message*
First 180 chars of search summary…
```

All user-generated text (names, subjects, file names, summaries) is
Markdown-escaped before insertion.

If all six endpoints return empty data, `answer` is:
```
_No data returned from Microsoft Graph. Verify that Calendars.Read,
Files.Read.All, Mail.Read, Chat.Read, and People.Read.All permissions
are granted._
```

### What the backend extracts and returns

| Response field | Source | Notes |
|---|---|---|
| `answer` | Formatted Markdown from all six endpoints | Snippets and metadata only — no full document or email body. |
| `conversation_id` | Freshly generated UUID | Graph API route is stateless. New UUID every call. |
| `turn_count` | Always `1` | Fixed. |
| `attributions` | OneDrive files (name + webUrl) and search hits (name + webUrl) | Emails, calendar, chats, and people do not produce attributions. |

---

## Error responses

All three routes return the same error shapes:

| Status | When | `detail` field |
|---|---|---|
| `401 Unauthorized` | No session, expired session, token refresh failure | Human-readable message (see [Authentication](#authentication)) |
| `502 Bad Gateway` | Graph API returned a non-2xx response | `"Graph API error (NNN): <upstream body>"` |
| `502 Bad Gateway` | Unexpected exception in the service layer | `"<Service> error: <exception message>"` |

Individual Graph endpoint failures inside the Graph API route (e.g. a single
endpoint returning 403 due to a missing permission) do **not** cause a 502 —
they are silently treated as empty and the other endpoints still succeed. Only
a failure in the service layer itself escalates to a 502.
