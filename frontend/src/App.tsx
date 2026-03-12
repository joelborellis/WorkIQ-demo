import { useEffect, useState } from "react";
import { backendUrl } from "./authConfig";
import { LogoutButton } from "./components/LoginButton";
import Arena from "./components/Arena";
import { ROUTES } from "./routeConfig";

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
    <div className="app-shell">
      <header className="app-header">
        <div className="app-brand">
          <div className="app-brand-mark">WI</div>
          <div className="app-brand-copy">
            <span className="app-brand-name">WorkIQ Arena</span>
            <span className="app-brand-meta">
              Microsoft 365 endpoint comparison workspace
            </span>
          </div>
        </div>

        <div className="app-header-actions">
          <span className="app-session-state">
            {state === "authenticated"
              ? "Authenticated"
              : state === "loading"
                ? "Checking session"
                : "Signed out"}
          </span>
          {user && (
            <span className="app-header-user">{user.name || user.email}</span>
          )}
          {state === "authenticated" && <LogoutButton />}
          {state === "unauthenticated" && (
            <a
              href={`${backendUrl}/auth/login`}
              className="btn btn-secondary btn-sm"
            >
              Sign in
            </a>
          )}
        </div>
      </header>

      <main className="app-main">
        {state === "loading" && (
          <div className="loading-screen">
            <div className="loading-card">
              <div className="loading-spinner" />
              <div className="loading-copy">
                Loading workspace and validating your session.
              </div>
            </div>
          </div>
        )}

        {state === "authenticated" && <Arena />}

        {state === "unauthenticated" && (
          <div className="auth-screen">
            <div className="auth-layout">
              <section className="auth-panel auth-panel-overview">
                <p className="auth-summary">
                  One prompt fans out across every configured Microsoft 365
                  endpoint, with responses rendered side by side for comparison.
                </p>

                <div className="auth-route-list">
                  {ROUTES.map((route) => (
                    <div key={route.id} className="auth-route-card">
                      <div className="auth-route-top">
                        <span
                          className="auth-route-swatch"
                          style={{ background: route.color }}
                        />
                        <div className="auth-route-heading">
                          <span
                            className="auth-route-name"
                            style={{ color: route.color }}
                          >
                            {route.name}
                          </span>
                          <span className="auth-route-method">
                            {route.method}
                          </span>
                        </div>
                      </div>
                      <p className="auth-route-label">{route.label}</p>
                      <p className="auth-route-description">
                        {route.description}
                      </p>
                      <div className="auth-route-sources">
                        {route.dataSources.slice(0, 4).map((source) => (
                          <span key={source} className="auth-source-pill">
                            {source}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </section>

              <section className="auth-panel auth-panel-login">
                <p className="auth-login-text">
                  Sign in with Microsoft to open the workspace and run the
                  existing server-backed endpoints against your tenant data.
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
                <p className="auth-login-note">
                  Authentication remains server-side. The frontend uses the
                  session cookie already established by the backend.
                </p>
              </section>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
