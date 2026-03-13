import { useAuth } from "../auth/useAuth.ts";

export default function LoginPage() {
  const { loginUrl } = useAuth();

  return (
    <div className="login-screen">
      <div className="login-card">
        <div className="login-brand">
          <span className="login-brand-mark">W</span>
          <h1 className="login-title">WorkIQ</h1>
        </div>

        <p className="login-subtitle">
          Ask questions about your Microsoft&nbsp;365 data.
          Copilot synthesizes answers grounded in your emails,
          calendar, Teams chats, and documents.
        </p>

        <a href={loginUrl} className="login-btn">
          <svg viewBox="0 0 21 21" fill="currentColor" aria-hidden="true" className="login-btn-icon">
            <path d="M0 0h10v10H0zm11 0h10v10H11zM0 11h10v10H0zm11 0h10v10H11z" />
          </svg>
          Sign in with Microsoft
        </a>

        <p className="login-note">
          Authentication is handled server-side.
          No tokens are stored in the browser.
        </p>
      </div>
    </div>
  );
}
