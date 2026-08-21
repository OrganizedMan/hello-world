import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { api, ApiError } from "../../api/client";
import type { GeometryResponse, ValidationRunResponse } from "../../api/types";
import { HelpTooltip } from "../../components/HelpTooltip";
import { StatusBanner } from "../../components/StatusBanner";
import { ModelViewer, type CameraPreset } from "./ModelViewer";


export type GeometryArtifact = GeometryResponse;

type ModelPageProps = {
  artifact?: GeometryArtifact;
  projectId?: string;
  sourceId?: string;
};

const cameraLabels: Record<CameraPreset, string> = {
  plan: "Plan camera selected",
  axonometric: "Axonometric camera selected",
  kitchen: "Kitchen camera selected",
  living: "Living-room camera selected",
};

const elementDetails: Record<string, { title: string; description: string; referenceId: string }> = {
  kitchen_island: { title: "Kitchen island", description: "Dimensions confirmed during guided review.", referenceId: "src_a1_island" },
  family_east: { title: "East living-room wall", description: "Window, solid TV area, then mudroom opening.", referenceId: "src_a1_family_east" },
  family_south: { title: "South living-room wall", description: "3-foot-1-inch wall, 5-foot opening, 3-foot-1-inch wall.", referenceId: "src_a1_family_south" },
  family_tv: { title: "60-inch TV", description: "Located entirely on the solid east wall section.", referenceId: "src_a1_tv" },
  staging_floor_estimated: { title: "Estimated staging area", description: "A neutral viewing surface estimated around the verified A-1 elements; it is not a traced floor outline.", referenceId: "src_a1_region" },
};


