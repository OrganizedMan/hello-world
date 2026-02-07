import { useState } from 'react';
import { api } from '../../hooks/useApi';
import { formatCurrency } from '../../utils/format';
import { getMonthName } from '../../utils/dates';

interface Props {
  month: string;
  onClose: () => void;
  onApplied: () => void;
}

export default function AutoBudget({ month, onClose, onApplied }: Props) {
  const [strategy, setStrategy] = useState('last_month_budgeted');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<any[] | null>(null);

  async function handleApply() {
    setLoading(true);
    try {
      const data = await api.autoBudget(month, strategy);
      setResults(data.allocated);
      onApplied();
    } catch (err: any) {
      alert(err.message);
    } finally {
      setLoading(false);
    }
  }

  const strategies = [
    { value: 'last_month_budgeted', label: "Last Month's Budgeted Amounts" },
    { value: 'last_month_spent', label: "Last Month's Spending" },
    { value: 'average_budgeted', label: 'Average Budgeted Amount' },
    { value: 'average_spent', label: 'Average Monthly Spending' },
    { value: 'goal', label: 'Fund Goals' },
  ];

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <h3>Auto-Budget for {getMonthName(month)}</h3>

        {!results ? (
          <>
            <div className="form-group">
              <label>Strategy:</label>
              {strategies.map(s => (
                <label key={s.value} className="radio-option">
                  <input
                    type="radio"
                    name="strategy"
                    value={s.value}
                    checked={strategy === s.value}
                    onChange={() => setStrategy(s.value)}
                  />
                  {s.label}
                </label>
              ))}
            </div>

            <div className="modal-actions">
              <button className="btn btn-primary" onClick={handleApply} disabled={loading}>
                {loading ? 'Applying...' : 'Apply'}
              </button>
              <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
            </div>
          </>
        ) : (
          <>
            <div className="auto-budget-results">
              {results.length === 0 ? (
                <p>No categories were updated.</p>
              ) : (
                <ul>
                  {results.map((r: any) => (
                    <li key={r.category_id}>
                      {r.name}: {formatCurrency(r.amount)}
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className="modal-actions">
              <button className="btn btn-primary" onClick={onClose}>Done</button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
