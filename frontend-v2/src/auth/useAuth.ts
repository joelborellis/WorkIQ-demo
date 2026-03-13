import { useContext } from "react";
import { AuthContext, type AuthContextValue } from "./AuthProvider.tsx";

export function useAuth(): AuthContextValue {
  return useContext(AuthContext);
}
