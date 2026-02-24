import { useRef, useEffect, useCallback } from 'react';
import type { RouteConfig } from '../routeConfig';

interface QueryBarProps {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  isSubmitting: boolean;
  routes: RouteConfig[];
}

export default function QueryBar({
  value,
  onChange,
  onSubmit,
  isSubmitting,
  routes,
}: QueryBarProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!isSubmitting) textareaRef.current?.focus();
  }, [isSubmitting]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        if (value.trim() && !isSubmitting) onSubmit();
      }
    },
    [value, isSubmitting, onSubmit]
  );

  return (
    <div className={`query-bar${isSubmitting ? ' submitting' : ''}`}>
      <div className="query-bar-inner">
        <span className="query-bar-prefix" aria-hidden="true">›</span>
        <textarea
          ref={textareaRef}
          className="query-bar-textarea"
          value={value}
          onChange={e => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask anything about your M365 data — all three APIs respond in parallel…"
          disabled={isSubmitting}
          rows={1}
          aria-label="Query input"
        />
        <button
          className={`query-bar-submit${isSubmitting ? ' submitting' : ''}`}
          onClick={onSubmit}
          disabled={!value.trim() || isSubmitting}
          aria-label="Submit query"
          title="Submit (Enter)"
        >
          {isSubmitting ? <span className="btn-spinner" /> : '▶'}
        </button>
      </div>
      <div className="query-bar-meta">
        <span className="query-bar-hint">↵ SEND  ·  ⇧↵ NEWLINE</span>
        <div className="query-bar-routes">
          {routes.map(r => (
            <span
              key={r.id}
              className="route-chip"
              style={{
                color: r.color,
                borderColor: `${r.color}55`,
                background: r.dimColor,
              }}
            >
              {r.name}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
