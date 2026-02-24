import { useState, useEffect } from "react";
import { backendUrl } from "./authConfig";
import { LogoutButton } from "./components/LoginButton";
import Arena from "./components/Arena";

interface User {
  name: string;
  email: string;
}

type AuthState = "loading" | "authenticated" | "unauthenticated";

function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [state, setState] = useState<AuthState>("loading");

  useEffect(() => {
    fetch(`${backendUrl}/auth/me`, { credentials: "include" })
      .then((res) => {
        if (res.ok) return res.json() as Promise<User>;
        throw new Error("Not authenticated");
      })
      .then((u) => {
        setUser(u);
        setState("authenticated");
      })
      .catch(() => {
        setState("unauthenticated");
      });
  }, []);

  return { user, state };
}

export default function App() {
  const { user, state } = useAuth();

  return (
    <div className="app">
      {/* ── Header ── */}
      <header className="app-header">
        <div className="app-header-brand">
          <span className="app-logo">
            Work<span>IQ</span>
          </span>
          <span className="app-header-badge">ARENA</span>
        </div>

        <div className="app-header-actions">
          {user && (
            <span className="app-header-user">
              {user.name || user.email}
            </span>
          )}
          {state === "authenticated" && <LogoutButton />}
          {state === "unauthenticated" && (
            <a href={`${backendUrl}/auth/login`} className="btn btn-ghost btn-sm">
              Sign in
            </a>
          )}
        </div>
      </header>

      {/* ── Main ── */}
      <main className="app-main">
        {state === "loading" && (
          <div className="loading-screen">
            <div className="loading-dots">
              <div className="loading-dot" />
              <div className="loading-dot" />
              <div className="loading-dot" />
            </div>
          </div>
        )}

        {state === "authenticated" && <Arena />}

        {state === "unauthenticated" && (
          <div className="auth-screen">
            <div className="auth-card">
              <div className="auth-logo">
                Work<span>IQ</span>
              </div>
              <div className="auth-tagline">AI Comparison Arena</div>
              <p className="auth-description">
                Ask questions about your Microsoft 365 data — emails, meetings,
                documents, and Teams — and compare responses across multiple AI
                routes simultaneously.
              </p>
              <a
                href={`${backendUrl}/auth/login`}
                className="auth-sign-in-btn"
              >
                <svg viewBox="0 0 21 21" fill="currentColor" aria-hidden="true">
                  <path d="M0 0h10v10H0zm11 0h10v10H11zM0 11h10v10H0zm11 0h10v10H11z" />
                </svg>
                Sign in with Microsoft
              </a>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
