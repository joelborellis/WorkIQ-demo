import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";

// No MSAL provider needed — authentication is handled server-side.
// The backend manages tokens; the frontend just uses a session cookie.
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
