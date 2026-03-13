import { useEffect, useRef } from "react";
import type { Message } from "./AppShell.tsx";
import MessageBubble from "./MessageBubble.tsx";

interface ChatWindowProps {
  messages: Message[];
  isLoading: boolean;
}

export default function ChatWindow({ messages, isLoading }: ChatWindowProps) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  return (
    <div className="chat-window">
      <div className="chat-messages">
        {messages.map((msg, i) => (
          <MessageBubble key={msg.id} message={msg} isLatest={i === messages.length - 1} />
        ))}
        <div ref={endRef} />
      </div>
    </div>
  );
}
