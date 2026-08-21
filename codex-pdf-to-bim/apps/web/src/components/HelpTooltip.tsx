import { type ReactNode, useId, useState } from "react";


type HelpTooltipProps = {
  label: string;
  children: ReactNode;
};


export function HelpTooltip({ label, children }: HelpTooltipProps) {
  const [open, setOpen] = useState(false);
  const tooltipId = useId();

  return (
    <span
      className="help-tooltip"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <button
        type="button"
        className="help-tooltip__trigger"
        aria-label={label}
        aria-describedby={open ? tooltipId : undefined}
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            setOpen(false);
          }
        }}
      >
        ?
      </button>
      {open ? (
        <span className="help-tooltip__content" id={tooltipId} role="tooltip">
          {children}
        </span>
      ) : null}
    </span>
  );
}
