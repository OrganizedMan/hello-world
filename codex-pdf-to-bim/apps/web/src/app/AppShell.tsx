import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { HelpTooltip } from "../components/HelpTooltip";


const workflow = ["Plans", "Review", "Model", "Render", "Report"];


export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="app-shell">
      <header className="topbar">
        <Link className="brand" to="/" aria-label="HearthView home">
          <span className="brand__mark" aria-hidden="true">H</span>
          <span>
            <strong>HearthView</strong>
            <small>Plans to home, clearly.</small>
          </span>
        </Link>
        <div className="local-badge">
          <span className="local-badge__pulse" aria-hidden="true" />
          Local &amp; private
          <HelpTooltip label="How local processing works">
            Your PDF is processed by the local service and never uploaded.
          </HelpTooltip>
        </div>
      </header>
      <nav className="workflow-nav" aria-label="Project workflow">
        <ol>
          {workflow.map((step, index) => (
            <li key={step}>
              <span>{index + 1}</span>
              {step}
            </li>
          ))}
        </ol>
      </nav>
      {children}
      <footer className="app-footer">
        <span>HearthView preview</span>
        <span>Not for permits, construction, or field verification.</span>
      </footer>
    </div>
  );
}
