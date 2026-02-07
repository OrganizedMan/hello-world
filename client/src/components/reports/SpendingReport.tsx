import { useState, useEffect } from 'react';
import { api } from '../../hooks/useApi';
import { formatCurrency } from '../../utils/format';
import { getCurrentMonth, getMonthName, getPreviousMonth, getNextMonth } from '../../utils/dates';

export default function SpendingReport() {
  const [month, setMonth] = useState(getCurrentMonth());
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.getSpendingReport({ month })
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [month]);

  if (loading) return <div className="page-loading"><div className="spinner" /></div>;
  if (!data) return <div className="empty-state">Could not load report.</div>;

  const { spending, totalSpent } = data;

  return (
    <div className="report">
      <div className="month-nav">
        <button className="btn btn-ghost" onClick={() => setMonth(getPreviousMonth(month))}>←</button>
        <h3>{getMonthName(month)}</h3>
        <button className="btn btn-ghost" onClick={() => setMonth(getNextMonth(month))}>→</button>
      </div>

      <div className="report-summary-cards">
        <div className="summary-card negative">
          <div className="summary-label">Total Spending</div>
          <div className="summary-value">{formatCurrency(totalSpent)}</div>
        </div>
      </div>

      {spending.length > 0 ? (
        <div className="spending-breakdown">
          {spending.map((group: any) => (
            <div key={group.name} className="spending-group">
              <div className="spending-group-header">
                <span className="spending-group-name">{group.name}</span>
                <span className="spending-group-total">{formatCurrency(group.total)}</span>
              </div>
              <div className="spending-bar-container">
                <div
                  className="spending-bar"
                  style={{ width: `${totalSpent > 0 ? (group.total / totalSpent) * 100 : 0}%` }}
                />
              </div>
              {group.categories.map((cat: any) => (
                <div key={cat.category_id} className="detail-row indent">
                  <span>{cat.category_name}</span>
                  <span>{formatCurrency(cat.total_spent)}</span>
                </div>
              ))}
            </div>
          ))}
        </div>
      ) : (
        <div className="empty-state">No spending data for this month.</div>
      )}
    </div>
  );
}
