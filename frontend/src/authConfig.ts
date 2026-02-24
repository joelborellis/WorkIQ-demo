/**
 * Frontend configuration.
 *
 * Authentication is handled entirely by the backend (confidential client).
 * The frontend only needs to know the backend's base URL.
 *
 * Auth flow:
 *   1. User clicks "Sign in" → browser navigates to  BACKEND_URL/auth/login
 *   2. Backend redirects to Microsoft login page
 *   3. Microsoft POSTs auth code to BACKEND_URL/auth/callback
 *   4. Backend exchanges code + client secret for tokens (server-side)
 *   5. Backend sets a signed session cookie and redirects to FRONTEND_URL
 *   6. All API calls use  credentials: 'include'  to send the cookie
 */

/** Base URL of the Python backend, e.g. http://localhost:8000 */
export const backendUrl =
  (import.meta.env.VITE_BACKEND_URL as string | undefined) ?? "http://localhost:8000";
