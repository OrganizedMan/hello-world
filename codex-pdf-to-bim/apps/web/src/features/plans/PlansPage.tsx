import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { api, ApiError } from "../../api/client";
import type { SourceResponse } from "../../api/types";
import { HelpTooltip } from "../../components/HelpTooltip";


type PlansPageProps = {
  projectId?: string;
  sourceId?: string;
  pageCount?: number;
};


export function PlansPage({ projectId: projectIdProp, sourceId: sourceIdProp, pageCount: pageCountProp }: PlansPageProps) {
  const params = useParams();
  const [searchParams] = useSearchParams();
  const projectId = projectIdProp ?? params.projectId ?? "";
  const sourceId = sourceIdProp ?? searchParams.get("source") ?? "";
  const [pageCount, setPageCount] = useState<number | null>(pageCountProp ?? null);
  const [selectedPage, setSelectedPage] = useState(pageCountProp === 1 ? 1 : 2);
  const [zoom, setZoom] = useState(100);
  const [selected, setSelected] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const previewUrl = `/api/projects/${projectId}/sources/${sourceId}/pages/${selectedPage}/preview?max_width=1600`;
  const reviewUrl = `/projects/${projectId}/review?source=${encodeURIComponent(sourceId)}`;
  const isA1 = selectedPage === 2 && (pageCount ?? 0) >= 2;

  useEffect(() => {
    if (pageCountProp !== undefined || !projectId || !sourceId) return;
    let active = true;
    api.get<SourceResponse>(`/api/projects/${projectId}/sources/${sourceId}`)
      .then((source) => {
        if (!active) return;
        setPageCount(source.page_count);
        if (source.page_count < 2) setSelectedPage(1);
      })
      .catch((caught) => {
        if (!active) return;
        setLoadError(caught instanceof ApiError ? caught.message : "HearthView could not list the PDF pages.");
      });
    return () => { active = false; };
  }, [pageCountProp, projectId, sourceId]);

  return (
    <main className="workspace-page">
      <header className="workspace-header">
        <div>
          <p className="eyebrow">Step 1 · Plans</p>
          <h1>Choose the proposed plan</h1>
          <p>We found the sheet most likely to describe the renovation. Make sure it is the future layout—not the existing house.</p>
        </div>
        <div className="workspace-header__note">
          <strong>{isA1 ? "Sheet A-1" : `Page ${selectedPage}`}</strong>
          <span>{isA1 ? "Proposed first floor" : "Not selected for 3D"}</span>
        </div>
      </header>

      <section className="plan-workspace" aria-label="Proposed plan selection">
        <div className="plan-viewer">
          <div className="plan-viewer__toolbar">
            <label htmlFor="plan-zoom">Plan zoom</label>
            <input
              id="plan-zoom"
              type="range"
              min="60"
              max="180"
              step="10"
              value={zoom}
              onChange={(event) => setZoom(Number(event.target.value))}
            />
            <output htmlFor="plan-zoom">{zoom}%</output>
            <HelpTooltip label="How to inspect this plan">
              Zoom in to read dimensions. HearthView uses the proposed first-floor drawing on sheet A-1 as its source.
            </HelpTooltip>
          </div>
          {pageCount ? (
            <div className="plan-pages" aria-label="PDF pages">
              {Array.from({ length: pageCount }, (_value, index) => index + 1).map((page) => (
                <button
                  aria-label={`Page ${page}`}
                  className={selectedPage === page ? "is-active" : ""}
                  key={page}
                  type="button"
                  onClick={() => {
                    setSelectedPage(page);
                    setSelected(false);
                  }}
                >
                  <img
                    src={`/api/projects/${projectId}/sources/${sourceId}/pages/${page}/preview?max_width=320`}
                    alt=""
                  />
                  <span>{page === 2 ? "Page 2 · A-1" : `Page ${page}`}</span>
                </button>
              ))}
            </div>
          ) : null}
          <div className="plan-viewer__canvas">
            <img
              src={previewUrl}
              alt={isA1 ? "Sheet A-1 proposed first-floor plan" : `PDF page ${selectedPage}`}
              style={{ width: `${zoom}%` }}
            />
          </div>
        </div>

        <aside className="decision-card">
          <p className="decision-card__kicker">One quick check</p>
          <h2>Is this the new layout?</h2>
          <p>Look for the title “Proposed First Floor Plan” and the kitchen, family room, and mudroom changes.</p>
          <dl className="source-facts">
            <div><dt>Drawing</dt><dd>A-1</dd></div>
            <div><dt>View</dt><dd>Proposed first floor</dd></div>
            <div><dt>Used for</dt><dd>3D layout and dimensions</dd></div>
          </dl>
          {loadError ? <div className="inline-error" role="alert"><strong>{loadError}</strong><span>Return to the start and import the PDF again.</span></div> : null}
          {!isA1 && pageCount ? (
            <div className="inline-error" role="alert">
              <strong>Select page 2 for this Garrigan A-1 model.</strong>
              <span>Other plan layouts remain viewable, but this local version will not guess their geometry.</span>
            </div>
          ) : null}
          <button className="button button--primary button--wide" type="button" disabled={!isA1} onClick={() => setSelected(true)}>
            Use proposed first floor
          </button>
          {selected ? (
            <div className="selection-confirmation" aria-live="polite">
              <strong>Proposed first floor selected</strong>
              <span>Next, confirm five details that protect the 3D layout.</span>
              <Link className="button button--primary button--wide" to={reviewUrl}>Review important details</Link>
            </div>
          ) : null}
        </aside>
      </section>
    </main>
  );
}
