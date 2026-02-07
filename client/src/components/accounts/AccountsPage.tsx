import { useState, useEffect, FormEvent } from 'react';
import { api } from '../../hooks/useApi';
import { formatCurrency } from '../../utils/format';

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [formData, setFormData] = useState({ name: '', type: 'checking', balance: '' });
  const [saving, setSaving] = useState(false);

  async function loadAccounts() {
    setLoading(true);
    try {
      const data = await api.getAccounts();
      setAccounts(data.accounts);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadAccounts(); }, []);

  async function handleAdd(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await api.createAccount({
        name: formData.name,
        type: formData.type,
        balance: parseFloat(formData.balance) || 0,
      });
      setFormData({ name: '', type: 'checking', balance: '' });
      setShowAdd(false);
      await loadAccounts();
    } catch (err: any) {
      alert(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleClose(id: string) {
    if (!confirm('Close this account?')) return;
    try {
      await api.updateAccount(id, { is_closed: 1 });
      await loadAccounts();
    } catch (err: any) {
      alert(err.message);
    }
  }

  async function handleDelete(id: string) {
    if (!confirm('Delete this account and all its transactions? This cannot be undone.')) return;
    try {
      await api.deleteAccount(id);
      await loadAccounts();
    } catch (err: any) {
      alert(err.message);
    }
  }

  const budgetAccounts = accounts.filter(a => a.is_budget);
  const trackingAccounts = accounts.filter(a => !a.is_budget);
  const totalBudget = budgetAccounts.reduce((s, a) => s + a.working_balance, 0);
  const totalTracking = trackingAccounts.reduce((s, a) => s + a.working_balance, 0);

  const accountTypes: Record<string, string> = {
    checking: 'Checking',
    savings: 'Savings',
    credit_card: 'Credit Card',
    cash: 'Cash',
    investment: 'Investment',
    mortgage: 'Mortgage',
    loan: 'Loan',
    other: 'Other',
  };

  if (loading) return <div className="page-loading"><div className="spinner" /></div>;

  return (
    <div className="accounts-page">
      <div className="page-header">
        <h2>Accounts</h2>
        <button className="btn btn-primary" onClick={() => setShowAdd(true)}>+ Add Account</button>
      </div>

      {showAdd && (
        <div className="card add-account-card">
          <h3>Add Account</h3>
          <form onSubmit={handleAdd}>
            <div className="form-group">
              <label>Account Name</label>
              <input
                type="text"
                value={formData.name}
                onChange={e => setFormData({ ...formData, name: e.target.value })}
                required
                autoFocus
              />
            </div>
            <div className="form-group">
              <label>Type</label>
              <select value={formData.type} onChange={e => setFormData({ ...formData, type: e.target.value })}>
                {Object.entries(accountTypes).map(([val, label]) => (
                  <option key={val} value={val}>{label}</option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label>Current Balance</label>
              <input
                type="number"
                step="0.01"
                value={formData.balance}
                onChange={e => setFormData({ ...formData, balance: e.target.value })}
                placeholder="0.00"
              />
              <small>For credit cards, enter as negative (e.g. -500.00)</small>
            </div>
            <div className="form-actions">
              <button type="submit" className="btn btn-primary" disabled={saving}>
                {saving ? 'Adding...' : 'Add Account'}
              </button>
              <button type="button" className="btn btn-ghost" onClick={() => setShowAdd(false)}>Cancel</button>
            </div>
          </form>
        </div>
      )}

      {budgetAccounts.length > 0 && (
        <div className="account-section">
          <div className="account-section-header">
            <h3>Budget Accounts</h3>
            <span className={`section-total ${totalBudget >= 0 ? 'positive' : 'negative'}`}>
              {formatCurrency(totalBudget)}
            </span>
          </div>
          {budgetAccounts.map(account => (
            <AccountCard
              key={account.id}
              account={account}
              typeLabel={accountTypes[account.type] || account.type}
              onClose={() => handleClose(account.id)}
              onDelete={() => handleDelete(account.id)}
            />
          ))}
        </div>
      )}

      {trackingAccounts.length > 0 && (
        <div className="account-section">
          <div className="account-section-header">
            <h3>Tracking Accounts</h3>
            <span className={`section-total ${totalTracking >= 0 ? 'positive' : 'negative'}`}>
              {formatCurrency(totalTracking)}
            </span>
          </div>
          {trackingAccounts.map(account => (
            <AccountCard
              key={account.id}
              account={account}
              typeLabel={accountTypes[account.type] || account.type}
              onClose={() => handleClose(account.id)}
              onDelete={() => handleDelete(account.id)}
            />
          ))}
        </div>
      )}

      {accounts.length === 0 && (
        <div className="empty-state">
          <p>No accounts yet. Add a checking or savings account to start budgeting!</p>
        </div>
      )}
    </div>
  );
}

function AccountCard({ account, typeLabel, onClose, onDelete }: {
  account: any;
  typeLabel: string;
  onClose: () => void;
  onDelete: () => void;
}) {
  return (
    <div className="account-card">
      <div className="account-info">
        <div className="account-name">{account.name}</div>
        <div className="account-type">{typeLabel}</div>
      </div>
      <div className="account-balances">
        <div className={`account-balance ${account.working_balance >= 0 ? 'positive' : 'negative'}`}>
          {formatCurrency(account.working_balance)}
        </div>
        <div className="account-cleared">
          Cleared: {formatCurrency(account.cleared_balance)}
        </div>
      </div>
      <div className="account-actions">
        <button className="btn btn-ghost btn-sm" onClick={onClose}>Close</button>
        <button className="btn btn-ghost btn-sm btn-danger-hover" onClick={onDelete}>Delete</button>
      </div>
    </div>
  );
}
