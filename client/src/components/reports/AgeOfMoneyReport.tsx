import { useState, useEffect } from 'react';
import { api } from '../../hooks/useApi';
import { formatCurrency } from '../../utils/format';

export default function AgeOfMoneyReport() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getAgeOfMoneyReport()
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="page-loading"><div className="spinner" /></div>;
  if (!data) return <div className="empty-state">Could not load report.</div>;

  const { currentAge, totalCash, avgDailySpending } = data;

  return (
    <div className="report">
      <div className="report-summary-cards">
        <div className="summary-card highlight">
          <div className="summary-label">Age of Money</div>
          <div className="summary-value large">{currentAge} days</div>
        </div>
        <div className="summary-card">
          <div className="summary-label">Total Cash</div>
          <div className="summary-value">{formatCurrency(totalCash)}</div>
        </div>
        <div className="summary-card">
          <div className="summary-label">Avg Daily Spending</div>
          <div className="summary-value">{formatCurrency(Math.round(avgDailySpending))}</div>
        </div>
      </div>

      <div className="age-explanation">
        <h3>What is Age of Money?</h3>
        <p>
          Age of Money tells you how long your dollars sit in your accounts before you spend them.
          The higher the number, the more financial buffer you have. A common goal is 30+ days,
          meaning you're spending money you earned at least a month ago.
        </p>
        <ul>
          <li><strong>0–14 days:</strong> Living paycheck to paycheck</li>
          <li><strong>14–30 days:</strong> Building a buffer</li>
          <li><strong>30+ days:</strong> Solid financial footing</li>
          <li><strong>60+ days:</strong> Strong financial health</li>
        </ul>
      </div>

      {data.history?.length > 0 && (
        <div className="chart-section">
          <h3>Age of Money Trend</h3>
          <div className="bar-chart">
            {data.history.map((point: any) => {
              const maxAge = Math.max(...data.history.map((h: any) => h.ageOfMoney), 1);
              return (
                <div key={point.month} className="chart-bar-group">
                  <div className="chart-bars">
                    <div
                      className={`chart-bar age ${point.ageOfMoney >= 30 ? 'good' : point.ageOfMoney >= 14 ? 'ok' : 'low'}`}
                      style={{ height: `${Math.max(2, (point.ageOfMoney / maxAge) * 150)}px` }}
                      title={`${point.ageOfMoney} days`}
                    />
                  </div>
                  <div className="chart-label">{point.month.slice(5)}</div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
