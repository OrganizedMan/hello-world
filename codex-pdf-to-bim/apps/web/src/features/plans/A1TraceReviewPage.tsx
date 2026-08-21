import { useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { api, ApiError } from "../../api/client";
import type { A1TraceResponse, TraceRecordResponse } from "../../api/types";
import { A1TraceCanvas, type ProvenanceFilter, type TraceMode } from "./A1TraceCanvas";
import { provenanceLabel, traceRecordLabel } from "./a1Trace";


type A1TraceReviewPageProps = {
  projectId?: string;
  sourceId?: string;
  trace?: A1TraceResponse;
};


export function A1TraceReviewPage({ projectId: projectIdProp, sourceId: sourceIdProp, trace: suppliedTrace }: A1TraceReviewPageProps) {
  const params = useParams();
  const [searchParams] = useSearchParams();
  const projectId = projectIdProp ?? params.projectId ?? "";
  const sourceId = sourceIdProp ?? searchParams.get("source") ?? "";
  const [trace, setTrace] = useState<A1TraceResponse | null>(suppliedTrace ?? null);
  const [error, setError] = useState<{ message: string; action: string } | null>(null);
  const [mode, setMode] = useState<TraceMode>("pdf");
  const [filter, setFilter] = useState<ProvenanceFilter>("all");
  const [selected, setSelected] = useState<TraceRecordResponse | null>(null);

  useEffect(() => {
    if (suppliedTrace || !projectId || !sourceId) return;
    let active = true;
    api.get<A1TraceResponse>(`/api/projects/${projectId}/sources/${sourceId}/a1-trace`)
      .then((nextTrace) => {
        if (!active) return;
        setTrace(nextTrace);
        setSelected(nextTrace.records[0] ?? null);
      })
      .catch((caught) => {
        if (!active) return;
        setError(caught instanceof ApiError
          ? { message: caught.message, action: caught.action }
          : { message: "HearthView could not open the A-1 trace.", action: "Return to Plans and try again." });
      });
    return () => { active = false; };
  }, [projectId, sourceId, suppliedTrace]);

  const records = useMemo(() => trace?.records.filter((record) => filter === "all" || record.provenance === filter) ?? [], [filter, trace]);
  const previewUrl = `/api/projects/${projectId}/sources/${sourceId}/a1-trace/preview?max_width=2048`;

  if (error) {
    return <main className="workspace-page"><div className="page-message inline-error" role="alert"><strong>{error.message}</strong><span>{error.action}</span></div></main>;
  }
  if (!trace) {
    return <main className="workspace-page"><p className="page-message" role="status">Preparing the A-1 trace…</p></main>;
  }

  return (
    <main className="workspace-page a1-trace-page">
      <header className="workspace-header">
        <div>
          <p className="eyebrow">A-1 geometry review</p>
          <h1>Compare the full proposed first floor</h1>
          <p>Inspect the PDF and trace together before any 3D work resumes.</p>
        </div>
        <Link className="button button--quiet" to={`/projects/${projectId}/plans?source=${encodeURIComponent(sourceId)}`}>Back to plan</Link>
      </header>
      <section className="a1-trace-workspace" aria-label="A-1 trace review">
        <div className="a1-trace-stage">
          <div className="a1-trace-toolbar" aria-label="Trace view controls">
            {(["pdf", "trace", "overlay"] as const).map((item) => <button key={item} type="button" className={mode === item ? "is-active" : ""} onClick={() => setMode(item)}>{item === "pdf" ? "PDF" : item === "trace" ? "Trace" : "Overlay"}</button>)}
          </div>
          <div className="a1-trace-frame">
            {mode !== "trace" ? <img src={previewUrl} alt="A-1 proposed first-floor plan crop" /> : null}
            <A1TraceCanvas trace={trace} mode={mode} provenanceFilter={filter} selectedId={selected?.id ?? null} onSelect={setSelected} />
          </div>
        </div>
        <aside className="a1-trace-panel">
          <p className="decision-card__kicker">Trace approval: pending</p>
          <h2>This trace is not approved for 3D</h2>
          <p>Verified items cite printed A-1 dimensions. Other elements are traced from visible drawing linework.</p>
          <dl className="a1-trace-counts">
            <div><dt>Dimension verified</dt><dd>{trace.summary.verified}</dd></div>
            <div><dt>Linework traced</dt><dd>{trace.summary.traced}</dd></div>
            <div><dt>Ambiguous</dt><dd>{trace.summary.ambiguous}</dd></div>
          </dl>
          <div className="a1-trace-filters" aria-label="Trace provenance filters">
            {(["all", "dimension_verified", "linework_traced", "ambiguous"] as const).map((item) => <button key={item} type="button" className={filter === item ? "is-active" : ""} onClick={() => setFilter(item)}>{item === "all" ? "All records" : provenanceLabel(item)}</button>)}
          </div>
          <div className="a1-trace-records" aria-label="Trace records">
            {records.map((record) => <button type="button" key={record.id} className={selected?.id === record.id ? "is-active" : ""} onClick={() => setSelected(record)}>{traceRecordLabel(record)}</button>)}
          </div>
          {selected ? <div className="a1-trace-selection"><strong>{traceRecordLabel(selected)}</strong><span>{provenanceLabel(selected.provenance)}</span>{selected.dimension_labels.length ? <small>Source: {selected.dimension_labels.join(", ")}</small> : <small>Position follows visible A-1 linework; no printed offset is claimed.</small>}</div> : null}
        </aside>
      </section>
    </main>
  );
}
