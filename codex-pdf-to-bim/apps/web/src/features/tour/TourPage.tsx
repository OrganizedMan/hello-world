import { useCallback, useEffect, useState } from "react";
import { z } from "zod";

import { HelpTooltip } from "../../components/HelpTooltip";
import { TourViewer, type TourMode, type TourPresetName } from "./TourViewer";


const vector3Schema = z.tuple([z.number().finite(), z.number().finite(), z.number().finite()]);
const cameraPresetSchema = z.object({
  name: z.enum(["kitchen_overview", "walk_start", "overhead"]),
  position: vector3Schema,
  target: vector3Schema,
});

const manifestSchema = z.object({
  schema: z.literal("hearthview-tour-spike/v1"),
  label: z.literal("Quality spike · visual staging"),
  canonical_geometry: z.literal(false),
  provisional_categories: z.array(z.string()).superRefine((categories, context) => {
    for (const required of ["cabinetry_detail", "hardware", "finishes", "furniture", "decor", "undimensioned_offsets"]) {
      if (!categories.includes(required)) {
        context.addIssue({ code: "custom", message: `missing provisional category: ${required}` });
      }
    }
  }),
  artifact: z.object({
    glb: z.literal("hearthview-kitchen-family.glb"),
    poster: z.literal("poster.webp"),
    environment: z.literal("environment.hdr"),
    total_browser_bytes: z.number().int().positive().max(45_000_000),
  }),
  runtime: z.object({
    eye_height_meters: z.literal(1.65),
    walkable: z.object({
      min_x: z.number().finite(),
      max_x: z.number().finite(),
      min_z: z.number().finite(),
      max_z: z.number().finite(),
    }),
    barriers: z.array(z.object({
      name: z.string().min(1),
      min_x: z.number().finite(),
      max_x: z.number().finite(),
      min_z: z.number().finite(),
      max_z: z.number().finite(),
    })),
    camera_presets: z.array(cameraPresetSchema).superRefine((presets, context) => {
      for (const required of ["kitchen_overview", "walk_start", "overhead"] as const) {
        if (!presets.some((preset) => preset.name === required)) {
          context.addIssue({ code: "custom", message: `missing camera preset: ${required}` });
        }
      }
    }),
  }),
}).passthrough();


export type TourManifest = z.infer<typeof manifestSchema>;


export function parseTourManifest(value: unknown): TourManifest {
  return manifestSchema.parse(value);
}


const modeDescriptions: Record<TourMode, string> = {
  orbit: "Orbit mode · Drag to look around and scroll to zoom.",
  move: "Move here mode · Select a clear spot on the floor.",
  walk: "Walk mode · Use the movement keys and look around at person height.",
};


export function TourPage() {
  const [attempt, setAttempt] = useState(0);
  const [manifest, setManifest] = useState<TourManifest | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [sceneReady, setSceneReady] = useState(false);
  const [mode, setMode] = useState<TourMode>("orbit");
  const [preset, setPreset] = useState<TourPresetName>("kitchen_overview");
  const [viewRevision, setViewRevision] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setManifest(null);
    setLoadError(false);
    setSceneReady(false);

    async function loadManifest() {
      try {
        const response = await fetch("/tour-spike/manifest.json", { signal: controller.signal });
        if (!response.ok) throw new Error(`manifest request failed: ${response.status}`);
        const nextManifest = parseTourManifest(await response.json());
        if (!controller.signal.aborted) setManifest(nextManifest);
      } catch (error) {
        if (!controller.signal.aborted) setLoadError(true);
      }
    }

    void loadManifest();
    return () => controller.abort();
  }, [attempt]);

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

  return (
    <main className="tour-page">
      <header className="tour-header">
        <div>
          <p className="eyebrow">A first look, grounded in the A-1 plan</p>
          <h1>Explore the proposed kitchen and family room</h1>
          <p>Move from a wide overview to a person-height walk through the shared living space.</p>
        </div>
        <aside className="tour-trust-note" aria-label="Tour trust note">
          <strong>{manifest.label}</strong>
          <span>Furniture, décor, and finishes are provisional visual choices—not measured construction details.</span>
        </aside>
      </header>

      <section className="tour-workspace" aria-label="Interactive room tour">
        <div className="tour-stage">
          <TourViewer
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
            <div className="tour-map" aria-hidden="true">
              <span className="tour-map__kitchen">Kitchen</span>
              <span className="tour-map__island">Island</span>
              <span className="tour-map__living">Family room</span>
              <span className="tour-map__north">↑</span>
            </div>
          </div>

          <p className="tour-local-note"><span aria-hidden="true">◆</span> This detailed room stays on this Mac after the assets are prepared.</p>
        </aside>
      </section>
    </main>
  );
}
