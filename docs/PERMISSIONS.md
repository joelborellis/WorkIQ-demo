# Microsoft Graph API Permissions — WorkIQ

All permissions are **delegated** (acting on behalf of the signed-in user).
There are no application permissions in this registration.

---

## Quick-reference table

| Permission | Admin consent? | Used by |
|---|:---:|---|
| `User.Read` | No | All routes (identity) |
| `Mail.Read` | No | Copilot Chat, Graph API |
| `Calendars.Read` | No | Graph API |
| `Chat.Read` | No | Copilot Chat, Graph API |
| `Files.Read.All` | **Yes** | Copilot Chat, Retrieval API, Graph API |
| `Sites.Read.All` | **Yes** | Copilot Chat, Retrieval API |
| `People.Read.All` | **Yes** | Copilot Chat, Graph API |
| `ChannelMessage.Read.All` | **Yes** | Copilot Chat |
| `OnlineMeetingTranscript.Read.All` | **Yes** | Copilot Chat |
| `ExternalItem.Read.All` | **Yes** | Copilot Chat, Retrieval API |

**6 of 10 permissions require admin consent.**
A Global Administrator or Cloud Application Administrator must grant consent
from **API permissions → Grant admin consent for \<tenant\>** in the Azure portal.

---

## Permissions by route

### All routes — Identity

| Permission | Admin consent? | Purpose |
|---|:---:|---|
| `User.Read` | No | Read the signed-in user's profile (name, email, OID used to identify the session) |

### Copilot Chat API (`/api/v1/copilot_chat`)

Calls `POST /beta/me/copilot/chats` — Microsoft's LLM synthesises an answer
grounded in the user's M365 data. The Copilot service internally queries all
M365 sources on behalf of the user, so a broad set of scopes is required.

| Permission | Admin consent? | Purpose |
|---|:---:|---|
| `Mail.Read` | No | Allows Copilot to ground answers in the user's email |
| `Chat.Read` | No | Allows Copilot to ground answers in Teams chats |
| `Files.Read.All` | **Yes** | Allows Copilot to ground answers in OneDrive files |
| `Sites.Read.All` | **Yes** | Allows Copilot to ground answers in SharePoint sites |
| `People.Read.All` | **Yes** | Allows Copilot to surface relevant colleagues |
| `ChannelMessage.Read.All` | **Yes** | Allows Copilot to ground answers in Teams channel messages |
| `OnlineMeetingTranscript.Read.All` | **Yes** | Allows Copilot to ground answers in meeting transcripts |
| `ExternalItem.Read.All` | **Yes** | Allows Copilot to ground answers in Microsoft Search connector data |

> **License requirement:** Every user who signs in must have a
> **Microsoft 365 Copilot** add-on license. Without it the API returns `403`.

### Retrieval API (`/api/v1/retrieval_api`)

Calls `POST /beta/copilot/retrieval` — returns raw semantic document chunks
from SharePoint, OneDrive, and external connectors. Searches all three sources
in parallel.

| Permission | Admin consent? | Purpose |
|---|:---:|---|
| `Files.Read.All` | **Yes** | Read OneDrive files (data source: `oneDriveBusiness`) |
| `Sites.Read.All` | **Yes** | Read SharePoint document libraries (data source: `sharePoint`) |
| `ExternalItem.Read.All` | **Yes** | Read Microsoft Search connector data (data source: `externalItem`) |

### Graph API (`/api/v1/graph_api`)

Calls Microsoft Graph v1.0 endpoints directly — fetches raw M365 data with no
LLM involved. Six endpoints are queried in parallel.

| Permission | Admin consent? | Graph endpoint | Data |
|---|:---:|---|---|
| `Mail.Read` | No | `GET /me/messages` | 5 most recent inbox emails |
| `Calendars.Read` | No | `GET /me/calendarView` | Calendar events for the next 7 days |
| `Chat.Read` | No | `GET /me/chats` | 5 most recent Teams chats |
| `Files.Read.All` | **Yes** | `GET /me/drive/recent` | 5 recently modified OneDrive files |
| `People.Read.All` | **Yes** | `GET /me/people` | 5 frequent collaborators |
| `Files.Read.All` | **Yes** | `POST /search/query` (driveItem) | Cross-M365 file search |
| `Mail.Read` | No | `POST /search/query` (message) | Cross-M365 email search |

> **Note:** The Graph Search API does not allow `message` and `driveItem` to be
> combined in a single request. The backend sends them as two parallel calls.

---

## Redirect URIs

Two redirect URIs must be registered under **Authentication → Web platform**:

| URI | Purpose |
|---|---|
| `http://localhost:8000/auth/callback` | Main app sign-in (backend → Microsoft) |
| `http://localhost:9998` | Standalone test scripts (`test_graph_endpoint.py`, `test_retrieval_endpoint.py`) |

For production, add the production callback URI alongside the localhost ones —
do not remove the localhost URIs, as removing them breaks local development.

---

## Re-consenting after new permissions are added

When new scopes are added to `GRAPH_SCOPES` in `backend/app/services/auth.py`,
existing sessions will not automatically pick them up. Each user must:

1. Sign out (click the sign-out button or clear the `workiq_session` cookie).
2. Sign back in — the consent prompt will appear for any newly added scopes
   that require user consent.

For permissions that require admin consent, the Global Administrator must
re-grant admin consent from the portal after the new permissions are added.

---

## Where permissions are configured in code

| File | Purpose |
|---|---|
| `backend/app/services/auth.py` — `GRAPH_SCOPES` | Definitive list of scopes requested at sign-in; must match what is configured in the portal |
| `backend/tests/test_graph_endpoint.py` — `SCOPES` | Subset used by the Graph API test script |
| `backend/tests/test_retrieval_endpoint.py` — `SCOPES` | Subset used by the Retrieval API test script |
| `infra/Setup-AppRegistration.ps1` | Automated portal configuration; must be kept in sync with `GRAPH_SCOPES` |
