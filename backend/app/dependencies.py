"""
Shared FastAPI dependency functions.

Auth flow
─────────
The frontend sets/reads a session cookie (``credentials: 'include'``).
Every protected route uses  get_graph_token()  which:

  1. Reads the serialised MSAL token cache from the session cookie.
  2. Calls acquire_token_silent() — automatically refreshes if expired.
  3. Writes the updated cache back to the session if a refresh occurred.
  4. Returns a valid Graph API access token.

No bearer tokens, no MSAL in the browser, no OBO flow.

Adding new protected routes
────────────────────────────
  Depends(get_current_user)  → needs the user's profile from the session
  Depends(get_graph_token)   → needs to call Microsoft Graph on behalf of the user
"""
from __future__ import annotations

import logging

from fastapi import Depends, HTTPException, Request, status

logger = logging.getLogger(__name__)


async def get_current_user(request: Request) -> dict:
    """
    Return the signed-in user's profile from the server-side session.
    Raises HTTP 401 if the session is missing or contains no user.
    """
    user = request.session.get("user")
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Please sign in at /auth/login.",
        )
    return user


async def get_graph_token(
    request: Request,
    _user: dict = Depends(get_current_user),
) -> str:
    """
    Return a valid Microsoft Graph API access token for the current user.

    Reads the MSAL token cache from the session, refreshes if necessary,
    and writes an updated cache back to the session if a refresh occurred.

    Raises HTTP 401 if the session is expired or the token cannot be refreshed.
    """
    auth_service = request.app.state.auth_service
    cache_key = request.session.get("cache_key")
    if not cache_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has no token cache. Please sign in again.",
        )

    serialised_cache = request.app.state.token_cache_store.get(cache_key)
    if not serialised_cache:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token cache not found. Please sign in again.",
        )

    try:
        token, updated_cache = auth_service.get_graph_token(serialised_cache)
    except ValueError as exc:
        logger.warning("Token retrieval failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    # Persist the refreshed cache back to the server-side store
    if updated_cache:
        request.app.state.token_cache_store[cache_key] = updated_cache

    return token
