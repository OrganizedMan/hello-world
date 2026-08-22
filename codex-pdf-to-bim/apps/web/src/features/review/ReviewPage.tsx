import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { api, ApiError } from "../../api/client";
import type { ProjectResponse, ReviewItemResponse, RevisionResponse } from "../../api/types";
import { HelpTooltip } from "../../components/HelpTooltip";
import { LengthField } from "../../components/LengthField";


export type ReviewItem = ReviewItemResponse;

type ReviewWorkspaceProps = {
  queue: ReadonlyArray<ReviewItem>;
  revision: number;
  onConfirm: (
    item: ReviewItem,
    revision: number,
    decision: { operation: "APPROVE_REVIEW" | "EDIT_AND_APPROVE"; payload: Record<string, string> },
  ) => Promise<{ revision: number; eventId: string }>;
  onUndo: (targetEventId: string, revision: number) => Promise<number>;
  evidencePreviewUrl?: (referenceId: string) => string;
};


export function ReviewWorkspace({ queue, revision, onConfirm, onUndo, evidencePreviewUrl }: ReviewWorkspaceProps) {
  const [index, setIndex] = useState(0);
  const [currentRevision, setCurrentRevision] = useState(revision);
  const [history, setHistory] = useState<ReadonlyArray<string>>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [islandWidth, setIslandWidth] = useState(`8'-7"`);
  const [islandDepth, setIslandDepth] = useState(`4'-3"`);
  const item = queue[index];

  useEffect(() => setCurrentRevision(revision), [revision]);

  if (!item) {
    return (
      <section className="review-complete" aria-live="polite">
        <span aria-hidden="true">✓</span>
        <h2>Your plan details are confirmed</h2>
        <p>HearthView can now check the layout and build your first 3D model.</p>
      </section>
    );
  }

  async function confirm() {
    setIsSaving(true);
    setError(null);
    try {
      const editedIsland = item.id === "review_a1_island"
        && (islandWidth !== `8'-7"` || islandDepth !== `4'-3"`);
      const result = await onConfirm(item, currentRevision, {
        operation: editedIsland ? "EDIT_AND_APPROVE" : "APPROVE_REVIEW",
        payload: editedIsland ? { width: islandWidth, depth: islandDepth } : {},
      });
      setCurrentRevision(result.revision);
      setHistory((current) => [...current, result.eventId]);
      setIndex((current) => current + 1);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "This decision could not be saved.");
    } finally {
      setIsSaving(false);
    }
  }

  async function undo() {
    const targetEventId = history.at(-1);
    if (!targetEventId) return;
    setIsSaving(true);
    setError(null);
    try {
      const nextRevision = await onUndo(targetEventId, currentRevision);
      setCurrentRevision(nextRevision);
      setHistory((current) => current.slice(0, -1));
      setIndex((current) => Math.max(0, current - 1));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "This decision could not be undone.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <section className="review-workspace" aria-label="Plan detail review">
      <div className="review-source">
        <div className="review-source__heading">
          <div>
            <span className="review-source__label">Source drawing</span>
            <strong>Sheet A-1 · Proposed first floor</strong>
          </div>
          <HelpTooltip label="Why this source is shown">
            Every confirmed detail stays linked to the drawing area that supports it.
          </HelpTooltip>
        </div>
        {evidencePreviewUrl ? <img src={evidencePreviewUrl(item.source_ref_id)} alt={`Highlighted source for ${item.title}`} /> : <div className="review-source__placeholder" aria-hidden="true">A-1</div>}
      </div>

      <article className="review-decision">
        <div className="review-progress">
          <span>{index + 1} of {queue.length}</span>
          <div className="review-progress__track" aria-hidden="true">
            <span style={{ width: `${((index + 1) / queue.length) * 100}%` }} />
          </div>
        </div>
        <p className="decision-card__kicker">Important plan detail</p>
        <h2>{item.title}</h2>
        <p className="review-decision__question">{item.question}</p>
        {item.value ? (
          <div className="review-value">
            <span>Value read from plan</span>
            <strong>{item.value}</strong>
          </div>
        ) : null}
        {item.id === "review_a1_island" ? (
          <div className="review-edit-fields" aria-label="Correct island dimensions">
            <LengthField id="review-island-width" label="Island width" value={islandWidth} onCommit={setIslandWidth} onDraftChange={setIslandWidth} disabled={isSaving} />
            <LengthField id="review-island-depth" label="Island depth" value={islandDepth} onCommit={setIslandDepth} onDraftChange={setIslandDepth} disabled={isSaving} />
          </div>
        ) : null}
        <div className="why-box">
          <strong>Why we’re asking</strong>
          <p>{item.help_text}</p>
        </div>
        {error ? <div className="inline-error" role="alert"><strong>{error}</strong><span>Please try again.</span></div> : null}
        <div className="review-actions">
          <button className="button button--primary" type="button" disabled={isSaving} onClick={() => void confirm()}>
            {isSaving ? "Saving…" : "Confirm and continue"}
          </button>
          <button
            className="button button--quiet"
            type="button"
            disabled={isSaving || index === 0}
            onClick={() => void undo()}
          >
            Go back
          </button>
        </div>
      </article>
    </section>
  );
}


