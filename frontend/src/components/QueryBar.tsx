import { useCallback, useEffect, useRef } from 'react';
import type { RouteConfig } from '../routeConfig';

interface QueryBarProps {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  onToggleRoute: (routeId: string) => void;
  isSubmitting: boolean;
  routes: RouteConfig[];
  selectedRouteIds: string[];
}

export default function QueryBar({
  value,
  onChange,
  onSubmit,
  onToggleRoute,
  isSubmitting,
  routes,
  selectedRouteIds,
}: QueryBarProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!isSubmitting) textareaRef.current?.focus();
  }, [isSubmitting]);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    textarea.style.height = '0px';
    textarea.style.height = `${Math.min(textarea.scrollHeight, 240)}px`;
  }, [value]);

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        if (value.trim() && !isSubmitting) onSubmit();
      }
    },
    [isSubmitting, onSubmit, value]
  );

  return (
    <div className={`query-bar${isSubmitting ? ' submitting' : ''}`}>
      <div className="query-bar-header">
        <div className="query-bar-header-copy">
          <span className="query-bar-title">Prompt</span>
          <span className="query-bar-subtitle">
            Send the same question to the selected endpoints.
          </span>
        </div>
        <div className="query-bar-hint">Enter to run · Shift+Enter for newline</div>
      </div>

      <div className="query-bar-selection">
        <span className="query-bar-selection-label">Endpoints</span>
        <div className="query-bar-routes" role="group" aria-label="Endpoints to run">
          {routes.map(route => {
            const isSelected = selectedRouteIds.includes(route.id);
            const isLastSelected = isSelected && selectedRouteIds.length === 1;

            return (
              <label
                key={route.id}
                className={`route-chip route-chip-toggle${isSelected ? ' checked' : ''}${isSubmitting || isLastSelected ? ' disabled' : ''}`}
                style={{
                  color: route.color,
                  borderColor: `${route.color}55`,
                }}
              >
                <input
                  type="checkbox"
                  className="route-chip-input"
                  checked={isSelected}
                  onChange={() => onToggleRoute(route.id)}
                  disabled={isSubmitting || isLastSelected}
                />
                <span
                  className="route-chip-dot"
                  style={{ background: route.color }}
                  aria-hidden="true"
                />
                {route.name}
              </label>
            );
          })}
        </div>
      </div>

      <div className="query-bar-editor">
        <textarea
          ref={textareaRef}
          className="query-bar-textarea"
          value={value}
          onChange={event => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about documents, meetings, conversations, files, decisions, or any other Microsoft 365 context."
          disabled={isSubmitting}
          rows={1}
          aria-label="Query input"
        />
        <button
          type="button"
          className={`query-bar-submit${isSubmitting ? ' submitting' : ''}`}
          onClick={onSubmit}
          disabled={!value.trim() || isSubmitting || selectedRouteIds.length === 0}
          aria-label="Submit query"
          title="Submit prompt"
        >
          {isSubmitting ? (
            <span className="btn-spinner" />
          ) : selectedRouteIds.length === 1 ? (
            'Run endpoint'
          ) : (
            'Run endpoints'
          )}
        </button>
      </div>

      <div className="query-bar-meta">
        <span className="query-bar-count">
          {selectedRouteIds.length} endpoint{selectedRouteIds.length === 1 ? '' : 's'} selected
        </span>
      </div>
    </div>
  );
}
