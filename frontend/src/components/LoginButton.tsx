import { backendUrl } from "../authConfig";

interface LoginButtonProps {
  variant?: "full" | "compact";
}

/**
 * Navigates to the backend's /auth/login endpoint, which starts the
 * Microsoft OAuth flow server-side.  No MSAL or browser-side tokens needed.
 */
export function LoginButton({ variant = "compact" }: LoginButtonProps) {
  const handleLogin = () => {
    window.location.href = `${backendUrl}/auth/login`;
  };

  return (
    <button className="btn btn-primary" onClick={handleLogin}>
      {variant === "full" ? "Sign in with Microsoft" : "Sign in"}
    </button>
  );
}

export function LogoutButton() {
  const handleLogout = () => {
    window.location.href = `${backendUrl}/auth/logout`;
  };

  return (
    <button className="btn btn-secondary" onClick={handleLogout}>
      Sign out
    </button>
  );
}
