import { useEffect, useState } from "react";


type LengthFieldProps = {
  id: string;
  label: string;
  value: string;
  onCommit: (value: string) => void;
  onDraftChange?: (value: string) => void;
  disabled?: boolean;
};


function looksLikeLength(value: string): boolean {
  const normalized = value.trim();
  const feetAndInches = /^\d+\s*['′]\s*-?\s*\d+(?:\.\d+)?\s*(?:["″]|in(?:ches)?)?$/i;
  const inches = /^\d+(?:\.\d+)?\s*(?:["″]|in(?:ches)?)$/i;
  const millimetres = /^\d+(?:\.\d+)?\s*mm$/i;
  return feetAndInches.test(normalized) || inches.test(normalized) || millimetres.test(normalized);
}


export function LengthField({ id, label, value, onCommit, onDraftChange, disabled = false }: LengthFieldProps) {
  const [draft, setDraft] = useState(value);
  const [error, setError] = useState<string | null>(null);
  const helpId = `${id}-help`;
  const errorId = `${id}-error`;

  useEffect(() => setDraft(value), [value]);

  function commit() {
    if (!looksLikeLength(draft)) {
      setError('Use a length such as 5\' 0", 60 in, or 1524 mm.');
      return;
    }
    setError(null);
    onCommit(draft.trim());
  }

  return (
    <div className="field length-field">
      <label htmlFor={id}>{label}</label>
      <div className="length-field__control">
        <input
          id={id}
          value={draft}
          disabled={disabled}
          aria-describedby={`${helpId}${error ? ` ${errorId}` : ""}`}
          aria-invalid={error ? "true" : undefined}
          inputMode="decimal"
          onChange={(event) => {
            setDraft(event.target.value);
            onDraftChange?.(event.target.value);
            if (error) setError(null);
          }}
          onBlur={commit}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              commit();
            }
          }}
        />
        <span className="length-field__unit" aria-hidden="true">ft / in</span>
      </div>
      <small id={helpId}>Enter feet and inches, for example 8&apos;-7&quot;.</small>
      {error ? <span className="field__error" id={errorId} role="alert">{error}</span> : null}
    </div>
  );
}
