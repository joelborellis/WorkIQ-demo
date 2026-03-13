import { useAuth } from "./auth/useAuth.ts";
import LoginPage from "./components/LoginPage.tsx";
import AppShell from "./components/AppShell.tsx";

export default function App() {
  const { state } = useAuth();

  if (state === "loading") {
    return (
      <div className="loading-screen">
        <div className="loading-card">
          <div className="loading-spinner" />
          <span className="loading-text">Verifying session&hellip;</span>
        </div>
      </div>
    );
  }

  if (state === "unauthenticated") {
    return <LoginPage />;
  }

  return <AppShell />;
}