export function ModelPage({ artifact: artifactProp, projectId: projectIdProp, sourceId: sourceIdProp }: ModelPageProps) {
  const params = useParams();
  const [searchParams] = useSearchParams();
  const projectId = projectIdProp ?? params.projectId ?? "";
  const sourceId = sourceIdProp ?? searchParams.get("source") ?? "";
  const [artifact, setArtifact] = useState<GeometryArtifact | null>(artifactProp ?? null);
  const [validation, setValidation] = useState<ValidationRunResponse["report"] | null>(null);
  const [camera, setCamera] = useState<CameraPreset>("axonometric");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState<{ message: string; action: string } | null>(null);
  const [isBuilding, setIsBuilding] = useState(!artifactProp);

  useEffect(() => {
    if (artifactProp || !projectId) return;
    let active = true;
    setIsBuilding(true);
    api.post<ValidationRunResponse>(`/api/projects/${projectId}/validate`).then(async (result) => {
      if (!active) return;
      setValidation(result.report);
      if (!result.token) return null;
      return api.post<GeometryArtifact>(`/api/projects/${projectId}/compile`, { token: result.token });
    }).then((compiled) => {
      if (active && compiled) setArtifact(compiled);
    }).catch((caught) => {
      if (!active) return;
      setError(caught instanceof ApiError
        ? { message: caught.message, action: caught.action }
        : { message: "HearthView could not build this 3D view.", action: "Return to Review, confirm the plan details, and try again." });
    }).finally(() => {
      if (active) setIsBuilding(false);
    });
    return () => { active = false; };
  }, [artifactProp, projectId]);

  const selected = selectedId ? (elementDetails[selectedId] ?? null) : null;
  const selectedDescription = selectedId === "kitchen_island" && artifact
    ? `${artifact.island_dimensions} confirmed during guided review.`
    : selected?.description;

  function chooseCamera(preset: CameraPreset) {
    setCamera(preset);
  }

  return (
    <main className="workspace-page model-page">
      <header className="workspace-header">
        <div>
          <p className="eyebrow">Step 3 · Model</p>
          <h1>Explore your proposed home</h1>
          <p>Orbit freely or jump to a familiar view. Changing cameras never changes the approved dimensions.</p>
        </div>
        {validation ? <StatusBanner status={validation.status} remaining={validation.blocking_count} /> : artifact ? <StatusBanner status="READY_TO_VIEW" /> : null}
      </header>

      {isBuilding ? <div className="model-loading" role="status"><span /><strong>Building one consistent 3D model…</strong><p>Checking dimensions and preparing the browser view.</p></div> : null}
      {error ? <div className="page-message inline-error" role="alert"><strong>{error.message}</strong><span>{error.action}</span></div> : null}
      {!isBuilding && validation && !artifact ? (
        <section className="model-blocked">
          <h2>A few plan details still need you</h2>
          <p>{validation.blocking_count} confirmations remain before HearthView can create a trusted 3D model.</p>
          <Link className="button button--primary" to={`/projects/${projectId}/review?source=${encodeURIComponent(sourceId)}`}>Finish plan review</Link>
        </section>
      ) : null}

      {artifact ? (
        <>
          <section className="model-toolbar" aria-label="3D camera views">
            <div>
              <strong>Choose a view</strong>
              <HelpTooltip label="How camera views work">These buttons move only the camera. The geometry hash below proves the model stays the same.</HelpTooltip>
            </div>
            <div className="camera-buttons">
              <button className={camera === "plan" ? "is-active" : ""} type="button" onClick={() => chooseCamera("plan")}>Plan view</button>
              <button className={camera === "axonometric" ? "is-active" : ""} type="button" onClick={() => chooseCamera("axonometric")}>3D overview</button>
              <button className={camera === "kitchen" ? "is-active" : ""} type="button" onClick={() => chooseCamera("kitchen")}>Kitchen view</button>
              <button className={camera === "living" ? "is-active" : ""} type="button" onClick={() => chooseCamera("living")}>Living room view</button>
            </div>
            <span className="visually-hidden" aria-live="polite">{cameraLabels[camera]}</span>
          </section>

          <section className="model-workspace">
            <div className="model-stage">
              <ModelViewer url={artifact.download_url} cameraPreset={camera} onSelect={setSelectedId} />
              <div className="geometry-identity">
                <span>One verified geometry</span>
                <code data-testid="geometry-hash">{artifact.geometry_hash}</code>
                <HelpTooltip label="What is a geometry hash?">A digital fingerprint. It stays identical while you orbit or change cameras, proving every view uses the same model.</HelpTooltip>
              </div>
              <p className="model-scope-note">Verified walls, openings, island, and TV are plan-derived. The neutral floor surface is an estimated staging aid.</p>
            </div>
            <aside className="model-evidence">
              <div className="model-element-list" aria-label="Model elements">
                <strong>Select an element</strong>
                {Object.entries(elementDetails).map(([elementId, detail]) => (
                  <button
                    className={selectedId === elementId ? "is-active" : ""}
                    key={elementId}
                    type="button"
                    onClick={() => setSelectedId(elementId)}
                  >
                    {detail.title}
                  </button>
                ))}
              </div>
              {selected ? (
                <>
                  <p className="decision-card__kicker">Selected in 3D</p>
                  <h2>{selected.title}</h2>
                  <p>{selectedDescription}</p>
                  <img
                    src={`/api/projects/${projectId}/evidence/${encodeURIComponent(selected.referenceId)}/preview?max_width=900`}
                    alt={`A-1 evidence for ${selected.title}`}
                  />
                  <span className="evidence-badge">Documented on sheet A-1</span>
                </>
              ) : (
                <div className="model-evidence__empty">
                  <span aria-hidden="true">↖</span>
                  <h2>Click something in 3D</h2>
                  <p>We’ll show the exact plan evidence behind that wall, island, or TV.</p>
                </div>
              )}
            </aside>
          </section>
          <div className="continue-strip">
            <span>This model is ready for a warm, lightly furnished rendering.</span>
            <Link className="button button--primary" to={`/projects/${projectId}/render?source=${encodeURIComponent(sourceId)}&geometry=${encodeURIComponent(artifact.artifact_id)}&geometryHash=${encodeURIComponent(artifact.geometry_hash)}`}>Create a polished render</Link>
          </div>
        </>
      ) : null}
    </main>
  );
}
