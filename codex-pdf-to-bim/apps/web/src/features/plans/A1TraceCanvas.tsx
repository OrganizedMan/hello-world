import type { KeyboardEvent } from "react";

import type { A1TraceResponse, TraceRecordResponse } from "../../api/types";


export type TraceMode = "pdf" | "trace" | "overlay";
export type ProvenanceFilter = "all" | "dimension_verified" | "linework_traced" | "ambiguous";

type A1TraceCanvasProps = {
  trace: A1TraceResponse;
  mode: TraceMode;
  provenanceFilter: ProvenanceFilter;
  selectedId: string | null;
  onSelect: (record: TraceRecordResponse) => void;
};


function points(record: TraceRecordResponse) {
  return record.geometry.points.map(([x, y]) => `${x},${y}`).join(" ");
}


function selectOnKey(event: KeyboardEvent<SVGPolygonElement>, record: TraceRecordResponse, onSelect: (record: TraceRecordResponse) => void) {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    onSelect(record);
  }
}


export function A1TraceCanvas({ trace, mode, provenanceFilter, selectedId, onSelect }: A1TraceCanvasProps) {
  const { x0, y0, x1, y1 } = trace.proposed_crop;
  const visible = mode !== "pdf";
  const records = provenanceFilter === "all"
    ? trace.records
    : trace.records.filter((record) => record.provenance === provenanceFilter);

  return (
    <svg
      aria-label="A-1 proposed-plan trace"
      className={`a1-trace-canvas a1-trace-canvas--${mode}`}
      viewBox={`${x0} ${y0} ${x1 - x0} ${y1 - y0}`}
      preserveAspectRatio="xMidYMid meet"
      aria-hidden={!visible}
    >
      {visible ? records.map((record) => (
        <polygon
          aria-label={`${record.room} ${record.kind}, ${record.provenance.replace("_", "-")}`}
          className={`a1-trace-canvas__record a1-trace-canvas__record--${record.kind}${selectedId === record.id ? " is-selected" : ""}`}
          data-provenance={record.provenance}
          data-testid={`trace-${record.id}`}
          key={record.id}
          points={points(record)}
          role="button"
          tabIndex={0}
          onClick={() => onSelect(record)}
          onKeyDown={(event) => selectOnKey(event, record, onSelect)}
        />
      )) : null}
    </svg>
  );
}
