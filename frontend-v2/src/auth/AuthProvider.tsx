import { createContext, useEffect, useState, type ReactNode } from "react";

const backendUrl =
  (import.meta.env.VITE_BACKEND_URL as string | undefined) ?? "http://localhost:8000";

export interface User {
  name: string;
  email: string;
}

export type AuthState = "loading" | "authenticated" | "unauthenticated";

export interface AuthContextValue {
  user: User | null;
  state: AuthState;
  loginUrl: string;
  logoutUrl: string;
}

export const AuthContext = createContext<AuthContextValue>({
  user: null,
  state: "loading",
  loginUrl: `${backendUrl}/auth/login`,
  logoutUrl: `${backendUrl}/auth/logout`,
});

export function AuthProvider({ children }: { children: ReactNode }) {
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

  return (
    <AuthContext
      value={{
        user,
        state,
        loginUrl: `${backendUrl}/auth/login`,
        logoutUrl: `${backendUrl}/auth/logout`,
      }}
    >
      {children}
    </AuthContext>
  );
}
