import { useState, useEffect } from 'react';
import { api } from '../../hooks/useApi';
import { formatCurrency } from '../../utils/format';
import { getMonthName } from '../../utils/dates';

export default function NetWorthReport() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getNetWorthReport()
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="page-loading"><div className="spinner" /></div>;
  if (!data) return <div className="empty-state">Could not load report.</div>;

  const { accounts, totals, timeline } = data;
  const maxVal = Math.max(...timeline.map((t: any) => Math.max(Math.abs(t.assets), Math.abs(t.liabilities), Math.abs(t.netWorth))), 1);

  return (
    <div className="report">
      <div className="report-summary-cards">
        <div className="summary-card positive">
          <div className="summary-label">Total Assets</div>
          <div className="summary-value">{formatCurrency(totals.assets)}</div>
        </div>
        <div className="summary-card negative">
          <div className="summary-label">Total Liabilities</div>
          <div className="summary-value">{formatCurrency(totals.liabilities)}</div>
        </div>
        <div className={`summary-card ${totals.netWorth >= 0 ? 'positive' : 'negative'}`}>
          <div className="summary-label">Net Worth</div>
          <div className="summary-value">{formatCurrency(totals.netWorth)}</div>
        </div>
      </div>

      {timeline.length > 0 && (
        <div className="chart-section">
          <h3>Net Worth Over Time</h3>
          <div className="bar-chart">
            {timeline.map((point: any) => (
              <div key={point.month} className="chart-bar-group">
                <div className="chart-bars">
                  <div
                    className="chart-bar assets"
                    style={{ height: `${Math.max(2, (Math.abs(point.assets) / maxVal) * 150)}px` }}
                    title={`Assets: ${formatCurrency(point.assets)}`}
                  />
                  <div
                    className="chart-bar liabilities"
                    style={{ height: `${Math.max(2, (Math.abs(point.liabilities) / maxVal) * 150)}px` }}
                    title={`Liabilities: ${formatCurrency(point.liabilities)}`}
                  />
                  <div
                    className={`chart-bar net-worth ${point.netWorth >= 0 ? 'positive' : 'negative'}`}
                    style={{ height: `${Math.max(2, (Math.abs(point.netWorth) / maxVal) * 150)}px` }}
                    title={`Net Worth: ${formatCurrency(point.netWorth)}`}
                  />
                </div>
                <div className="chart-label">{point.month.slice(5)}</div>
              </div>
            ))}
          </div>
          <div className="chart-legend">
            <span className="legend-item"><span className="legend-dot assets" /> Assets</span>
            <span className="legend-item"><span className="legend-dot liabilities" /> Liabilities</span>
            <span className="legend-item"><span className="legend-dot net-worth" /> Net Worth</span>
          </div>
        </div>
      )}

      <div className="report-details">
        <h3>Assets</h3>
        {accounts.assets.map((a: any) => (
          <div key={a.id} className="detail-row">
            <span>{a.name}</span>
            <span className="positive">{formatCurrency(a.balance)}</span>
          </div>
        ))}

        <h3>Liabilities</h3>
        {accounts.liabilities.map((a: any) => (
          <div key={a.id} className="detail-row">
            <span>{a.name}</span>
            <span className="negative">{formatCurrency(Math.abs(a.balance))}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
