import { useState } from "react";
import { useAuth } from "../auth/useAuth.ts";
import { sendChat, type ChatResponse, type Attribution } from "../api/chat.ts";
import ChatWindow from "./ChatWindow.tsx";
import ChatInput from "./ChatInput.tsx";
import TypingIndicator from "./TypingIndicator.tsx";

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  attributions?: Attribution[];
  timestamp: Date;
}

export default function AppShell() {
  const { user, logoutUrl } = useAuth();
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSend(text: string) {
    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);
    setError(null);

    try {
      const res: ChatResponse = await sendChat({
        question: text,
        conversation_id: conversationId ?? undefined,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      });

      setConversationId(res.conversation_id);

      const assistantMsg: Message = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: res.answer,
        attributions: res.attributions,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      const detail = err instanceof Error ? err.message : "Something went wrong";
      setError(detail);
    } finally {
      setIsLoading(false);
    }
  }

  function handleNewConversation() {
    setMessages([]);
    setConversationId(null);
    setError(null);
  }

  return (
    <div className="shell">
      <header className="shell-header">
        <div className="shell-brand">
          <span className="shell-brand-mark">W</span>
          <span className="shell-brand-name">WorkIQ</span>
        </div>

        <div className="shell-header-right">
          {messages.length > 0 && (
            <button
              className="btn-new-chat"
              onClick={handleNewConversation}
              title="New conversation"
            >
              New chat
            </button>
          )}
          <span className="shell-user">{user?.name || user?.email}</span>
          <a href={logoutUrl} className="btn-sign-out">
            Sign out
          </a>
        </div>
      </header>

      <main className="shell-main">
        {messages.length === 0 && !isLoading ? (
          <div className="empty-state">
            <h2 className="empty-title">What would you like to know?</h2>
            <p className="empty-subtitle">
              Ask anything about your Microsoft&nbsp;365 data&thinsp;&mdash;&thinsp;emails,
              meetings, documents, Teams chats, and more.
            </p>
          </div>
        ) : (
          <ChatWindow messages={messages} isLoading={isLoading} />
        )}

        {isLoading && <TypingIndicator />}

        {error && (
          <div className="chat-error">
            <span className="chat-error-label">Error</span>
            {error}
          </div>
        )}
      </main>

      <footer className="shell-footer">
        <ChatInput onSend={handleSend} disabled={isLoading} />
      </footer>
    </div>
  );
}
