import { backendUrl } from "../authConfig";

export interface CopilotChatRequest {
  question: string;
  conversation_id?: string;
  file_uris?: string[];
  additional_context?: string[];
  web_search?: boolean;
  timezone?: string;
}

export interface Attribution {
  title: string;
  url?: string;
}

export interface CopilotChatResponse {
  conversation_id: string;
  answer: string;
  attributions: Attribution[];
  turn_count: number;
}

/**
 * POST /api/v1/copilot_chat
 *
 * The session cookie is sent automatically via  credentials: 'include'.
 * No bearer token is needed — authentication is handled server-side.
 */
export async function sendCopilotChat(
  payload: CopilotChatRequest
): Promise<CopilotChatResponse> {
  return sendToRoute("/api/v1/copilot_chat", payload);
}

/**
 * POST to any route endpoint — used by the Arena to fire multiple routes
 * simultaneously. Pass the path (e.g. "/api/v1/copilot_chat") and payload.
 */
export async function sendToRoute(
  endpoint: string,
  payload: CopilotChatRequest
): Promise<CopilotChatResponse> {
  const response = await fetch(`${backendUrl}${endpoint}`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (response.status === 401) {
    window.location.href = `${backendUrl}/auth/login`;
    throw new Error("Session expired. Redirecting to login...");
  }

  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const err = await response.json();
      detail = err.detail ?? detail;
    } catch {
      // response body may not be JSON
    }
    throw new Error(detail);
  }

  return response.json() as Promise<CopilotChatResponse>;
}
