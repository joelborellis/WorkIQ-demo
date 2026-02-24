import { useState, useRef, useEffect, type FormEvent, type KeyboardEvent } from "react";
import { sendCopilotChat, type Attribution } from "../api/copilotApi";

interface Message {
  role: "user" | "assistant";
  content: string;
  attributions?: Attribution[];
}

export function CopilotChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [error, setError] = useState<string | null>(null);

  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const sendMessage = async (question: string) => {
    setError(null);
    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setIsLoading(true);

    try {
      const data = await sendCopilotChat({
        question,
        conversation_id: conversationId,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      });
      setConversationId(data.conversation_id);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.answer,
          attributions: data.attributions,
        },
      ]);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      // Don't show "redirecting to login" as an error — the page will navigate
      if (!msg.includes("Redirecting to login")) {
        setError(msg);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const q = input.trim();
    if (!q || isLoading) return;
    setInput("");
    sendMessage(q);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      const q = input.trim();
      if (!q || isLoading) return;
      setInput("");
      sendMessage(q);
    }
  };

  const startNewChat = () => {
    setMessages([]);
    setConversationId(undefined);
    setError(null);
  };

  return (
    <div className="chat-wrapper">
      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <div className="chat-header">
        <span className="chat-title">
          {conversationId ? "Conversation" : "New conversation"}
        </span>
        {conversationId && (
          <button className="btn btn-ghost" onClick={startNewChat}>
            New chat
          </button>
        )}
      </div>

      {/* ── Messages ────────────────────────────────────────────────────────── */}
      <div className="chat-messages">
        {messages.length === 0 && !isLoading && (
          <p className="chat-empty">
            Ask anything about your Microsoft 365 data — emails, meetings,
            documents, Teams messages, and more.
          </p>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`message message--${msg.role}`}>
            <div className="message-bubble">
              <p className="message-text">{msg.content}</p>
            </div>
            {msg.attributions && msg.attributions.length > 0 && (
              <div className="message-attributions">
                <span className="attributions-label">Sources:</span>
                <ul>
                  {msg.attributions.map((attr, j) =>
                    attr.url ? (
                      <li key={j}>
                        <a href={attr.url} target="_blank" rel="noreferrer">
                          {attr.title}
                        </a>
                      </li>
                    ) : (
                      <li key={j}>{attr.title}</li>
                    )
                  )}
                </ul>
              </div>
            )}
          </div>
        ))}

        {isLoading && (
          <div className="message message--assistant">
            <div className="message-bubble message-bubble--loading">
              <span className="loading-dot" />
              <span className="loading-dot" />
              <span className="loading-dot" />
            </div>
          </div>
        )}

        {error && (
          <div className="chat-error">
            <strong>Error:</strong> {error}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* ── Input ───────────────────────────────────────────────────────────── */}
      <form className="chat-input-area" onSubmit={handleSubmit}>
        <textarea
          className="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about your emails, meetings, documents… (Enter to send, Shift+Enter for newline)"
          disabled={isLoading}
          rows={2}
        />
        <button
          type="submit"
          className="btn btn-primary chat-send"
          disabled={isLoading || !input.trim()}
        >
          Send
        </button>
      </form>
    </div>
  );
}
