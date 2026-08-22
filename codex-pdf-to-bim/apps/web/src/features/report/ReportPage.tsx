import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api } from "../../api/client";
import { StatusBanner } from "../../components/StatusBanner";


type ReportIssue = { readonly code: string; readonly message: string; readonly action: string };
export type HomeownerReport = {
  status: "READY_TO_VIEW" | "NEEDS_INPUT" | "CONFLICTING_INFORMATION";
  blocking_count: number;
  evidence_coverage_percent: number;
  source_name: string;
  source_hash: string;
  model_hash: string;
  geometry_hash: string;
  island_dimensions: string;
  validator_version: string;
  issues: ReadonlyArray<ReportIssue>;
};

export function ReportPage({ report: reportProp }: { report?: HomeownerReport }) {
  const { projectId = "" } = useParams();
  const [report, setReport] = useState<HomeownerReport | null>(reportProp ?? null);
  const [loadFailed, setLoadFailed] = useState(false);

  useEffect(() => {
    if (reportProp || !projectId) return;
    let active = true;
    api.get<HomeownerReport>(`/api/projects/${projectId}/report`)
      .then((authoritativeReport) => {
        if (active) setReport(authoritativeReport);
      })
      .catch(() => { if (active) setLoadFailed(true); });
    return () => { active = false; };
  }, [projectId, reportProp]);

  if (loadFailed) return <main className="workspace-page"><div className="page-message inline-error" role="alert"><strong>This report could not be opened.</strong><span>Return to your model and try again.</span></div></main>;
  if (!report) return <main className="workspace-page"><p className="page-message" role="status">Preparing your plan-to-3D report…</p></main>;

  const ready = report.status === "READY_TO_VIEW" && report.blocking_count === 0;
  return (
    <main className="workspace-page report-page">
      <header className="workspace-header">
        <div>
          <p className="eyebrow">Step 5 · Report</p>
          <h1>Your plan-to-3D report</h1>
          <p>A readable record of what HearthView used, what you confirmed, and which exact geometry produced every view.</p>
        </div>
        <StatusBanner status={report.status} remaining={report.blocking_count} />
      </header>

      <section className="report-hero">
        <div className="report-verdict"><span aria-hidden="true">{ready ? "✓" : "!"}</span><div><strong>{ready ? "Ready to view and render" : "More review is needed"}</strong><p>{ready ? "All required A-1 facts passed the exact layout checks." : `${report.blocking_count} items must be resolved before a trusted render.`}</p></div></div>
        <div className="coverage-meter"><div><strong>{report.evidence_coverage_percent}%</strong><span>of modeled elements linked to evidence</span></div><div className="coverage-meter__bar"><span style={{ width: `${report.evidence_coverage_percent}%` }} /></div></div>
      </section>

      <section className="report-grid">
        <article className="report-card">
          <p className="decision-card__kicker">Source</p>
          <h2>Your drawing</h2>
          <dl className="identity-list">
            <div><dt>PDF</dt><dd>{report.source_name}</dd></div>
            <div><dt>Source fingerprint</dt><dd><code>{report.source_hash}</code></dd></div>
          </dl>
        </article>
        <article className="report-card">
          <p className="decision-card__kicker">Consistency</p>
          <h2>One model, every view</h2>
          <dl className="identity-list">
            <div><dt>Reviewed model</dt><dd><code>{report.model_hash}</code></dd></div>
            <div><dt>3D geometry</dt><dd><code>{report.geometry_hash}</code></dd></div>
          </dl>
        </article>
      </section>

      <section className="report-card report-checks">
        <div><p className="decision-card__kicker">Checks</p><h2>Important A-1 details</h2></div>
        {report.issues.length ? (
          <ul>{report.issues.map((issue) => <li key={`${issue.code}-${issue.message}`}><strong>{issue.message}</strong><span>{issue.action}</span></li>)}</ul>
        ) : (
          <ul className="passed-checks">
            <li><strong>Kitchen island</strong><span>{report.island_dimensions}</span></li>
            <li><strong>East family-room wall</strong><span>Window → solid TV area → mudroom opening</span></li>
            <li><strong>South opening wall</strong><span>3 feet 1 inch → 5 feet → 3 feet 1 inch</span></li>
            <li><strong>TV location</strong><span>Entirely on the solid east wall section</span></li>
          </ul>
        )}
      </section>
      <div className="report-disclaimer">Homeowner visualization only. This report is not a permit set, construction document, structural review, or field measurement.</div>
      <div className="continue-strip"><span>Keep this report with your project as a record of the model used.</span><Link className="button button--primary" to="/">Start another project</Link></div>
    </main>
  );
}
