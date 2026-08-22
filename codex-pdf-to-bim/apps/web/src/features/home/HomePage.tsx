import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, ApiError } from "../../api/client";
import type { ProjectResponse, SourceResponse } from "../../api/types";
import { HelpTooltip } from "../../components/HelpTooltip";


export function HomePage() {
  const navigate = useNavigate();
  const [isImporting, setIsImporting] = useState(false);
  const [error, setError] = useState<{ message: string; action: string } | null>(null);

  async function importPdf(file: File) {
    setIsImporting(true);
    setError(null);
    try {
      const suggestedName = file.name.replace(/\.pdf$/i, "").trim() || "My renovation";
      const project = await api.post<ProjectResponse>("/api/projects", { name: suggestedName });
      const form = new FormData();
      form.append("file", file);
      const source = await api.upload<SourceResponse>(`/api/projects/${project.id}/sources`, form);
      navigate(`/projects/${project.id}/plans?source=${encodeURIComponent(source.id)}`);
    } catch (caught) {
      if (caught instanceof ApiError) {
        setError({ message: caught.message, action: caught.action });
      } else {
        setError({
          message: "HearthView could not reach its local plan service.",
          action: "Keep this page open, restart HearthView, and try the PDF again.",
        });
      }
    } finally {
      setIsImporting(false);
    }
  }

  return (
    <main className="home-page">
      <section className="hero">
        <div className="hero__copy">
          <p className="eyebrow">A calmer way to understand your renovation</p>
          <h1>See your plans come to life</h1>
          <p className="hero__lede">
            Add your architect&apos;s PDF, confirm a few important details, and walk through a
            clear 3D version of the proposed home.
          </p>
          <div className="hero__actions">
            <label className={`button button--primary file-button${isImporting ? " file-button--busy" : ""}`}>
              <span>{isImporting ? "Reading your plans…" : "Add plan PDFs"}</span>
              <input
                className="visually-hidden"
                type="file"
                accept="application/pdf,.pdf"
                aria-label="Add plan PDFs"
                disabled={isImporting}
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) void importPdf(file);
                }}
              />
            </label>
            <span className="file-hint">Architectural PDF · up to 50 MB</span>
          </div>
          <div className="import-status" aria-live="polite">
            {isImporting ? <p>Creating a private project and preparing page previews…</p> : null}
            {error ? (
              <div className="inline-error" role="alert">
                <strong>{error.message}</strong>
                <span>{error.action}</span>
              </div>
            ) : null}
          </div>
          <p className="privacy-line">
            <span aria-hidden="true">◆</span>
            Your plans stay on this Mac
            <HelpTooltip label="Learn about plan privacy">
              Source PDFs, review decisions, 3D models, and renders remain in your local
              HearthView project folder.
            </HelpTooltip>
          </p>
        </div>
        <div className="hero__visual" aria-label="A floor plan becoming a warm 3D room">
          <div className="plan-card">
            <span className="plan-line plan-line--one" />
            <span className="plan-line plan-line--two" />
            <span className="plan-line plan-line--three" />
            <span className="plan-room">A-1</span>
          </div>
          <div className="room-card">
            <span className="room-card__sun" />
            <span className="room-card__island" />
            <span className="room-card__sofa" />
          </div>
        </div>
      </section>
      <section className="how-it-works" aria-labelledby="how-title">
        <div>
          <p className="eyebrow">Designed for homeowners</p>
          <h2 id="how-title">Three simple steps</h2>
        </div>
        <ol className="step-cards">
          <li><span>1</span><strong>Add your plans</strong><p>Drop in one or more architectural PDFs.</p></li>
          <li><span>2</span><strong>Confirm what matters</strong><p>We highlight only details that need your decision.</p></li>
          <li><span>3</span><strong>Explore and render</strong><p>Move through consistent 3D views and warm finished images.</p></li>
        </ol>
      </section>
    </main>
  );
}
