const backendUrl =
  (import.meta.env.VITE_BACKEND_URL as string | undefined) ?? "http://localhost:8000";

export interface ChatRequest {
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

export interface ChatResponse {
  conversation_id: string;
  answer: string;
  attributions: Attribution[];
  turn_count: number;
}

export async function sendChat(payload: ChatRequest): Promise<ChatResponse> {
  const response = await fetch(`${backendUrl}/api/v1/copilot_chat`, {
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

  return response.json() as Promise<ChatResponse>;
}
