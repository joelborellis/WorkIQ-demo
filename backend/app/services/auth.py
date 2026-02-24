"""
AuthService
-----------
Manages the OAuth 2.0 Authorization Code flow (confidential client) and
server-side token lifecycle.

Why confidential client instead of SPA + OBO?
──────────────────────────────────────────────
In the OBO (On-Behalf-Of) pattern, the frontend holds a token in sessionStorage
and passes it to the backend.  The confidential-client auth-code pattern is more
secure:

  • Tokens are NEVER stored in the browser.
  • The client secret (held only by the backend) proves the app's identity.
  • The backend silently refreshes expired tokens without user interaction.
  • If the frontend is compromised, an attacker cannot extract Graph tokens.

Flow
────
  1. /auth/login  → initiate_auth_code_flow()  → redirect to Microsoft login
  2. /auth/callback  → acquire_token_by_auth_code_flow()  → tokens stored in session
  3. Protected routes → acquire_token_silent()  → returns (refreshing if needed)
"""
from __future__ import annotations

import logging

import msal

from app.config import Settings

logger = logging.getLogger(__name__)

# Microsoft Graph delegated scopes required by the Copilot Chat API.
GRAPH_SCOPES: list[str] = [
    # ── Identity ──────────────────────────────────────────────────────────────
    "https://graph.microsoft.com/User.Read",
    # ── Mail (Copilot Chat + Graph API) ───────────────────────────────────────
    "https://graph.microsoft.com/Mail.Read",
    # ── Calendar (Graph API) ──────────────────────────────────────────────────
    "https://graph.microsoft.com/Calendars.Read",
    # ── Files (Retrieval API + Graph API) ─────────────────────────────────────
    "https://graph.microsoft.com/Files.Read.All",
    "https://graph.microsoft.com/Sites.Read.All",
    # ── Teams (Copilot Chat + Graph API) ──────────────────────────────────────
    "https://graph.microsoft.com/Chat.Read",
    "https://graph.microsoft.com/ChannelMessage.Read.All",
    # ── People (Copilot Chat + Graph API) ─────────────────────────────────────
    "https://graph.microsoft.com/People.Read.All",
    # ── Meetings / Connectors (Copilot Chat + Retrieval API) ──────────────────
    "https://graph.microsoft.com/OnlineMeetingTranscript.Read.All",
    "https://graph.microsoft.com/ExternalItem.Read.All",
]


class AuthService:
    """
    Wraps MSAL's ConfidentialClientApplication for the auth-code flow.

    A single instance is created at application startup and stored on
    ``app.state.auth_service``.  The token cache is NOT stored here —
    each request deserialises the per-user cache from the session cookie,
    performs its operation, then re-serialises it back into the session.
    This keeps the service stateless and safe for concurrent requests.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _make_msal_app(self, token_cache: msal.SerializableTokenCache) -> msal.ConfidentialClientApplication:
        """Create a fresh ConfidentialClientApplication backed by the given cache."""
        return msal.ConfidentialClientApplication(
            client_id=self._settings.client_id,
            client_credential=self._settings.client_secret,
            authority=self._settings.authority,
            token_cache=token_cache,
        )

    # ── Login initiation ─────────────────────────────────────────────────────

    def initiate_auth_flow(self) -> dict:
        """
        Start the auth-code flow.

        Returns the flow dict that must be stored in the user's session.
        It contains the ``auth_uri`` to redirect the user to, plus MSAL's
        internal state/nonce values used for CSRF validation on callback.
        """
        cache = msal.SerializableTokenCache()
        app = self._make_msal_app(cache)
        flow = app.initiate_auth_code_flow(
            scopes=GRAPH_SCOPES,
            redirect_uri=self._settings.redirect_uri,
        )
        if "error" in flow:
            raise ValueError(f"Failed to initiate auth flow: {flow}")
        return flow

    # ── Callback — exchange code for tokens ──────────────────────────────────

    def complete_auth_flow(self, auth_flow: dict, auth_response: dict) -> dict:
        """
        Complete the auth-code flow after the user has signed in.

        Args:
            auth_flow:     The flow dict that was stored in the session at login.
            auth_response: The query-string parameters received at the callback
                           (must include ``code`` and ``state``).

        Returns:
            A dict with keys:
              - ``msal_cache``: serialised token cache to store in the session
              - ``user``:       dict with ``name`` and ``email`` from the id_token

        Raises ``ValueError`` on failure (bad state, expired code, etc.).
        """
        cache = msal.SerializableTokenCache()
        app = self._make_msal_app(cache)

        result = app.acquire_token_by_auth_code_flow(auth_flow, auth_response)

        if "error" in result:
            raise ValueError(
                f"{result.get('error')}: {result.get('error_description', 'unknown')}"
            )

        claims = result.get("id_token_claims", {})
        return {
            "msal_cache": cache.serialize(),
            "user": {
                "name":  claims.get("name", ""),
                "email": claims.get("preferred_username", ""),
                "oid":   claims.get("oid", ""),
            },
        }

    # ── Token retrieval (used by protected routes) ────────────────────────────

    def get_graph_token(self, serialised_cache: str) -> tuple[str, str | None]:
        """
        Return a valid Graph API access token for the cached user.

        Uses ``acquire_token_silent``, which automatically refreshes expired
        tokens using the stored refresh token — no user interaction needed.

        Args:
            serialised_cache: The MSAL token cache from ``request.session``.

        Returns:
            ``(access_token, updated_cache_or_None)`` — if the cache was
            updated (i.e. a refresh occurred), the caller should write the
            new value back to the session.

        Raises ``ValueError`` if no valid token can be obtained (e.g. the
        session has expired and a fresh login is required).
        """
        cache = msal.SerializableTokenCache()
        cache.deserialize(serialised_cache)

        app = self._make_msal_app(cache)
        accounts = app.get_accounts()

        if not accounts:
            raise ValueError("No account in cache — please sign in again.")

        result = app.acquire_token_silent(scopes=GRAPH_SCOPES, account=accounts[0])

        if not result or "access_token" not in result:
            raise ValueError("Token refresh failed — please sign in again.")

        updated_cache = cache.serialize() if cache.has_state_changed else None
        return result["access_token"], updated_cache
