# Azure App Registration — WorkIQ

This document explains what the Azure app registration is, why it is configured
the way it is, and how to create one — either with the provided PowerShell script
or step-by-step in the Azure portal.

---

## Table of contents

1. [What is an app registration and why does WorkIQ need one?](#what-is-an-app-registration)
2. [How the authentication flow works](#how-the-authentication-flow-works)
3. [Why Web platform, not Single-page Application?](#why-web-platform-not-single-page-application)
4. [Option A — Automated setup (recommended)](#option-a--automated-setup-recommended)
5. [Option B — Manual setup in the Azure portal](#option-b--manual-setup-in-the-azure-portal)
6. [Environment variables reference](#environment-variables-reference)
7. [Production deployment checklist](#production-deployment-checklist)
8. [Troubleshooting](#troubleshooting)

---

## What is an app registration?

An app registration is a record in Microsoft Entra ID (formerly Azure Active
Directory) that tells Microsoft:

- **Who this application is** — its name, type, and which tenant it belongs to.
- **What it is allowed to do** — which Microsoft 365 APIs it can call and on
  whose behalf.
- **Where to send the user after they sign in** — the redirect URI.

WorkIQ needs an app registration because it calls the Microsoft 365 Copilot Chat
API, which is part of Microsoft Graph. Before Microsoft will respond to those
API calls, it needs to know that a legitimate, consented application is making
the request on behalf of a signed-in user.

---

## How the authentication flow works

WorkIQ uses the **OAuth 2.0 Authorization Code flow**. Here is what happens when
a user signs in, in plain terms:

**Step 1 — The user clicks "Sign in"**
The browser navigates to the WorkIQ backend at `/auth/login`. No sign-in form
is shown yet — this just starts the process.

**Step 2 — The backend redirects to Microsoft**
The backend tells the browser to go to Microsoft's login page, along with a
secret piece of state it will use later to verify the response is genuine.

**Step 3 — The user authenticates with Microsoft**
The user enters their Microsoft 365 credentials on Microsoft's own login page
(WorkIQ never sees the password). If required, the user also completes MFA.

**Step 4 — Microsoft sends an authorization code to the backend**
After a successful login, Microsoft redirects the browser to
`/auth/callback?code=...` on the WorkIQ backend. The `code` is a short-lived,
single-use token that can be exchanged for real tokens.

**Step 5 — The backend exchanges the code for tokens**
The backend sends the code to Microsoft along with the **client secret** — a
credential that proves the backend is the legitimate WorkIQ application, not an
impostor. Microsoft returns an access token (to call Graph APIs) and a refresh
token (to silently get new access tokens when they expire).

**Step 6 — Tokens are stored on the server, not in the browser**
The tokens are stored in a server-side session. The browser receives only a
signed session cookie — not the tokens themselves. This means even if the
frontend were compromised, an attacker could not extract the tokens from browser
memory or storage.

**Step 7 — The backend redirects the user back to the app**
The user is sent back to the frontend, now signed in. From here, any API calls
the frontend makes include the session cookie, and the backend uses the stored
token to call Microsoft Graph on the user's behalf.

**Token refresh (automatic)**
Access tokens expire after approximately one hour. The backend handles renewal
silently using the stored refresh token — the user is never asked to sign in
again unless they have been inactive for a very long time (typically 90 days).

```
 Browser (React)          Python backend            Microsoft Entra
 ───────────────          ──────────────            ───────────────

 Click "Sign in"
      │
      ▼
 GET /auth/login ────────►  Redirect to
                            Microsoft login ─────►  Login page shown
                                                         │
                                                    User signs in
                                                         │
                            GET /auth/callback ◄─────── │
                            ?code=...
                                │
                            Exchange code
                            + client secret ─────►  Returns tokens
                                │
                            Store tokens in
                            server session
                            Set session cookie
                                │
 Redirect to app ◄─────────────┘
      │
 GET /auth/me ───────────►  Read session
 (with cookie)              Return {name, email}
      │
 Render chat UI
      │
 POST /api/v1/copilot_chat  acquire_token_silent()
 (with cookie) ─────────►   Call Graph Copilot API ►  Return answer
                                │
 Display answer ◄──────────────┘
```

---

## Why Web platform, not Single-page Application?

When setting up the app registration, Microsoft asks you to choose a platform
type. WorkIQ uses **Web**, not **Single-page application (SPA)**. Here is why.

A SPA registration gives tokens directly to the browser (stored in
`sessionStorage` or `localStorage`). This is simpler to set up but has a
significant downside: if an attacker manages to run malicious JavaScript on the
page (a cross-site scripting attack), they can read those tokens and impersonate
the user anywhere that token is valid.

The Web (confidential client) approach keeps tokens entirely on the server. The
browser only ever holds a session cookie. Even if malicious JavaScript runs,
there are no tokens to steal.

Additionally, only a confidential client can hold a **client secret** — a
credential that Microsoft uses to verify the application's identity when
exchanging the authorization code for tokens. This adds a second layer of proof
beyond just knowing the authorization code.

| | SPA (public client) | Web (confidential client) |
|---|---|---|
| Tokens stored in browser | Yes (`sessionStorage`) | No — server only |
| Vulnerable to XSS token theft | Yes | No |
| Proves app identity with secret | No | Yes |
| Handles token refresh | MSAL in browser | Backend, silently |

---

## Option A — Automated setup (recommended)

The `infra/Setup-AppRegistration.ps1` script performs every configuration step
and writes the environment variable files for you.

### Prerequisites

- PowerShell 7.2 or later
- Azure CLI 2.37 or later — install from <https://aka.ms/installazurecli>
- An account with **Application Administrator** or **Global Administrator** role
  in the target Entra ID tenant
- **Global Administrator** or **Cloud Application Administrator** role to grant
  admin consent (step 7 of the script)

### Run the script

Open a PowerShell terminal in the root of the repository and run:

```powershell
az login
.\infra\Setup-AppRegistration.ps1 -WriteEnvFiles
```

`az login` opens a browser window to sign in to Azure. Once complete, the
script runs automatically and prints a summary:

```
══════════════════════════════════════════════════════════════════
  WorkIQ — App Registration Complete
══════════════════════════════════════════════════════════════════
  Tenant ID     : xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
  Client ID     : xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
  Client Secret : <value — shown once>
  Redirect URI  : http://localhost:8000/auth/callback
  Frontend URL  : http://localhost:5173
  SECRET_KEY    : <random 32-byte value>
══════════════════════════════════════════════════════════════════
```

With `-WriteEnvFiles`, the values are written to `backend/.env` and
`frontend/.env.local` automatically.

### Script parameters

| Parameter | Default | Description |
|---|---|---|
| `-BackendUrl` | `http://localhost:8000` | Base URL of the backend. The redirect URI is `{BackendUrl}/auth/callback`. |
| `-FrontendUrl` | `http://localhost:5173` | Where the backend redirects the user after sign-in. |
| `-AppDisplayName` | `WorkIQ` | How the app appears in Entra ID. |
| `-SecretExpiryYears` | `1` | Lifetime of the client secret. |
| `-SkipAdminConsent` | off | Use this if you do not have admin rights. Grant consent manually afterwards (see [Troubleshooting](#troubleshooting)). |
| `-WriteEnvFiles` | off | Write `backend/.env` and `frontend/.env.local`. |

### Other scripts

**Add a redirect URI** (e.g. after deploying to production):
```powershell
.\infra\Update-RedirectUris.ps1 `
    -ClientId "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" `
    -Add "https://api.contoso.com/auth/callback"
```

**Remove the registration** (e.g. to start fresh or clean up a test tenant):
```powershell
.\infra\Remove-AppRegistration.ps1 -ClientId "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
```

---

## Option B — Manual setup in the Azure portal

If you prefer to configure the registration by hand, follow these steps in
order.

### Step 1 — Create the registration

1. Sign in to the [Azure portal](https://portal.azure.com).
2. In the top search bar, search for **Microsoft Entra ID** and open it.
3. In the left menu, select **App registrations**, then **New registration**.
4. Fill in the form:
   - **Name**: `WorkIQ` (or any name you prefer)
   - **Supported account types**: select **Accounts in this organizational
     directory only** (single tenant)
   - **Redirect URI**: leave blank for now — you will set it in the next step
5. Click **Register**.

You will be taken to the overview page for the new registration. Note the
**Application (client) ID** and **Directory (tenant) ID** — you will need both.

### Step 2 — Add the Web platform and redirect URI

1. In the left menu, select **Authentication**.
2. Click **Add a platform**, then choose **Web**.
3. In the **Redirect URIs** field, enter:
   ```
   http://localhost:8000/auth/callback
   ```
4. Under **Implicit grant and hybrid flows**, make sure **both** checkboxes are
   **unchecked**:
   - ID tokens — **off**
   - Access tokens — **off**

   These options are for older, less secure flows. The auth-code flow used by
   WorkIQ does not need them.
5. Click **Configure**, then **Save**.

### Step 3 — Add Microsoft Graph permissions

1. In the left menu, select **API permissions**.
2. Click **Add a permission** → **Microsoft Graph** → **Delegated permissions**.
3. Use the search box to find and check each of the following permissions:

   | Permission | Why it is needed |
   |---|---|
   | `Sites.Read.All` | Read SharePoint sites and documents |
   | `Mail.Read` | Read the user's emails |
   | `People.Read.All` | Read organisational people data |
   | `OnlineMeetingTranscript.Read.All` | Read Teams meeting transcripts |
   | `Chat.Read` | Read Teams chat messages |
   | `ChannelMessage.Read.All` | Read Teams channel messages |
   | `ExternalItem.Read.All` | Read data from Microsoft Search connectors |

4. Click **Add permissions**.
5. Back on the API permissions page, click **Grant admin consent for
   \<your tenant name\>** and confirm. This step requires a Global Administrator
   or Cloud Application Administrator account.

   > Without admin consent, users will see a "needs approval" screen every time
   > they try to sign in, and the Copilot Chat API will return errors.

### Step 4 — Create a client secret

1. In the left menu, select **Certificates & secrets**.
2. Under **Client secrets**, click **New client secret**.
3. Enter a description (e.g. `WorkIQ-Backend`) and choose an expiry (1 year is
   a sensible default).
4. Click **Add**.
5. **Copy the secret value immediately.** It is displayed only once. If you
   navigate away without copying it, you will need to delete it and create a
   new one.

### Step 5 — Create the environment files

Using the values you have collected, create `backend/.env` and
`frontend/.env.local` as shown in the
[Environment variables reference](#environment-variables-reference) section.

---

## Environment variables reference

### `backend/.env`

```dotenv
# Azure Entra ID — from the app registration Overview page
TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
CLIENT_SECRET=<value from Certificates & secrets>

# Session signing key — generate with:
#   python -c "import secrets; print(secrets.token_hex(32))"
# Changing this value invalidates all active user sessions.
SECRET_KEY=<random hex string>

# OAuth — must exactly match the URI registered in the app registration
REDIRECT_URI=http://localhost:8000/auth/callback

# Where to send the user after sign-in / sign-out
FRONTEND_URL=http://localhost:5173

# CORS — must be an explicit origin (not *) when credentials are used
ALLOWED_ORIGINS=http://localhost:5173

DEBUG=false
```

### `frontend/.env.local`

```dotenv
# The frontend only needs to know where the backend is.
# All Azure credentials stay on the server.
VITE_BACKEND_URL=http://localhost:8000
```

---

## Production deployment checklist

When deploying to Azure Container Apps or any production host, work through
this list.

- [ ] **Add the production redirect URI** to the app registration:
  ```powershell
  .\infra\Update-RedirectUris.ps1 `
      -ClientId "<client-id>" `
      -Add "https://api.yourdomain.com/auth/callback"
  ```

- [ ] **Set `REDIRECT_URI`** in the backend environment to the production value:
  ```
  REDIRECT_URI=https://api.yourdomain.com/auth/callback
  ```

- [ ] **Set `FRONTEND_URL`** and **`ALLOWED_ORIGINS`** to the production
  frontend URL:
  ```
  FRONTEND_URL=https://app.yourdomain.com
  ALLOWED_ORIGINS=https://app.yourdomain.com
  ```

- [ ] **Generate a new `SECRET_KEY`** for production (different from the one
  used in development). Store it as a secret in Key Vault or as a Container App
  secret — never in source control.

- [ ] **Enable HTTPS-only cookies** — in `backend/app/main.py`, change:
  ```python
  https_only=False   # dev
  ```
  to:
  ```python
  https_only=not settings.debug   # uses DEBUG=false in prod → https_only=True
  ```

- [ ] **Plan for secret rotation** — client secrets expire. Create a new secret
  before the old one expires, update the `CLIENT_SECRET` environment variable,
  and then delete the old secret from the portal.

- [ ] **Assign Copilot licenses** — every user who will sign in needs a
  Microsoft 365 Copilot add-on license. Without it the API returns `403`.

---

## Troubleshooting

### "The redirect URI does not match" (`AADSTS50011`)

The URI the backend sent to Microsoft during login does not exactly match any
URI registered in the app registration.

**Check:**
- Does `REDIRECT_URI` in `backend/.env` match what is in the portal under
  **Authentication → Redirect URIs**? Trailing slashes, HTTP vs HTTPS, and port
  numbers must be identical.
- If you recently added a new URI, it can take a minute to propagate. Try again.

**Fix:**
```powershell
.\infra\Update-RedirectUris.ps1 `
    -ClientId "<client-id>" `
    -Add "http://localhost:8000/auth/callback"
```

### "The user or administrator has not consented" (`AADSTS65001`)

Admin consent has not been granted for the Graph permissions.

**Fix:** A Global Administrator or Cloud Application Administrator must go to
**API permissions → Grant admin consent for \<tenant\>** in the portal, or run:
```powershell
az ad app permission admin-consent --id <object-id-of-registration>
```

### API returns `403 Forbidden` after successful sign-in

The signed-in user does not have a Microsoft 365 Copilot add-on license. Assign
the license through the [Microsoft 365 admin center](https://admin.microsoft.com).

### "Session has no token cache" or "Not authenticated" after sign-in

The session cookie was not set or was rejected by the browser.

**Common causes:**
- The frontend is on a different origin from the backend (e.g. different port)
  and the browser is blocking the cookie due to `SameSite` policy. Make sure
  `ALLOWED_ORIGINS` in `backend/.env` includes the frontend origin exactly.
- The `SECRET_KEY` was changed after the user signed in, which invalidates their
  session. They need to sign in again.
- In production, `https_only=True` is set but the request is coming over HTTP.

### "Token refresh failed — please sign in again"

The refresh token has expired. This happens after approximately 90 days of
inactivity for single-tenant apps, or if an administrator has revoked the
user's session. The user needs to sign in again.

### The script fails with "Insufficient privileges"

The account used to run `Setup-AppRegistration.ps1` does not have permission
to create app registrations or grant admin consent.

- To **create and configure** the registration: requires at least
  **Application Administrator**.
- To **grant admin consent**: requires **Global Administrator** or
  **Cloud Application Administrator**.

If you only have Application Administrator rights, run the script with
`-SkipAdminConsent` and ask a Global Admin to grant consent separately in
the portal.
