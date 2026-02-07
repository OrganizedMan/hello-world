import { useState, useEffect } from 'react';
import { api } from '../../hooks/useApi';
import { formatCurrency } from '../../utils/format';
import { getMonthName } from '../../utils/dates';

export default function IncomeExpenseReport() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getIncomeExpenseReport()
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="page-loading"><div className="spinner" /></div>;
  if (!data?.months?.length) return <div className="empty-state">No data yet. Add some transactions!</div>;

  const maxVal = Math.max(...data.months.map((m: any) => Math.max(m.income, m.expenses)), 1);

  const totalIncome = data.months.reduce((s: number, m: any) => s + m.income, 0);
  const totalExpenses = data.months.reduce((s: number, m: any) => s + m.expenses, 0);
  const totalNet = totalIncome - totalExpenses;

  return (
    <div className="report">
      <div className="report-summary-cards">
        <div className="summary-card positive">
          <div className="summary-label">Total Income</div>
          <div className="summary-value">{formatCurrency(totalIncome)}</div>
        </div>
        <div className="summary-card negative">
          <div className="summary-label">Total Expenses</div>
          <div className="summary-value">{formatCurrency(totalExpenses)}</div>
        </div>
        <div className={`summary-card ${totalNet >= 0 ? 'positive' : 'negative'}`}>
          <div className="summary-label">Net</div>
          <div className="summary-value">{formatCurrency(totalNet)}</div>
        </div>
      </div>

      <div className="chart-section">
        <h3>Monthly Income vs Expenses</h3>
        <div className="bar-chart">
          {data.months.map((m: any) => (
            <div key={m.month} className="chart-bar-group">
              <div className="chart-bars">
                <div
                  className="chart-bar income"
                  style={{ height: `${Math.max(2, (m.income / maxVal) * 150)}px` }}
                  title={`Income: ${formatCurrency(m.income)}`}
                />
                <div
                  className="chart-bar expense"
                  style={{ height: `${Math.max(2, (m.expenses / maxVal) * 150)}px` }}
                  title={`Expenses: ${formatCurrency(m.expenses)}`}
                />
              </div>
              <div className="chart-label">{m.month.slice(5)}</div>
            </div>
          ))}
        </div>
        <div className="chart-legend">
          <span className="legend-item"><span className="legend-dot income" /> Income</span>
          <span className="legend-item"><span className="legend-dot expense" /> Expenses</span>
        </div>
      </div>

      <div className="report-details">
        <h3>Monthly Breakdown</h3>
        <div className="detail-table">
          <div className="detail-header">
            <span>Month</span>
            <span>Income</span>
            <span>Expenses</span>
            <span>Net</span>
          </div>
          {data.months.map((m: any) => (
            <div key={m.month} className="detail-row four-col">
              <span>{getMonthName(m.month)}</span>
              <span className="positive">{formatCurrency(m.income)}</span>
              <span className="negative">{formatCurrency(m.expenses)}</span>
              <span className={m.net >= 0 ? 'positive' : 'negative'}>{formatCurrency(m.net)}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
