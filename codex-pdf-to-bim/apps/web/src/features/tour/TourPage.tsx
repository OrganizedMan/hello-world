import { useCallback, useEffect, useState } from "react";

import { HelpTooltip } from "../../components/HelpTooltip";
import { TourOrientationMap } from "./TourOrientationMap";
import { TourViewer, type TourMode, type TourPresetName } from "./TourViewer";
import { parseTourManifest, type TourManifest } from "./tourManifest";

export { parseTourManifest, type TourManifest } from "./tourManifest";


const modeDescriptions: Record<TourMode, string> = {
  orbit: "Orbit mode · Drag to look around and scroll to zoom.",
  move: "Move here mode · Select a clear spot on the floor.",
  walk: "Walk mode · Use the movement keys and look around at person height.",
};


type TourPageProps = {
  /** Public folder holding manifest.json and the artifacts it names. */
  basePath?: string;
};


export function TourPage({ basePath = "/tour-spike" }: TourPageProps = {}) {
  const [attempt, setAttempt] = useState(0);
  const [manifest, setManifest] = useState<TourManifest | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [sceneReady, setSceneReady] = useState(false);
  const [mode, setMode] = useState<TourMode>("orbit");
  const [preset, setPreset] = useState<TourPresetName>("kitchen_overview");
  const [viewRevision, setViewRevision] = useState(0);
  const [activeStorey, setActiveStorey] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setManifest(null);
    setLoadError(false);
    setSceneReady(false);

    async function loadManifest() {
      try {
        const response = await fetch(`${basePath}/manifest.json`, { signal: controller.signal });
        if (!response.ok) throw new Error(`manifest request failed: ${response.status}`);
        const nextManifest = parseTourManifest(await response.json());
        if (!controller.signal.aborted) setManifest(nextManifest);
      } catch (error) {
        if (!controller.signal.aborted) setLoadError(true);
      }
    }

    void loadManifest();
    return () => controller.abort();
  }, [attempt, basePath]);

  const showPreset = useCallback((nextPreset: TourPresetName) => {
    setMode("orbit");
    setPreset(nextPreset);
    setViewRevision((current) => current + 1);
  }, []);

  if (loadError) {
    return (
      <main className="tour-page tour-page--message">
        <section className="tour-error" role="alert">
          <p className="eyebrow">Local tour unavailable</p>
          <h1>The room could not be opened</h1>
          <p>The tour files may be missing or incomplete. Your plans and project work are still safe.</p>
          <button className="button button--primary" type="button" onClick={() => setAttempt((current) => current + 1)}>
            Try again
          </button>
        </section>
      </main>
    );
  }

  if (!manifest) {
    return (
      <main className="tour-page tour-page--message">
        <section className="tour-loading" role="status">
          <span className="tour-loading__mark" aria-hidden="true">H</span>
          <h1>Preparing your room…</h1>
          <p>Opening the detailed tour from this Mac.</p>
          <progress aria-label="Room loading progress" max="100" value="0">0%</progress>
        </section>
      </main>
    );
  }

  const traced = manifest.schema === "hearthview-tour/v2";
  // Only the traced manifest carries storeys, and only when more than one is
  // drawn; the kitchen tour has none and shows no switcher.
  const storeys = manifest.schema === "hearthview-tour/v2" ? manifest.storeys ?? [] : [];

  return (
    <main className="tour-page">
      <header className="tour-header">
        <div>
          <p className="eyebrow">{traced ? "Traced from A-1" : "Unapproved prototype"}</p>
          <h1>
            {storeys.length > 1
              ? "Walk the proposed house"
              : traced
                ? "Walk the proposed first floor"
                : "Explore the proposed kitchen and family room"}
          </h1>
          <p>
            {storeys.length > 1
              ? `Every wall, opening and room position across ${storeys.length} drawn storeys is lifted from the proposed-plan linework.`
              : traced
                ? "Every wall, opening and room position here is lifted from the A-1 proposed-plan linework."
                : "Compare the full A-1 trace before relying on this experimental room tour."}
          </p>
        </div>
        <aside className="tour-trust-note" aria-label="Tour trust note">
          <strong>{manifest.label}</strong>
          {traced ? (
            <>
              <span>
                {manifest.provenance.verified_percent}% of the solids stand on a dimension read from the
                drawing: wall footprints and thicknesses, opening positions and widths, and the printed
                ceiling height.
              </span>
              <span>{manifest.provenance.absent_from_drawing_set}</span>
              <span>
                Assumed instead: {manifest.provenance.assumed.join("; ")}. Finishes and lighting are
                presentation, not measured detail.
              </span>
            </>
          ) : (
            <>
              <span>Unapproved prototype: its geometry must not be treated as A-1 accurate until the 2D trace review is approved.</span>
              <span>Furniture, décor, and finishes are provisional visual choices—not measured construction details.</span>
            </>
          )}
        </aside>
      </header>

      <section className="tour-workspace" aria-label="Interactive room tour">
        <div className="tour-stage">
          <TourViewer
            basePath={basePath}
            visibleStoreys={activeStorey ? [activeStorey] : []}
            manifest={manifest}
            mode={mode}
            preset={preset}
            viewRevision={viewRevision}
            onModeChange={setMode}
            onReady={() => {
              setSceneReady(true);
            }}
            onLoadError={() => setLoadError(true)}
          />
          {!sceneReady ? (
            <div className="tour-stage__loading" role="status">
              <strong>Opening the detailed room…</strong>
              <span>Loading the local scene</span>
              <progress aria-label="Room loading progress">Loading</progress>
            </div>
          ) : null}
          <div className="tour-mode-status" role="status" aria-label="Tour mode" aria-live="polite">
            {modeDescriptions[mode]}
          </div>
        </div>

        <aside className="tour-panel" aria-label="Tour controls and help">
          {storeys.length > 1 ? (
            <div className="tour-storeys">
              <span className="tour-storeys__label">Floor</span>
              <div className="tour-storeys__buttons">
                <button
                  type="button"
                  className="tour-storey"
                  aria-pressed={activeStorey === null}
                  onClick={() => setActiveStorey(null)}
                >
                  Whole house
                </button>
                {storeys.map((storey) => (
                  <button
                    key={storey.node}
                    type="button"
                    className="tour-storey"
                    aria-pressed={activeStorey === storey.node}
                    onClick={() => setActiveStorey(storey.node)}
                  >
                    {storey.name}
                    <span className="tour-storey__sheet">{storey.sheet}</span>
                  </button>
                ))}
              </div>
            </div>
          ) : null}
          <div className="tour-panel__heading">
            <div>
              <span>Choose how to explore</span>
              <h2>Room controls</h2>
            </div>
            <HelpTooltip label="How the room controls work">
              Orbit for a wide look, Move here to choose a floor spot, or Walk to explore at person height.
            </HelpTooltip>
          </div>

          <div className="tour-controls" aria-label="View controls">
            <button type="button" aria-label="Orbit" className={mode === "orbit" ? "is-active" : ""} onClick={() => setMode("orbit")} aria-pressed={mode === "orbit"}>
              <span aria-hidden="true">↻</span><strong>Orbit</strong><small>Look around freely</small>
            </button>
            <button type="button" aria-label="Move here" className={mode === "move" ? "is-active" : ""} onClick={() => setMode("move")} aria-pressed={mode === "move"}>
              <span aria-hidden="true">⌖</span><strong>Move here</strong><small>Choose a clear floor spot</small>
            </button>
            <button type="button" aria-label="Walk" className={mode === "walk" ? "is-active" : ""} onClick={() => setMode("walk")} aria-pressed={mode === "walk"}>
              <span aria-hidden="true">↑</span><strong>Walk</strong><small>Explore at person height</small>
            </button>
            <button type="button" aria-label="Overhead" onClick={() => showPreset("overhead")}>
              <span aria-hidden="true">⌂</span><strong>Overhead</strong><small>See the whole room</small>
            </button>
            <button type="button" aria-label="Reset" onClick={() => showPreset("kitchen_overview")}>
              <span aria-hidden="true">↺</span><strong>Reset</strong><small>Return to the kitchen view</small>
            </button>
            {mode === "walk" ? (
              <button type="button" aria-label="Exit walk" className="tour-controls__exit" onClick={() => setMode("orbit")}>
                <span aria-hidden="true">×</span><strong>Exit walk</strong><small>Return to orbit safely</small>
              </button>
            ) : null}
          </div>

          <div className="tour-guide">
            <strong>While walking</strong>
            <p>Use <kbd>WASD</kbd> or arrow keys to move. Use the mouse or drag to look. Press <kbd>Esc</kbd> or choose Exit walk at any time.</p>
          </div>

          <div className="tour-orientation" aria-label="Room orientation map">
            <div className="tour-orientation__heading"><strong>Room orientation</strong><span>N</span></div>
            <TourOrientationMap orientation={manifest.orientation} island={manifest.island_footprint} />
          </div>

          <p className="tour-local-note"><span aria-hidden="true">◆</span> This detailed room stays on this Mac after the assets are prepared.</p>
        </aside>
      </section>
    </main>
  );
}
