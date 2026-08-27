import { useCallback, useEffect, useMemo, useState } from 'react';
import type { Departure, HealthStatus } from '@nypenn/shared';
import { fetchBoard, getToken, setToken, Unauthorized } from './api';
import { loadPins, savePins } from './pins';
import { Login } from './components/Login';
import { TrackCell } from './components/TrackCell';
import { TrainSheet } from './components/TrainSheet';

const REFRESH_MS = 15_000;

export function App() {
  const [token, setTokenState] = useState<string | null>(getToken());
  const [departures, setDepartures] = useState<Departure[] | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [pins, setPins] = useState<string[]>(loadPins);

  const signOut = useCallback(() => {
    setToken(null);
    setTokenState(null);
    setDepartures(null);
  }, []);

  const refresh = useCallback(async () => {
    try {
      const data = await fetchBoard();
      setDepartures(data.departures);
      setHealth(data.health);
      setError(null);
    } catch (err) {
      if (err instanceof Unauthorized) {
        signOut();
        return;
      }
      // Keep showing the last good board rather than blanking the screen —
      // a stale board is still useful, an empty one never is.
      setError('Cannot reach the server.');
    }
  }, [signOut]);

  useEffect(() => {
    if (!token) return;
    void refresh();
    const timer = setInterval(() => void refresh(), REFRESH_MS);

    // Phones suspend timers in the background; refresh on return so the
    // board is never silently minutes out of date when you look at it.
    const onVisible = () => document.visibilityState === 'visible' && void refresh();
    document.addEventListener('visibilitychange', onVisible);

    return () => {
      clearInterval(timer);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [token, refresh]);

  const togglePin = useCallback((trainId: string) => {
    setPins((prev) => {
      const next = prev.includes(trainId)
        ? prev.filter((t) => t !== trainId)
        : [...prev, trainId];
      savePins(next);
      return next;
    });
  }, []);

  // Pinned trains float to the top; everything else stays in departure order.
  const ordered = useMemo(() => {
    if (!departures) return null;
    const pinned = departures.filter((d) => pins.includes(d.trainId));
    const rest = departures.filter((d) => !pins.includes(d.trainId));
    return [...pinned, ...rest];
  }, [departures, pins]);

  if (!token) {
    return (
      <Login
        onSuccess={(t) => {
          setToken(t);
          setTokenState(t);
        }}
      />
    );
  }

  const selectedDeparture = ordered?.find((d) => d.trainId === selected) ?? null;
  const stale = health && !health.ok;

  return (
    <div className="app">
      <header className="bar">
        <h1>NY Penn Departures</h1>
        <span className="muted" onClick={signOut} role="button" tabIndex={0}>
          Sign out
        </span>
      </header>

      {error && <div className="banner error">{error} Showing the last known board.</div>}

      {!error && stale && (
        <div className="banner">
          Collector last updated{' '}
          {health.secondsSinceLastPoll === null
            ? 'never'
            : `${Math.round(health.secondsSinceLastPoll / 60)} min ago`}
          . Tracks and times may be out of date.
        </div>
      )}

      {!ordered ? (
        <div className="empty">Loading the board…</div>
      ) : ordered.length === 0 ? (
        <div className="empty">No departures on the board right now.</div>
      ) : (
        <div className="rows">
          {ordered.map((d) => (
            <button
              key={`${d.trainId}-${d.scheduledDep}`}
              className={`row${pins.includes(d.trainId) ? ' pinned' : ''}`}
              onClick={() => setSelected(d.trainId)}
            >
              <div className="time">
                {formatTime(d.scheduledDep)}
                {d.secondsLate > 60 && (
                  <span className="late">+{Math.round(d.secondsLate / 60)} min</span>
                )}
              </div>
              <div className="dest">
                <div className="name">{d.destination}</div>
                <div className="sub">
                  {d.lineCode || d.line}
                  {d.status && (
                    <>
                      {' · '}
                      <span className={/delay/i.test(d.status) ? 'status-delayed' : ''}>
                        {d.status}
                      </span>
                    </>
                  )}
                </div>
              </div>
              <TrackCell departure={d} />
            </button>
          ))}
        </div>
      )}

      <div className="legend">
        <span><span className="swatch" style={{ color: 'var(--text)', fontStyle: 'normal' }}>4</span> posted</span>
        <span><span className="swatch" style={{ color: 'var(--high)' }}>~4</span> likely</span>
        <span><span className="swatch" style={{ color: 'var(--medium)' }}>~4</span> uncertain</span>
        <span><span className="swatch" style={{ color: 'var(--low)' }}>~4</span> a guess</span>
      </div>

      {selectedDeparture && (
        <TrainSheet
          departure={selectedDeparture}
          pinned={pins.includes(selectedDeparture.trainId)}
          onTogglePin={() => togglePin(selectedDeparture.trainId)}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    timeZone: 'America/New_York',
  });
}
