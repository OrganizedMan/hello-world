import { useState } from 'react'
import { api } from '../api'
import type { TiersResponse } from '../types'

const TIER_LABEL: Record<string, string> = { A: 'Tier A — vector', B: 'Tier B — flat vector', C: 'Tier C — raster' }

export function SourcePanel({ tiers }: { tiers: TiersResponse | null }) {
  const [selected, setSelected] = useState<'a1' | 'degraded'>('a1')

  return (
    <div className="panel source-panel" data-testid="source-panel">
      <h2>Source document</h2>
      <div className="tier-toggle">
        <button className={selected === 'a1' ? 'active' : ''} onClick={() => setSelected('a1')}>
          Sheet A-1 (native)
        </button>
        <button className={selected === 'degraded' ? 'active' : ''} onClick={() => setSelected('degraded')}>
          150 DPI scan (degraded)
        </button>
      </div>
      {tiers && (
        <p className="tier-badge" data-testid={`tier-badge-${selected}`}>
          {TIER_LABEL[tiers[selected].tier]} — {tiers[selected].effort_estimate}
        </p>
      )}
      <img
        className="source-image"
        src={api.sourceImageUrl(selected)}
        alt={`Garrigan sheet A-1 (${selected})`}
        data-testid="source-image"
      />
    </div>
  )
}
