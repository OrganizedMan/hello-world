type ProjectStatus = "READY_TO_VIEW" | "NEEDS_INPUT" | "CONFLICTING_INFORMATION" | "PREVIEW_ONLY";


type StatusBannerProps = {
  status: ProjectStatus;
  remaining?: number;
};


const statusCopy: Record<ProjectStatus, { title: string; body: (remaining?: number) => string }> = {
  READY_TO_VIEW: {
    title: "Ready to view",
    body: () => "Your confirmed drawing details are ready to build in 3D.",
  },
  NEEDS_INPUT: {
    title: "Needs your input",
    body: (remaining) => `${remaining ?? 0} drawing details left to confirm`,
  },
  CONFLICTING_INFORMATION: {
    title: "Conflicting information",
    body: () => "Two drawing details disagree. Review them together before building 3D.",
  },
  PREVIEW_ONLY: {
    title: "Preview only",
    body: () => "You can explore this model, but final rendering remains locked.",
  },
};


export function StatusBanner({ status, remaining }: StatusBannerProps) {
  const copy = statusCopy[status];
  return (
    <section className={`status-banner status-banner--${status.toLowerCase()}`} role="status">
      <span className="status-banner__dot" aria-hidden="true" />
      <span>
        <strong>{copy.title}</strong>
        <span>{copy.body(remaining)}</span>
      </span>
    </section>
  );
}
