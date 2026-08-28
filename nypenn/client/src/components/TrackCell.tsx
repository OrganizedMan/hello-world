import type { Departure } from '@nypenn/shared';

/**
 * The track cell — the reason this app exists.
 *
 * A posted track and a predicted one must never be mistakable for each other:
 * being sent confidently to the wrong end of Penn is worse than being told
 * nothing. So a prediction differs by colour, italics, and a "~" prefix, and
 * says PREDICTED underneath. Three redundant signals, because colour alone
 * fails in sunlight and for colour-blind readers.
 */
export function TrackCell({ departure }: { departure: Departure }) {
  if (departure.track) {
    return (
      <div className="track posted">
        <div className="value">{departure.track}</div>
        <div className="label">Track</div>
      </div>
    );
  }

  const p = departure.prediction;
  if (!p) {
    return (
      <div className="track unknown">
        <div className="value">—</div>
        <div className="label">Not posted</div>
      </div>
    );
  }

  return (
    <div className={`track predicted ${p.confidence}`}>
      <div className="value">{p.track}</div>
      <div className="label">Predicted</div>
    </div>
  );
}
