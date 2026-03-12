import { useCallback, useEffect, useState } from 'react';
import { ROUTES } from '../routeConfig';
import { sendToRoute, type Attribution } from '../api/copilotApi';
import {
  buildWordSet,
  getUniqueWords,
  jaccardSimilarity,
} from '../utils/diff';
import QueryBar from './QueryBar';
import ResponsePanel, { type PanelStatus } from './ResponsePanel';
import RaceStatusBar from './RaceStatusBar';

type LayoutMode = 'split' | 'stack' | 'focus';

const LAYOUT_OPTIONS: { id: LayoutMode; label: string }[] = [
  { id: 'split', label: 'Grid' },
  { id: 'stack', label: 'Stack' },
  { id: 'focus', label: 'Focus' },
];

interface RouteState {
  status: PanelStatus;
  answer: string;
  attributions: Attribution[];
  latencyMs: number | null;
  error: string | null;
}

function makeIdleStates(): Record<string, RouteState> {
  return Object.fromEntries(
    ROUTES.map(route => [
      route.id,
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
  const [submittedQuery, setSubmittedQuery] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [selectedRouteIds, setSelectedRouteIds] = useState<string[]>(
    ROUTES.map(route => route.id)
  );
  const [routeStates, setRouteStates] =
    useState<Record<string, RouteState>>(makeIdleStates);
  const [hasQueried, setHasQueried] = useState(false);
  const [queryStartTime, setQueryStartTime] = useState<number | null>(null);
  const [layoutMode, setLayoutMode] = useState<LayoutMode>('split');
  const [focusedRouteId, setFocusedRouteId] = useState<string>(
    ROUTES[0]?.id ?? ''
  );
  const activeRoutes = ROUTES.filter(route => selectedRouteIds.includes(route.id));

  useEffect(() => {
    if (activeRoutes.some(route => route.id === focusedRouteId)) return;
    setFocusedRouteId(activeRoutes[0]?.id ?? '');
  }, [activeRoutes, focusedRouteId]);

  const resetComparison = useCallback(() => {
    setSubmittedQuery('');
    setHasQueried(false);
    setQueryStartTime(null);
    setRouteStates(makeIdleStates());
    setIsSubmitting(false);
  }, []);

  const handleToggleRoute = useCallback(
    (routeId: string) => {
      if (isSubmitting) return;

      setSelectedRouteIds(prev => {
        const isSelected = prev.includes(routeId);
        if (isSelected && prev.length === 1) return prev;

        const nextIds = isSelected
          ? prev.filter(id => id !== routeId)
          : ROUTES.filter(route => prev.includes(route.id) || route.id === routeId).map(
              route => route.id
            );

        return nextIds;
      });

      resetComparison();
    },
    [isSubmitting, resetComparison]
  );

  const handleSubmit = useCallback(async () => {
    const trimmed = query.trim();
    if (!trimmed || isSubmitting || activeRoutes.length === 0) return;

    const startTime = Date.now();
    setIsSubmitting(true);
    setHasQueried(true);
    setSubmittedQuery(trimmed);
    setQueryStartTime(startTime);
    setFocusedRouteId(activeRoutes[0]?.id ?? '');
    setRouteStates(
      Object.fromEntries(
        ROUTES.map(route => [
          route.id,
          {
            status: activeRoutes.some(activeRoute => activeRoute.id === route.id)
              ? ('loading' as PanelStatus)
              : ('idle' as PanelStatus),
            answer: '',
            attributions: [],
            latencyMs: null,
            error: null,
          },
        ])
      )
    );

    await Promise.allSettled(
      activeRoutes.map(async route => {
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
  }, [activeRoutes, isSubmitting, query]);

  const handleClearResults = useCallback(() => {
    setQuery('');
    resetComparison();
  }, [resetComparison]);

  const completedRoutes = activeRoutes.filter(
    route => routeStates[route.id].status === 'done'
  );

  const uniqueWordSets: Record<string, Set<string>> = {};
  const similarityPairs: { aName: string; bName: string; score: number }[] = [];

  if (completedRoutes.length >= 2) {
    for (const route of completedRoutes) {
      const others = completedRoutes
        .filter(otherRoute => otherRoute.id !== route.id)
        .map(otherRoute => routeStates[otherRoute.id].answer);
      uniqueWordSets[route.id] = getUniqueWords(
        routeStates[route.id].answer,
        others
      );
    }

    for (let i = 0; i < completedRoutes.length; i++) {
      for (let j = i + 1; j < completedRoutes.length; j++) {
        const routeA = completedRoutes[i];
        const routeB = completedRoutes[j];
        similarityPairs.push({
          aName: routeA.name,
          bName: routeB.name,
          score: jaccardSimilarity(
            buildWordSet(routeStates[routeA.id].answer),
            buildWordSet(routeStates[routeB.id].answer)
          ),
        });
      }
    }
  }

  const totalCompleted = activeRoutes.filter(route => {
    const status = routeStates[route.id].status;
    return status === 'done' || status === 'error';
  }).length;
  const successfulCount = activeRoutes.filter(
    route => routeStates[route.id].status === 'done'
  ).length;
  const errorCount = activeRoutes.filter(
    route => routeStates[route.id].status === 'error'
  ).length;

  const statusRoutes = activeRoutes.map(route => ({
    route,
    status: routeStates[route.id].status,
    latencyMs: routeStates[route.id].latencyMs,
  }));

  const isFocusMode = layoutMode === 'focus' && activeRoutes.length > 1;
  const focusedRoute = activeRoutes.find(route => route.id === focusedRouteId) ?? activeRoutes[0];
  const sidebarRoutes = activeRoutes.filter(route => route.id !== focusedRouteId);

  return (
    <div className="arena-shell">
      <aside className="arena-sidebar">
        <section className="sidebar-section">
          <div className="sidebar-section-header">
            <span className="sidebar-section-title">Selected endpoints</span>
            <span className="sidebar-section-value">{activeRoutes.length}</span>
          </div>

          <div className="route-directory">
            {activeRoutes.map(route => {
              const state = routeStates[route.id];

              return (
                <button
                  key={route.id}
                  type="button"
                  className={`route-directory-item${focusedRouteId === route.id ? ' active' : ''}`}
                  onClick={() => setFocusedRouteId(route.id)}
                >
                  <div className="route-directory-top">
                    <span
                      className="route-directory-swatch"
                      style={{ background: route.color }}
                    />
                    <span
                      className="route-directory-name"
                      style={{ color: route.color }}
                    >
                      {route.name}
                    </span>
                    <span className={`route-directory-state state-${state.status}`}>
                      {state.status}
                    </span>
                  </div>
                  <div className="route-directory-label">{route.label}</div>
                  <div className="route-directory-meta">
                    <span>{route.method}</span>
                    <span>{route.dataSources.length} sources</span>
                    <span>
                      {state.latencyMs !== null
                        ? `${state.latencyMs.toLocaleString()}ms`
                        : 'waiting'}
                    </span>
                  </div>
                </button>
              );
            })}
          </div>
        </section>

        <section className="sidebar-section">
          <div className="sidebar-section-header">
            <span className="sidebar-section-title">Comparison</span>
            <span className="sidebar-section-value">
              {hasQueried ? `${totalCompleted}/${activeRoutes.length}` : 'idle'}
            </span>
          </div>

          {!hasQueried ? (
            <div className="sidebar-note">
              Submit one prompt to measure latency, inspect source attributions,
              and highlight endpoint-specific terms in each answer.
            </div>
          ) : (
            <>
              <div className="prompt-preview">{submittedQuery}</div>

              <div className="comparison-stats">
                <div className="comparison-stat">
                  <span className="comparison-stat-label">Completed</span>
                  <span className="comparison-stat-value">{totalCompleted}</span>
                </div>
                <div className="comparison-stat">
                  <span className="comparison-stat-label">Successful</span>
                  <span className="comparison-stat-value">{successfulCount}</span>
                </div>
                <div className="comparison-stat">
                  <span className="comparison-stat-label">Errors</span>
                  <span className="comparison-stat-value">{errorCount}</span>
                </div>
              </div>

              {similarityPairs.length > 0 ? (
                <div className="overlap-list">
                  {similarityPairs.map(({ aName, bName, score }) => (
                    <div key={`${aName}-${bName}`} className="overlap-item">
                      <div className="overlap-item-copy">
                        <span>{aName}</span>
                        <span>{bName}</span>
                      </div>
                      <div className="overlap-track">
                        <div
                          className="overlap-fill"
                          style={{ width: `${Math.round(score * 100)}%` }}
                        />
                      </div>
                      <span className="overlap-value">
                        {Math.round(score * 100)}%
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="sidebar-note">
                  Overlap appears once at least two endpoints finish successfully.
                </div>
              )}
            </>
          )}
        </section>
      </aside>

      <section className="arena-stage">
        <div className="stage-toolbar">
          <div className="stage-toolbar-copy">
            <span className="stage-toolbar-title">Workspace</span>
            <span className="stage-toolbar-meta">
              {hasQueried
                ? `${totalCompleted} of ${activeRoutes.length} endpoints have returned`
                : 'Choose one or more endpoints, then run the same prompt in parallel'}
            </span>
          </div>

          <div className="stage-toolbar-actions">
            {hasQueried && (
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={handleClearResults}
              >
                Clear results
              </button>
            )}

            <div className="view-switch" role="tablist" aria-label="Layout mode">
              {LAYOUT_OPTIONS.map(option => (
                <button
                  key={option.id}
                  type="button"
                  role="tab"
                  aria-selected={layoutMode === option.id}
                  className={`view-switch-btn${layoutMode === option.id ? ' active' : ''}`}
                  onClick={() => setLayoutMode(option.id)}
                  disabled={option.id === 'focus' && activeRoutes.length <= 1}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        <QueryBar
          value={query}
          onChange={setQuery}
          onSubmit={handleSubmit}
          onToggleRoute={handleToggleRoute}
          isSubmitting={isSubmitting}
          routes={ROUTES}
          selectedRouteIds={selectedRouteIds}
        />

        {hasQueried && activeRoutes.length > 0 ? (
          <RaceStatusBar
            routes={statusRoutes}
            startTime={queryStartTime}
            totalCompleted={totalCompleted}
          />
        ) : null}

        <div className="stage-results">
          {!hasQueried ? (
            <div className="arena-welcome">
              <div className="welcome-panel welcome-panel-manifest">
                <div className="welcome-section-title">Endpoint manifest</div>
                <div className="manifest-table">
                  {activeRoutes.map(route => (
                    <div key={route.id} className="manifest-row">
                      <div className="manifest-cell manifest-cell-route">
                        <span
                          className="manifest-swatch"
                          style={{ background: route.color }}
                        />
                        <div className="manifest-route-copy">
                          <span
                            className="manifest-route-name"
                            style={{ color: route.color }}
                          >
                            {route.name}
                          </span>
                          <span className="manifest-route-label">
                            {route.label}
                          </span>
                        </div>
                      </div>
                      <div className="manifest-cell">{route.method}</div>
                      <div className="manifest-cell manifest-cell-sources">
                        {route.dataSources.join(', ')}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="welcome-panel welcome-panel-notes">
                <div className="welcome-section-title">Workspace notes</div>
                <div className="note-list">
                  <div className="note-item">
                    Pick one, two, or all three endpoints before you run the prompt.
                  </div>
                  <div className="note-item">
                    Use grid view to compare selected endpoints, or switch to
                    focus when you need a single reading surface.
                  </div>
                  <div className="note-item">
                    Source links appear below each completed response when the
                    backend returns them.
                  </div>
                </div>
              </div>
            </div>
          ) : isFocusMode ? (
            <div className="focus-layout">
              <div className="focus-main">
                {focusedRoute && (
                  <ResponsePanel
                    route={focusedRoute}
                    status={routeStates[focusedRoute.id].status}
                    answer={routeStates[focusedRoute.id].answer}
                    attributions={routeStates[focusedRoute.id].attributions}
                    latencyMs={routeStates[focusedRoute.id].latencyMs}
                    error={routeStates[focusedRoute.id].error}
                    uniqueWords={uniqueWordSets[focusedRoute.id] ?? new Set()}
                  />
                )}
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
            <div
              className={`response-grid response-grid-count-${activeRoutes.length}${layoutMode === 'stack' ? ' layout-stack' : ''}`}
            >
              {activeRoutes.map(route => (
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
      </section>
    </div>
  );
}
