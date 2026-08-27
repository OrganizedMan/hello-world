import { useEffect, useState } from 'react';
import type { Departure } from '@nypenn/shared';
import { fetchTrainHistory, type TrainHistoryEntry } from '../api';

const SOURCE_LABEL: Record<string, string> = {
  'train-history': "this train's own past runs",
  'line-history': 'other trains on this line',
  'line-prior': 'a default for this line, with no history yet',
};

/**
 * Detail panel: why the board is saying what it is saying.
 *
 * Showing the raw past assignments is the honest version of a confidence
 * score — it lets you overrule a shaky prediction yourself.
 */
export function TrainSheet({
  departure,
  pinned,
  onTogglePin,
  onClose,
}: {
  departure: Departure;
  pinned: boolean;
  onTogglePin: () => void;
  onClose: () => void;
}) {
  const [history, setHistory] = useState<TrainHistoryEntry[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    fetchTrainHistory(departure.trainId)
      .then((r) => active && setHistory(r.history))
      .catch(() => active && setFailed(true));
    return () => {
      active = false;
    };
  }, [departure.trainId]);

  const p = departure.prediction;

  return (
    <div className="sheet-backdrop" onClick={onClose} role="presentation">
      <div
        className="sheet"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={`Train ${departure.trainId} to ${departure.destination}`}
      >
        <h2>
          {departure.destination} · {formatTime(departure.scheduledDep)}
        </h2>
        <div className="muted">
          Train {departure.trainId} · {departure.line}
        </div>

        {departure.track ? (
          <div className="section">
            <h3>Track</h3>
            <div>
              Track {departure.track}, posted by NJ Transit.
            </div>
          </div>
        ) : p ? (
          <div className="section">
            <h3>Prediction</h3>
            <div>
              Track <strong>{p.track}</strong> — {p.confidence} confidence, from{' '}
              {SOURCE_LABEL[p.source] ?? p.source}
              {p.sampleSize > 0 && ` (${p.sampleSize} past run${p.sampleSize === 1 ? '' : 's'})`}.
            </div>
            <div className="muted" style={{ marginTop: 6 }}>
              NJ Transit has not posted this track yet. Confirm on the board before you walk.
            </div>
          </div>
        ) : (
          <div className="section">
            <h3>Prediction</h3>
            <div className="muted">
              Not enough history for this train yet. It builds up over the coming weeks.
            </div>
          </div>
        )}

        <div className="section">
          <h3>Recent tracks</h3>
          {failed ? (
            <div className="muted">Could not load history.</div>
          ) : !history ? (
            <div className="muted">Loading…</div>
          ) : history.length === 0 ? (
            <div className="muted">No past runs recorded yet.</div>
          ) : (
            <div className="history">
              {history.map((h) => (
                <div className="chip" key={h.serviceDate}>
                  <span className="date">{formatDate(h.serviceDate)}</span>
                  {h.finalTrack}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="section">
          <button className="action" onClick={onTogglePin}>
            {pinned ? 'Unpin this train' : 'Pin to the top'}
          </button>
        </div>
      </div>
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

function formatDate(serviceDate: string): string {
  return new Date(`${serviceDate}T12:00:00Z`).toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'numeric',
    day: 'numeric',
    timeZone: 'UTC',
  });
}
