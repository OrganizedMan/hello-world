import { useEffect, useState } from 'react'
import './App.css'
import { api } from './api'
import { SourcePanel } from './components/SourcePanel'
import { ThreeViewer } from './components/ThreeViewer'
import { ValidationPanel } from './components/ValidationPanel'
import { WallInspector } from './components/WallInspector'
import type { FamilyRoomMeshResponse, FamilyRoomResponse, FamilyRoomSource, TiersResponse } from './types'

const SOURCES: { value: FamilyRoomSource; label: string }[] = [
  { value: 'hand_traced', label: 'Hand-traced (Stage 0)' },
  { value: 'extracted', label: 'Extracted from PDF (Stage 1)' },
]

export default function App() {
  const [source, setSource] = useState<FamilyRoomSource>('hand_traced')
  const [room, setRoom] = useState<FamilyRoomResponse | null>(null)
  const [mesh, setMesh] = useState<FamilyRoomMeshResponse | null>(null)
  const [tiers, setTiers] = useState<TiersResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setRoom(null)
    setMesh(null)
    Promise.all([api.familyRoom(source), api.familyRoomMesh(source), api.tiers()])
      .then(([r, m, t]) => {
        setRoom(r)
        setMesh(m)
        setTiers(t)
      })
      .catch((e: Error) => setError(e.message))
  }, [source])

  if (error) {
    return (
      <div className="app-error" data-testid="app-error">
        <h1>Could not reach the local API</h1>
        <p>{error}</p>
        <p>Is the FastAPI server running? (uvicorn server:app --app-dir packages/server/src)</p>
      </div>
    )
  }

  if (!room || !mesh) {
    return (
      <div className="app-loading" data-testid="app-loading">
        Loading the Garrigan family room…
      </div>
    )
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>261 Grove Street — Family Room</h1>
        <p className="subtitle">
          PDF → deterministic 3D model. Every camera on this model reads the same geometry —{' '}
          <code>{room.geometry_hash.slice(0, 12)}</code>.
        </p>
        <div className="source-toggle" data-testid="source-toggle">
          {SOURCES.map((s) => (
            <button
              key={s.value}
              className={s.value === source ? 'active' : ''}
              data-testid={`source-toggle-${s.value}`}
              onClick={() => setSource(s.value)}
            >
              {s.label}
            </button>
          ))}
          {source === 'extracted' && (
            <span className="unreviewed-badge" data-testid="unreviewed-badge">
              unreviewed proposal — not yet approved by a human
            </span>
          )}
        </div>
      </header>
      <main className="app-grid">
        <SourcePanel tiers={tiers} />
        <div className="panel viewer-panel">
          <h2>Deterministic 3D model</h2>
          <ThreeViewer mesh={mesh} fixtureIds={room.fixtures?.map((f) => f.id)} />
        </div>
        <WallInspector
          walls={room.walls}
          tvInterval={room.tv_wall_interval}
          dimensionMatches={room.dimension_matches}
          fixtures={room.fixtures}
        />
        <ValidationPanel report={room.validation} geometryHash={room.geometry_hash} />
      </main>
    </div>
  )
}
