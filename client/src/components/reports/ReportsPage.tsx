import { useState } from 'react';
import NetWorthReport from './NetWorthReport';
import SpendingReport from './SpendingReport';
import IncomeExpenseReport from './IncomeExpenseReport';
import AgeOfMoneyReport from './AgeOfMoneyReport';

type ReportTab = 'net-worth' | 'spending' | 'income-expense' | 'age-of-money';

export default function ReportsPage() {
  const [tab, setTab] = useState<ReportTab>('net-worth');

  const tabs: { key: ReportTab; label: string }[] = [
    { key: 'net-worth', label: 'Net Worth' },
    { key: 'spending', label: 'Spending' },
    { key: 'income-expense', label: 'Income vs Expense' },
    { key: 'age-of-money', label: 'Age of Money' },
  ];

  return (
    <div className="reports-page">
      <div className="page-header">
        <h2>Reports</h2>
      </div>

      <div className="report-tabs">
        {tabs.map(t => (
          <button
            key={t.key}
            className={`tab-btn ${tab === t.key ? 'active' : ''}`}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="report-content">
        {tab === 'net-worth' && <NetWorthReport />}
        {tab === 'spending' && <SpendingReport />}
        {tab === 'income-expense' && <IncomeExpenseReport />}
        {tab === 'age-of-money' && <AgeOfMoneyReport />}
      </div>
    </div>
  );
}
