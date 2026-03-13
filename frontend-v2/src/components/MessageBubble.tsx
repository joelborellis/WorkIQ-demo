import Markdown from "react-markdown";
import type { Message } from "./AppShell.tsx";

interface MessageBubbleProps {
  message: Message;
  isLatest: boolean;
}

export default function MessageBubble({ message, isLatest }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <article
      className={`message message-${message.role}${isLatest ? " message-latest" : ""}`}
    >
      <div className="message-meta">
        <span className="message-author">{isUser ? "You" : "WorkIQ"}</span>
        <time className="message-time">
          {message.timestamp.toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </time>
      </div>

      <div className="message-body">
        {isUser ? (
          <p>{message.content}</p>
        ) : (
          <Markdown>{message.content}</Markdown>
        )}
      </div>

      {message.attributions && message.attributions.length > 0 && (
        <div className="message-attributions">
          <span className="attributions-label">Sources</span>
          <ul className="attributions-list">
            {message.attributions.map((attr, i) => (
              <li key={i}>
                {attr.url ? (
                  <a
                    href={attr.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="attribution-link"
                  >
                    {attr.title}
                  </a>
                ) : (
                  <span className="attribution-text">{attr.title}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </article>
  );
}
