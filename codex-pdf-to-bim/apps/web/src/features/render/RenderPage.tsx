import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { api, ApiError } from "../../api/client";
import type { BlenderCapabilityResponse, RenderJobResponse } from "../../api/types";
import { HelpTooltip } from "../../components/HelpTooltip";


export type BlenderCapability = BlenderCapabilityResponse;
type RenderJob = RenderJobResponse;

type RenderPageProps = {
  capability?: BlenderCapability;
  projectId?: string;
  geometryArtifactId?: string;
};


export function RenderPage({ capability: capabilityProp, projectId: projectIdProp, geometryArtifactId: geometryProp }: RenderPageProps) {
  const params = useParams();
  const [searchParams] = useSearchParams();
  const projectId = projectIdProp ?? params.projectId ?? "";
  const geometryArtifactId = geometryProp ?? searchParams.get("geometry") ?? "";
  const sourceId = searchParams.get("source") ?? "";
  const [capability, setCapability] = useState<BlenderCapability | null>(capabilityProp ?? null);
  const [camera, setCamera] = useState("KITCHEN");
  const [quality, setQuality] = useState("FINAL");
  const [size, setSize] = useState("1920x1080");
  const [job, setJob] = useState<RenderJob | null>(null);
  const [error, setError] = useState<{ message: string; action: string } | null>(null);

  useEffect(() => {
    if (capabilityProp) return;
    let active = true;
    api.get<BlenderCapability>("/api/render-capability")
      .then((result) => { if (active) setCapability(result); })
      .catch(() => { if (active) setCapability({ available: false, executable: null, version: null, message: "Render support could not be checked.", action: "Restart HearthView and try again." }); });
    return () => { active = false; };
  }, [capabilityProp]);

  useEffect(() => {
    if (!projectId) return;
    let active = true;
    api.get<RenderJob>(`/api/projects/${projectId}/render-jobs/latest`)
      .then((result) => { if (active) setJob(result); })
      .catch(() => undefined);
    return () => { active = false; };
  }, [projectId]);

  useEffect(() => {
    if (!job || !["QUEUED", "RUNNING"].includes(job.status)) return;
    const interval = window.setInterval(() => {
      api.get<RenderJob>(`/api/render-jobs/${job.id}`).then(setJob).catch(() => undefined);
    }, 1500);
    return () => window.clearInterval(interval);
  }, [job]);

  async function startRender() {
    const [width, height] = size.split("x").map(Number);
    setError(null);
    try {
      const response = await api.post<RenderJob>(`/api/projects/${projectId}/render-jobs`, {
        geometry_artifact_id: geometryArtifactId,
        camera,
        quality,
        width,
        height,
        style: "WARM_BLANK_SLATE",
      });
      setJob(response);
    } catch (caught) {
      setError(caught instanceof ApiError
        ? { message: caught.message, action: caught.action }
        : { message: "HearthView could not start this render.", action: "Check Blender, then try again." });
    }
  }

  const modelUrl = `/projects/${projectId}/model?source=${encodeURIComponent(sourceId)}`;
  const reportUrl = `/projects/${projectId}/report`;
  const canRender = Boolean(capability?.available && geometryArtifactId && !job?.status.match(/QUEUED|RUNNING/));

  return (
    <main className="workspace-page render-page">
      <header className="workspace-header">
        <div>
          <p className="eyebrow">Step 4 · Render</p>
          <h1>Create a warm, polished view</h1>
          <p>Start with a tasteful blank slate: enough furniture to understand scale, without deciding your décor for you.</p>
        </div>
        <Link className="button button--quiet" to={modelUrl}>Keep exploring in 3D</Link>
      </header>

      <section className="render-workspace">
        <div className="render-preview">
          {job?.status === "COMPLETE" && job.image_url ? (
            <>
              <img src={job.image_url} alt="Warm Blank Slate photoreal render" />
              <a className="render-download" href={job.image_url} download>Download full-size PNG</a>
            </>
          ) : (
            <div className="render-preview__concept" aria-label="Warm neutral furnished room preview">
              <span className="concept-window" />
              <span className="concept-island" />
              <span className="concept-sofa" />
              <span className="concept-rug" />
              <div><strong>Warm Blank Slate</strong><span>Warm neutrals and just enough furniture to understand scale</span></div>
            </div>
          )}
          {job ? <div className={`render-job render-job--${job.status.toLowerCase()}`} role="status"><strong>{job.status === "COMPLETE" ? "Render ready" : job.status === "FAILED" ? "Render needs attention" : "Creating your render"}</strong><span>{job.message}</span></div> : null}
        </div>

        <aside className="render-settings" aria-label="Render settings">
          <div className="render-settings__heading">
            <div><p className="decision-card__kicker">Your settings</p><h2>Frame the view</h2></div>
            <HelpTooltip label="About these render settings">Settings affect only lighting, furnishings, camera, and image quality. They never edit the approved geometry.</HelpTooltip>
          </div>

          <div className="field">
            <label htmlFor="visual-style">Visual style</label>
            <select id="visual-style" value="Warm Blank Slate" disabled>
              <option>Warm Blank Slate</option>
            </select>
            <small>Lightly furnished with warm, neutral finishes</small>
          </div>
          <div className="field">
            <label htmlFor="render-camera">Camera view</label>
            <select id="render-camera" value={camera} onChange={(event) => setCamera(event.target.value)}>
              <option value="KITCHEN">Kitchen view</option>
              <option value="LIVING_ROOM">Living room view</option>
              <option value="AXONOMETRIC">3D overview</option>
              <option value="PLAN">Plan view</option>
            </select>
            <small>Choose the room or overview you want to render.</small>
          </div>
          <div className="field">
            <label htmlFor="render-quality">Render quality</label>
            <select id="render-quality" value={quality} onChange={(event) => setQuality(event.target.value)}>
              <option value="DRAFT">Draft · quicker preview</option>
              <option value="FINAL">Final · photoreal quality</option>
            </select>
            <small>{quality === "FINAL" ? "Uses ray-traced lighting and denoising; allow several minutes." : "Uses a faster lighting engine for checking the composition."}</small>
          </div>
          <div className="field">
            <label htmlFor="render-size">Image size</label>
            <select id="render-size" value={size} onChange={(event) => setSize(event.target.value)}>
              <option value="1280x720">1280 × 720 · screen</option>
              <option value="1920x1080">1920 × 1080 · Full HD</option>
              <option value="2560x1440">2560 × 1440 · large</option>
            </select>
            <small>Larger images take longer and use more memory.</small>
          </div>

          {capability && !capability.available ? (
            <div className="capability-note" role="status">
              <strong>One-time renderer setup needed</strong>
              <p>{capability.message}</p>
              <span>{capability.action}</span>
            </div>
          ) : capability?.available ? <p className="renderer-ready">✓ {capability.version ?? "Blender"} is ready locally</p> : <p className="renderer-ready">Checking local renderer…</p>}
          {error ? <div className="inline-error" role="alert"><strong>{error.message}</strong><span>{error.action}</span></div> : null}
          <button className="button button--primary button--wide" type="button" disabled={!canRender} onClick={() => void startRender()}>Create polished render</button>
          <p className="render-privacy">The approved model is rendered on this Mac. No plan or image upload is required.</p>
          {job?.status === "COMPLETE" ? <Link className="button button--quiet button--wide" to={reportUrl}>View plan-to-3D report</Link> : null}
        </aside>
      </section>
    </main>
  );
}
