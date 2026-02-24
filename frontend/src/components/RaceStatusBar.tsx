import { useState, useEffect } from 'react';
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
  }, [startTime, allDone]);

  useEffect(() => {
    if (allDone && startTime) setElapsed(Date.now() - startTime);
  }, [allDone, startTime]);

  return (
    <div className="race-bar">
      <div className="race-bar-status">
        <div className={`race-bar-dot${allDone ? ' done' : ''}`} />
        {allDone ? 'ALL RESPONSES READY' : 'QUERYING'}
      </div>

      <div className="race-routes">
        {routes.map(({ route, status, latencyMs }, i) => {
          const isDone = status === 'done' || status === 'error';
          const isLoading = status === 'loading';

          let timeDisplay: string;
          if (latencyMs !== null) {
            timeDisplay = `${latencyMs.toLocaleString()}ms`;
          } else if (isLoading) {
            timeDisplay = `${elapsed.toLocaleString()}ms`;
          } else {
            timeDisplay = '—';
          }

          return (
            <span key={route.id} className="qs-route-item">
              {i > 0 && <span className="qs-sep">·</span>}
              <span className="qs-route-name" style={{ color: route.color }}>
                {route.name}
              </span>
              <span className={`qs-route-time${isDone ? (status === 'error' ? ' err' : ' done') : ''}`}>
                {status === 'done' && '✓ '}
                {status === 'error' && '✗ '}
                {timeDisplay}
              </span>
            </span>
          );
        })}
      </div>
    </div>
  );
}
