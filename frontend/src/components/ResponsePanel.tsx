import React, { useMemo, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import type { Attribution } from '../api/copilotApi';
import type { RouteConfig } from '../routeConfig';
import { splitIntoTokens } from '../utils/diff';

export type PanelStatus = 'idle' | 'loading' | 'done' | 'error';

interface ResponsePanelProps {
  route: RouteConfig;
  status: PanelStatus;
  answer: string;
  attributions: Attribution[];
  latencyMs: number | null;
  error: string | null;
  uniqueWords: Set<string>;
  isCompact?: boolean;
  onFocus?: () => void;
}

const SKELETON_WIDTHS = ['82%', '68%', '91%', '55%', '76%', '88%', '43%'];

function SkeletonLines() {
  return (
    <div className="panel-skeleton">
      {SKELETON_WIDTHS.map((w, i) => (
        <div
          key={i}
          className="skeleton-line"
          style={{ width: w, animationDelay: `${i * 0.07}s` }}
        />
      ))}
    </div>
  );
}

function useMarkdownComponents(
  uniqueWords: Set<string>,
  routeColor: string
) {
  const highlightString = useCallback(
    (text: string): React.ReactNode => {
      if (uniqueWords.size === 0) return text;
      const tokens = splitIntoTokens(text);
      const hasMatch = tokens.some(
        t => t.type === 'word' && uniqueWords.has(t.value.toLowerCase())
      );
      if (!hasMatch) return text;
      return tokens.map((token, i) =>
        token.type === 'word' && uniqueWords.has(token.value.toLowerCase()) ? (
          <mark
            key={i}
            style={
              {
                '--mark-bg': `${routeColor}28`,
                '--mark-color': routeColor,
              } as React.CSSProperties
            }
          >
            {token.value}
          </mark>
        ) : (
          token.value
        )
      );
    },
    [uniqueWords, routeColor]
  );

  const wrapChildren = useCallback(
    (children: React.ReactNode): React.ReactNode => {
      if (typeof children === 'string') return highlightString(children);
      if (Array.isArray(children)) {
        return children.map((child, i) =>
          typeof child === 'string' ? (
            <React.Fragment key={i}>{highlightString(child)}</React.Fragment>
          ) : (
            child
          )
        );
      }
      return children;
    },
    [highlightString]
  );

  return useMemo(
    () => ({
      p: ({ children, ...props }: React.ComponentPropsWithoutRef<'p'>) => (
        <p {...props}>{wrapChildren(children)}</p>
      ),
      li: ({ children, ...props }: React.ComponentPropsWithoutRef<'li'>) => (
        <li {...props}>{wrapChildren(children)}</li>
      ),
      td: ({ children, ...props }: React.ComponentPropsWithoutRef<'td'>) => (
        <td {...props}>{wrapChildren(children)}</td>
      ),
      th: ({ children, ...props }: React.ComponentPropsWithoutRef<'th'>) => (
        <th {...props}>{wrapChildren(children)}</th>
      ),
    }),
    [wrapChildren]
  );
}

export default function ResponsePanel({
  route,
  status,
  answer,
  attributions,
  latencyMs,
  error,
  uniqueWords,
  isCompact,
  onFocus,
}: ResponsePanelProps) {
  const isDone = status === 'done';
  const isLoading = status === 'loading';
  const isError = status === 'error';

  const mdComponents = useMarkdownComponents(uniqueWords, route.color);

  const panelStyle = {
    '--route-color': route.color,
    '--route-glow': route.glowColor,
    borderColor: isLoading
      ? `${route.color}50`
      : isDone
      ? `${route.color}28`
      : undefined,
  } as React.CSSProperties;

  return (
    <div
      className={`response-panel status-${status}${isCompact ? ' compact' : ''}`}
      style={panelStyle}
      onClick={isCompact ? onFocus : undefined}
      role={isCompact ? 'button' : undefined}
      tabIndex={isCompact ? 0 : undefined}
    >
      {/* ── Header ── */}
      <div className="panel-header">
        <div className="panel-header-left">
          {/* Row 1: dot + name + status chip */}
          <div className="panel-name-row">
            <div
              className={`panel-route-dot${isLoading ? ' pulsing' : ''}`}
              style={{ background: route.color }}
            />
            <span className="panel-route-name" style={{ color: route.color }}>
              {route.name}
            </span>
            {isLoading && (
              <span className="panel-status-chip loading">QUERYING</span>
            )}
            {isError && (
              <span className="panel-status-chip error">ERROR</span>
            )}
          </div>

          {/* Row 2: method badge + full API name (hidden in compact mode) */}
          {!isCompact && (
            <div className="panel-route-desc">
              <span
                className="panel-method-badge"
                style={{ borderColor: `${route.color}40`, color: route.color }}
              >
                {route.method}
              </span>
              <span className="panel-route-desc-sep">·</span>
              <span className="panel-route-label">{route.label}</span>
            </div>
          )}
        </div>

        {/* Latency — right-aligned, shown once we have a value */}
        {latencyMs !== null && (
          <div className={`panel-latency${isDone ? ' done' : ''}`}>
            {isDone && <span className="latency-check">✓</span>}
            {latencyMs.toLocaleString()}ms
          </div>
        )}
      </div>

      {/* ── Body ── */}
      <div className="panel-body">
        {status === 'idle' && (
          <div className="panel-idle">
            <div className="panel-idle-glyph">◎</div>
            <div className="panel-idle-text">Waiting for query</div>
          </div>
        )}

        {isLoading && <SkeletonLines />}

        {isDone && answer && (
          <div className="panel-response-text">
            <ReactMarkdown components={mdComponents}>
              {answer}
            </ReactMarkdown>
          </div>
        )}

        {isError && error && (
          <div className="panel-error">⚠ {error}</div>
        )}
      </div>

      {/* ── Attributions ── */}
      {isDone && !isCompact && attributions.length > 0 && (
        <div className="panel-attributions">
          <div className="attributions-label">Sources</div>
          <ul className="attribution-list">
            {attributions.map((attr, i) =>
              attr.url ? (
                <li key={i}>
                  <a
                    href={attr.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="attribution-link"
                  >
                    <span style={{ color: route.color }}>↗</span>
                    {attr.title}
                  </a>
                </li>
              ) : (
                <li key={i}>
                  <span className="attribution-link no-url">{attr.title}</span>
                </li>
              )
            )}
          </ul>
        </div>
      )}
    </div>
  );
}
