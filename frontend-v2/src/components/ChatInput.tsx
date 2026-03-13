import { useRef, useState, type KeyboardEvent } from "react";

interface ChatInputProps {
  onSend: (text: string) => void;
  disabled: boolean;
}

export default function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  function handleSubmit() {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }

  function handleInput() {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }

  return (
    <div className="chat-input-bar">
      <textarea
        ref={textareaRef}
        className="chat-textarea"
        value={value}
        onChange={(e) => {
          setValue(e.target.value);
          handleInput();
        }}
        onKeyDown={handleKeyDown}
        placeholder="Ask about your M365 data..."
        rows={1}
        disabled={disabled}
      />
      <button
        className="chat-send-btn"
        onClick={handleSubmit}
        disabled={disabled || !value.trim()}
        title="Send message"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="send-icon">
          <path d="M22 2 11 13" />
          <path d="M22 2 15 22 11 13 2 9z" />
        </svg>
      </button>
    </div>
  );
}
