"""
Auth routes
-----------
  GET /auth/login     – initiate OAuth 2.0 auth-code flow → redirect to Microsoft
  GET /auth/callback  – receive code from Microsoft → exchange → set session cookie
  GET /auth/logout    – clear session → redirect to Microsoft logout
  GET /auth/me        – return current user info (frontend polls this to check state)
"""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/login", include_in_schema=False)
async def login(request: Request) -> RedirectResponse:
    """
    Kick off the OAuth auth-code flow.

    Stores MSAL's flow state in the session (contains nonce/state for CSRF
    protection) then redirects the browser to Microsoft's login page.
    """
    auth_service = request.app.state.auth_service
    try:
        flow = auth_service.initiate_auth_flow()
    except ValueError as exc:
        logger.error("Failed to initiate auth flow: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Could not initiate login.") from exc

    # Persist the flow dict so the callback can validate state/nonce
    request.session["auth_flow"] = flow

    return RedirectResponse(flow["auth_uri"])


@router.get("/callback", include_in_schema=False)
async def callback(request: Request) -> RedirectResponse:
    """
    Handle the redirect from Microsoft after the user authenticates.

    Microsoft appends ``?code=...&state=...`` to the redirect URI.
    MSAL validates the state against what was stored in the session (CSRF
    protection), then exchanges the code + client secret for tokens.
    Tokens are stored server-side in the session — they never reach the browser.
    """
    settings = request.app.state.settings
    auth_service = request.app.state.auth_service

    auth_flow = request.session.pop("auth_flow", None)
    if not auth_flow:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired login session. Please try signing in again.",
        )

    # Microsoft sends an error query param if the user denied consent
    if "error" in request.query_params:
        error_desc = request.query_params.get("error_description", request.query_params["error"])
        logger.warning("Auth callback received error: %s", error_desc)
        return RedirectResponse(f"{settings.frontend_url}?auth_error={request.query_params['error']}")

    try:
        result = auth_service.complete_auth_flow(
            auth_flow=auth_flow,
            auth_response=dict(request.query_params),
        )
    except ValueError as exc:
        logger.error("Token exchange failed: %s", exc)
        return RedirectResponse(f"{settings.frontend_url}?auth_error=token_exchange_failed")

    # Store the MSAL token cache server-side (not in the cookie — it is too
    # large and would silently exceed the ~4 KB browser cookie size limit).
    # Only a small UUID key is written to the session cookie.
    cache_key = str(uuid.uuid4())
    request.app.state.token_cache_store[cache_key] = result["msal_cache"]
    request.session["cache_key"] = cache_key
    request.session["user"] = result["user"]

    logger.info("User signed in: %s", result["user"].get("email"))

    return RedirectResponse(settings.frontend_url)


@router.get("/logout", include_in_schema=False)
async def logout(request: Request) -> RedirectResponse:
    """
    Sign the user out: clear the server-side session and redirect to
    Microsoft's logout endpoint so the SSO session is also terminated.
    """
    settings = request.app.state.settings
    user_email = request.session.get("user", {}).get("email", "unknown")

    # Remove the server-side token cache for this user
    cache_key = request.session.get("cache_key")
    if cache_key:
        request.app.state.token_cache_store.pop(cache_key, None)

    request.session.clear()
    logger.info("User signed out: %s", user_email)

    ms_logout = (
        f"https://login.microsoftonline.com/{settings.tenant_id}/oauth2/v2.0/logout"
        f"?post_logout_redirect_uri={settings.frontend_url}"
    )
    return RedirectResponse(ms_logout)


@router.get("/me")
async def me(request: Request) -> JSONResponse:
    """
    Return the currently signed-in user's profile.

    The frontend calls this endpoint (with ``credentials: 'include'``) on
    page load to determine whether the user is authenticated.

    Returns:
        200 with  ``{name, email}``  if signed in.
        401 if not authenticated.
    """
    user = request.session.get("user")
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
        )
    # Omit the internal oid from the response
    return JSONResponse({"name": user.get("name"), "email": user.get("email")})
