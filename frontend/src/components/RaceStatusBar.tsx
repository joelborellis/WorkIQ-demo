import { useEffect, useState } from 'react';
import type { RouteConfig } from '../routeConfig';
import type { PanelStatus } from './ResponsePanel';

interface RouteStatusInfo {
  route: RouteConfig;
  status: PanelStatus;
  latencyMs: number | null;
}

interface RaceStatusBarProps {
  routes: RouteStatusInfo[];
  startTime: number | null;
  totalCompleted: number;
}

export default function RaceStatusBar({
  routes,
  startTime,
  totalCompleted,
}: RaceStatusBarProps) {
  const [elapsed, setElapsed] = useState(0);
  const allDone = totalCompleted === routes.length;

  useEffect(() => {
    if (!startTime || allDone) return;
    const id = setInterval(() => setElapsed(Date.now() - startTime), 50);
    return () => clearInterval(id);
  }, [allDone, startTime]);

  useEffect(() => {
    if (allDone && startTime) setElapsed(Date.now() - startTime);
  }, [allDone, startTime]);

  return (
    <div className="race-bar">
      <div
        className="race-bar-progress"
        aria-hidden="true"
        style={{ gridTemplateColumns: `repeat(${Math.max(routes.length, 1)}, minmax(0, 1fr))` }}
      >
        {routes.map(({ route, status }) => (
          <span
            key={route.id}
            className={`race-bar-segment status-${status}`}
            style={{ background: route.color }}
          />
        ))}
      </div>

      <div className="race-bar-body">
        <div className="race-bar-status">
          <div className={`race-bar-dot${allDone ? ' done' : ''}`} />
          <div className="race-bar-copy">
            <span className="race-bar-title">
              {allDone ? 'Comparison ready' : 'Running comparison'}
            </span>
            <span className="race-bar-meta">
              {totalCompleted} of {routes.length} endpoints finished
            </span>
          </div>
        </div>

        <div className="race-routes">
          {routes.map(({ route, status, latencyMs }) => {
            const isDone = status === 'done' || status === 'error';
            const isLoading = status === 'loading';

            let timeDisplay = '—';
            if (latencyMs !== null) {
              timeDisplay = `${latencyMs.toLocaleString()}ms`;
            } else if (isLoading) {
              timeDisplay = `${elapsed.toLocaleString()}ms`;
            }

            return (
              <span key={route.id} className={`qs-route-item state-${status}`}>
                <span className="qs-route-name" style={{ color: route.color }}>
                  {route.name}
                </span>
                <span
                  className={`qs-route-time${isDone ? (status === 'error' ? ' err' : ' done') : ''}`}
                >
                  {status === 'done' && '✓ '}
                  {status === 'error' && '✗ '}
                  {timeDisplay}
                </span>
              </span>
            );
          })}
        </div>
      </div>
    </div>
  );
}
