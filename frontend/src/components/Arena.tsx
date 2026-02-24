import { useState, useCallback } from 'react';
import { ROUTES } from '../routeConfig';
import { sendToRoute, type Attribution } from '../api/copilotApi';
import {
  getUniqueWords,
  jaccardSimilarity,
  buildWordSet,
} from '../utils/diff';
import QueryBar from './QueryBar';
import ResponsePanel, { type PanelStatus } from './ResponsePanel';
import RaceStatusBar from './RaceStatusBar';

type LayoutMode = 'split' | 'stack' | 'focus';

interface RouteState {
  status: PanelStatus;
  answer: string;
  attributions: Attribution[];
  latencyMs: number | null;
  error: string | null;
}

function makeIdleStates(): Record<string, RouteState> {
  return Object.fromEntries(
    ROUTES.map(r => [
      r.id,
      {
        status: 'idle' as PanelStatus,
        answer: '',
        attributions: [],
        latencyMs: null,
        error: null,
      },
    ])
  );
}

export default function Arena() {
  const [query, setQuery] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [routeStates, setRouteStates] =
    useState<Record<string, RouteState>>(makeIdleStates);
  const [hasQueried, setHasQueried] = useState(false);
  const [queryStartTime, setQueryStartTime] = useState<number | null>(null);
  const [layoutMode, setLayoutMode] = useState<LayoutMode>('split');
  const [focusedRouteId, setFocusedRouteId] = useState<string>(
    ROUTES[0]?.id ?? ''
  );

  const handleSubmit = useCallback(async () => {
    const trimmed = query.trim();
    if (!trimmed || isSubmitting) return;

    const startTime = Date.now();
    setIsSubmitting(true);
    setHasQueried(true);
    setQueryStartTime(startTime);
    setRouteStates(
      Object.fromEntries(
        ROUTES.map(r => [
          r.id,
          {
            status: 'loading' as PanelStatus,
            answer: '',
            attributions: [],
            latencyMs: null,
            error: null,
          },
        ])
      )
    );

    await Promise.allSettled(
      ROUTES.map(async route => {
        try {
          const result = await sendToRoute(route.endpoint, {
            question: trimmed,
          });
          setRouteStates(prev => ({
            ...prev,
            [route.id]: {
              status: 'done',
              answer: result.answer,
              attributions: result.attributions,
              latencyMs: Date.now() - startTime,
              error: null,
            },
          }));
        } catch (err) {
          setRouteStates(prev => ({
            ...prev,
            [route.id]: {
              status: 'error',
              answer: '',
              attributions: [],
              latencyMs: Date.now() - startTime,
              error: err instanceof Error ? err.message : 'Unknown error',
            },
          }));
        }
      })
    );

    setIsSubmitting(false);
  }, [query, isSubmitting]);

  const handleNewQuery = useCallback(() => {
    setQuery('');
    setHasQueried(false);
    setQueryStartTime(null);
    setRouteStates(makeIdleStates());
    setIsSubmitting(false);
  }, []);

  // ── Diff computations ──────────────────────────────────────────────────
  const completedRoutes = ROUTES.filter(
    r => routeStates[r.id].status === 'done'
  );

  const uniqueWordSets: Record<string, Set<string>> = {};
  const similarityPairs: { aName: string; bName: string; score: number }[] = [];

  if (completedRoutes.length >= 2) {
    for (const route of completedRoutes) {
      const others = completedRoutes
        .filter(r => r.id !== route.id)
        .map(r => routeStates[r.id].answer);
      uniqueWordSets[route.id] = getUniqueWords(
        routeStates[route.id].answer,
        others
      );
    }

    for (let i = 0; i < completedRoutes.length; i++) {
      for (let j = i + 1; j < completedRoutes.length; j++) {
        const a = completedRoutes[i];
        const b = completedRoutes[j];
        similarityPairs.push({
          aName: a.name,
          bName: b.name,
          score: jaccardSimilarity(
            buildWordSet(routeStates[a.id].answer),
            buildWordSet(routeStates[b.id].answer)
          ),
        });
      }
    }
  }

  const totalCompleted = ROUTES.filter(r => {
    const s = routeStates[r.id].status;
    return s === 'done' || s === 'error';
  }).length;

  const statusRoutes = ROUTES.map(r => ({
    route: r,
    status: routeStates[r.id].status,
    latencyMs: routeStates[r.id].latencyMs,
  }));

  // ── Render ──────────────────────────────────────────────────────────────
  const isFocusMode = layoutMode === 'focus' && ROUTES.length > 1;
  const focusedRoute = ROUTES.find(r => r.id === focusedRouteId) ?? ROUTES[0];
  const sidebarRoutes = ROUTES.filter(r => r.id !== focusedRouteId);

  return (
    <div className="arena">
      {/* ── Top controls ── */}
      <div className="arena-top">
        <QueryBar
          value={query}
          onChange={setQuery}
          onSubmit={handleSubmit}
          isSubmitting={isSubmitting}
          routes={ROUTES}
        />

        {hasQueried && (
          <RaceStatusBar
            routes={statusRoutes}
            startTime={queryStartTime}
            totalCompleted={totalCompleted}
          />
        )}

        <div className="arena-toolbar">
          <div className="toolbar-left">
            {hasQueried && (
              <button
                className="btn btn-ghost btn-sm"
                onClick={handleNewQuery}
              >
                ✕ New Query
              </button>
            )}

            {similarityPairs.length > 0 && (
              <div className="similarity-row">
                <span className="toolbar-label">CONTENT OVERLAP</span>
                {similarityPairs.map(({ aName, bName, score }) => (
                  <div key={`${aName}-${bName}`} className="similarity-item">
                    <span className="similarity-names">
                      {aName} ↔ {bName}
                    </span>
                    <div className="similarity-track">
                      <div
                        className="similarity-fill"
                        style={{ width: `${Math.round(score * 100)}%` }}
                      />
                    </div>
                    <span className="similarity-pct">
                      {Math.round(score * 100)}%
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="toolbar-right">
            <span className="toolbar-label">VIEW</span>
            {(['split', 'stack', 'focus'] as LayoutMode[]).map(mode => (
              <button
                key={mode}
                className={`mode-btn${layoutMode === mode ? ' active' : ''}`}
                onClick={() => setLayoutMode(mode)}
                disabled={mode === 'focus' && ROUTES.length <= 1}
                title={
                  mode === 'split' ? 'Side by side' :
                  mode === 'stack' ? 'Stacked' :
                  'Focus one panel'
                }
              >
                {mode === 'split' ? '⊞' : mode === 'stack' ? '☰' : '⊡'}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* ── Body ── */}
      <div className="arena-body">
        {!hasQueried ? (
          /* ── Welcome / explain screen ── */
          <div className="arena-welcome">
            <div className="welcome-title">
              Compare <span>M365 APIs</span>
            </div>
            <div className="welcome-sub">
              One question — three APIs respond in parallel — see exactly what
              each one returns and how the content differs
            </div>

            <div className="welcome-api-cards">
              {ROUTES.map(r => (
                <div
                  key={r.id}
                  className="welcome-api-card"
                  style={{ borderColor: `${r.color}33` }}
                >
                  <div className="wac-header">
                    <div className="wac-dot" style={{ background: r.color }} />
                    <span className="wac-name" style={{ color: r.color }}>
                      {r.name}
                    </span>
                  </div>
                  <div className="wac-label">{r.label}</div>
                  <div className="wac-desc">{r.description}</div>
                  <div className="wac-sources-label">Data sources</div>
                  <div className="wac-sources">
                    {r.dataSources.map(src => (
                      <span
                        key={src}
                        className="wac-source-tag"
                        style={{ borderColor: `${r.color}30`, color: r.color }}
                      >
                        {src}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            <div className="welcome-hint">
              Type a question above and press Enter to compare
            </div>
          </div>
        ) : isFocusMode ? (
          /* ── Focus layout ── */
          <div className="focus-layout">
            <div className="focus-main">
              <ResponsePanel
                route={focusedRoute}
                status={routeStates[focusedRoute.id].status}
                answer={routeStates[focusedRoute.id].answer}
                attributions={routeStates[focusedRoute.id].attributions}
                latencyMs={routeStates[focusedRoute.id].latencyMs}
                error={routeStates[focusedRoute.id].error}
                uniqueWords={uniqueWordSets[focusedRoute.id] ?? new Set()}
              />
            </div>
            <div className="focus-sidebar">
              {sidebarRoutes.map(route => (
                <ResponsePanel
                  key={route.id}
                  route={route}
                  status={routeStates[route.id].status}
                  answer={routeStates[route.id].answer}
                  attributions={routeStates[route.id].attributions}
                  latencyMs={routeStates[route.id].latencyMs}
                  error={routeStates[route.id].error}
                  uniqueWords={uniqueWordSets[route.id] ?? new Set()}
                  isCompact
                  onFocus={() => setFocusedRouteId(route.id)}
                />
              ))}
            </div>
          </div>
        ) : (
          /* ── Split / Stack layout ── */
          <div
            className={`response-grid${layoutMode === 'stack' ? ' layout-stack' : ''}`}
          >
            {ROUTES.map(route => (
              <ResponsePanel
                key={route.id}
                route={route}
                status={routeStates[route.id].status}
                answer={routeStates[route.id].answer}
                attributions={routeStates[route.id].attributions}
                latencyMs={routeStates[route.id].latencyMs}
                error={routeStates[route.id].error}
                uniqueWords={uniqueWordSets[route.id] ?? new Set()}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
