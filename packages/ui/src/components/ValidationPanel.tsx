import type { ValidationReport } from '../types'

const STATUS_LABEL: Record<string, string> = { pass: 'PASS', warn: 'WARN', block: 'BLOCK' }

export function ValidationPanel({ report, geometryHash }: { report: ValidationReport; geometryHash: string }) {
  return (
    <div className="panel validation-panel" data-testid="validation-panel">
      <h2>Validation report</h2>
      <p className={`overall-status ${report.is_blocking ? 'blocking' : 'clear'}`} data-testid="overall-status">
        {report.is_blocking ? 'BLOCKED — cannot render' : 'Not blocking — model built and locked'}
      </p>
      <ul className="check-list">
        {report.checks.map((c) => (
          <li key={c.check_id} className={`check-row status-${c.status}`}>
            <span className="badge">{STATUS_LABEL[c.status]}</span>
            <span className="check-id">{c.check_id}</span>
            <span className="check-message">{c.message}</span>
            {c.details.length > 0 && (
              <ul className="check-details">
                {c.details.map((d, i) => (
                  <li key={i}>{d}</li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>
      <div className="geometry-hash" data-testid="geometry-hash">
        <span className="label">geometry_hash</span>
        <code>{geometryHash}</code>
      </div>
    </div>
  )
}
