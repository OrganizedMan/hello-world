import type { WallSegment } from '../types'

// The pane where the reported family-room failure would have been caught
// in five seconds (plan §11): each wall's openings, in order, with the
// TV's solid interval called out explicitly so "window, then solid TV
// wall, then mudroom opening" — versus "a 5' opening on a different
// wall" — is visible at a glance, not something you have to infer.
export function WallInspector({ walls, tvInterval }: { walls: WallSegment[]; tvInterval: { wall_id: string; t_start_nm: number; t_end_nm: number } }) {
  return (
    <div className="panel wall-inspector" data-testid="wall-inspector">
      <h2>Wall inspector</h2>
      {walls.map((wall) => (
        <div key={wall.id} className="wall-block">
          <h3>{wall.id}</h3>
          <p className="wall-meta">
            {wall.construction} · length {wall.length.display} · thickness {wall.thickness.display} · ceiling{' '}
            {wall.top_z.display}
          </p>
          <ol className="opening-sequence">
            {wall.openings.length === 0 && <li className="empty">no openings</li>}
            {wall.openings.map((o) => (
              <li key={o.id} className={`opening-kind-${o.kind}`}>
                <strong>{o.kind}</strong> {o.width.display} ({o.t_start.display} → {o.t_end.display})
                {o.connects && <span className="connects"> → {o.connects[1]}</span>}
              </li>
            ))}
          </ol>
          {wall.id === tvInterval.wall_id && (
            <p className="tv-callout" data-testid="tv-callout">
              60&quot; TV mounts on the solid wall here — never on an opening, on this or any other wall.
            </p>
          )}
        </div>
      ))}
    </div>
  )
}
