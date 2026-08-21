import type { TraceRecordResponse } from "../../api/types";


export function traceRecordLabel(record: TraceRecordResponse) {
  return `${record.room.replaceAll("_", " ")} ${record.kind}`;
}


export function provenanceLabel(value: TraceRecordResponse["provenance"]) {
  return value === "dimension_verified"
    ? "Dimension verified"
    : value === "linework_traced"
      ? "Linework traced"
      : "Ambiguous";
}