export function ReviewPage() {
  const { projectId = "" } = useParams();
  const [searchParams] = useSearchParams();
  const sourceId = searchParams.get("source") ?? "";
  const [queue, setQueue] = useState<ReadonlyArray<ReviewItem> | null>(null);
  const [revision, setRevision] = useState(0);
  const [loadError, setLoadError] = useState<{ message: string; action: string } | null>(null);
  useEffect(() => {
    let active = true;
    Promise.all([
      api.get<ProjectResponse>(`/api/projects/${projectId}`),
      api.get<ReviewItem[]>(`/api/projects/${projectId}/review-queue`),
    ]).then(([project, items]) => {
      if (!active) return;
      setRevision(project.revision);
      setQueue(items.filter((item) => item.state === "UNREVIEWED"));
    }).catch((caught) => {
      if (!active) return;
      setLoadError(caught instanceof ApiError
        ? { message: caught.message, action: caught.action }
        : { message: "HearthView could not open this review.", action: "Return to Plans and try again." });
    });
    return () => { active = false; };
  }, [projectId]);

  async function confirm(
    item: ReviewItem,
    baseRevision: number,
    decision: { operation: "APPROVE_REVIEW" | "EDIT_AND_APPROVE"; payload: Record<string, string> },
  ) {
    const eventId = typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `${Date.now()}-${item.id}`;
    const response = await api.post<RevisionResponse>(`/api/projects/${projectId}/review-events`, {
      id: eventId,
      base_revision: baseRevision,
      operation: decision.operation,
      item_id: item.id,
      payload: decision.payload,
      source_ref_ids: [item.source_ref_id],
      rationale: decision.operation === "EDIT_AND_APPROVE"
        ? "Homeowner corrected and confirmed this plan detail in guided review."
        : "Homeowner confirmed this plan detail in guided review.",
    });
    setRevision(response.revision);
    return { revision: response.revision, eventId };
  }

  async function undo(targetEventId: string, baseRevision: number) {
    const eventId = typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `${Date.now()}-undo`;
    const response = await api.post<RevisionResponse>(`/api/projects/${projectId}/review-events/revert`, {
      id: eventId,
      base_revision: baseRevision,
      target_event_id: targetEventId,
    });
    setRevision(response.revision);
    return response.revision;
  }

  return (
    <main className="workspace-page">
      <header className="workspace-header">
        <div>
          <p className="eyebrow">Step 2 · Review</p>
          <h1>Confirm what matters</h1>
          <p>One clear decision at a time. Each answer remains tied to the exact drawing that informed it.</p>
        </div>
        <Link className="button button--quiet" to={`/projects/${projectId}/plans?source=${encodeURIComponent(sourceId)}`}>Back to plan</Link>
      </header>
      {loadError ? <div className="page-message inline-error" role="alert"><strong>{loadError.message}</strong><span>{loadError.action}</span></div> : null}
      {!queue && !loadError ? <p className="page-message" aria-live="polite">Preparing your review…</p> : null}
      {queue ? (
        <>
          <ReviewWorkspace
            queue={queue}
            revision={revision}
            onConfirm={confirm}
            onUndo={undo}
            evidencePreviewUrl={(referenceId) => `/api/projects/${projectId}/evidence/${encodeURIComponent(referenceId)}/preview?max_width=1400`}
          />
          <div className="continue-strip">
            <span>After all five checks, HearthView validates the layout before creating 3D.</span>
            <Link className="button button--quiet" to={`/projects/${projectId}/model?source=${encodeURIComponent(sourceId)}`}>Go to 3D model</Link>
          </div>
        </>
      ) : null}
    </main>
  );
}
