import { useState, useEffect, useCallback } from 'react';
import { api } from '../../hooks/useApi';
import { formatCurrency } from '../../utils/format';
import { formatDate, getToday } from '../../utils/dates';
import TransactionForm from './TransactionForm';

export default function TransactionsPage() {
  const [transactions, setTransactions] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [accounts, setAccounts] = useState<any[]>([]);
  const [categories, setCategories] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [filterAccount, setFilterAccount] = useState('');
  const [page, setPage] = useState(0);
  const pageSize = 50;

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {
        limit: String(pageSize),
        offset: String(page * pageSize),
      };
      if (filterAccount) params.account_id = filterAccount;

      const [txData, accData, catData] = await Promise.all([
        api.getTransactions(params),
        api.getAccounts(),
        api.getCategories(),
      ]);
      setTransactions(txData.transactions);
      setTotal(txData.total);
      setAccounts(accData.accounts);
      const allCats = catData.categoryGroups.flatMap((g: any) =>
        g.categories.map((c: any) => ({ ...c, groupName: g.name }))
      );
      setCategories(allCats);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [filterAccount, page]);

  useEffect(() => { loadData(); }, [loadData]);

  async function handleDelete(id: string) {
    if (!confirm('Delete this transaction?')) return;
    try {
      await api.deleteTransaction(id);
      await loadData();
    } catch (err: any) {
      alert(err.message);
    }
  }

  async function handleToggleCleared(tx: any) {
    try {
      await api.updateTransaction(tx.id, { cleared: !tx.cleared });
      await loadData();
    } catch (err: any) {
      alert(err.message);
    }
  }

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="transactions-page">
      <div className="page-header">
        <h2>Transactions</h2>
        <div className="page-header-actions">
          <select
            value={filterAccount}
            onChange={e => { setFilterAccount(e.target.value); setPage(0); }}
            className="filter-select"
          >
            <option value="">All Accounts</option>
            {accounts.map(a => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>
          <button className="btn btn-primary" onClick={() => setShowAdd(true)}>
            + Add Transaction
          </button>
        </div>
      </div>

      {showAdd && (
        <TransactionForm
          accounts={accounts}
          categories={categories}
          onSaved={() => { setShowAdd(false); loadData(); }}
          onCancel={() => setShowAdd(false)}
        />
      )}

      {loading && !transactions.length ? (
        <div className="page-loading"><div className="spinner" /></div>
      ) : (
        <>
          <div className="transactions-list">
            <div className="tx-header">
              <div className="tx-col-date">Date</div>
              <div className="tx-col-payee">Payee</div>
              <div className="tx-col-category">Category</div>
              <div className="tx-col-memo hide-mobile">Memo</div>
              <div className="tx-col-amount">Amount</div>
              <div className="tx-col-actions">C</div>
            </div>

            {transactions.map(tx => (
              editingId === tx.id ? (
                <TransactionForm
                  key={tx.id}
                  transaction={tx}
                  accounts={accounts}
                  categories={categories}
                  onSaved={() => { setEditingId(null); loadData(); }}
                  onCancel={() => setEditingId(null)}
                />
              ) : (
                <div key={tx.id} className={`tx-row ${tx.cleared ? 'cleared' : ''}`}>
                  <div className="tx-col-date">{formatDate(tx.date)}</div>
                  <div className="tx-col-payee" onClick={() => setEditingId(tx.id)}>
                    {tx.transfer_account_id
                      ? `Transfer: ${tx.transfer_account_name || 'Account'}`
                      : tx.payee || '—'}
                  </div>
                  <div className="tx-col-category">{tx.category_name || '—'}</div>
                  <div className="tx-col-memo hide-mobile">{tx.memo || ''}</div>
                  <div className={`tx-col-amount ${tx.amount >= 0 ? 'positive' : 'negative'}`}>
                    {formatCurrency(tx.amount)}
                  </div>
                  <div className="tx-col-actions">
                    <button
                      className={`btn-clear ${tx.cleared ? 'is-cleared' : ''}`}
                      onClick={() => handleToggleCleared(tx)}
                      title={tx.cleared ? 'Cleared' : 'Uncleared'}
                    >
                      {tx.cleared ? '✓' : '○'}
                    </button>
                    <button className="btn btn-ghost btn-xs btn-danger-hover" onClick={() => handleDelete(tx.id)}>×</button>
                  </div>
                </div>
              )
            ))}

            {transactions.length === 0 && (
              <div className="empty-state">No transactions yet. Add one to get started!</div>
            )}
          </div>

          {totalPages > 1 && (
            <div className="pagination">
              <button className="btn btn-ghost btn-sm" onClick={() => setPage(p => p - 1)} disabled={page === 0}>
                ← Prev
              </button>
              <span className="page-info">Page {page + 1} of {totalPages}</span>
              <button className="btn btn-ghost btn-sm" onClick={() => setPage(p => p + 1)} disabled={page >= totalPages - 1}>
                Next →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
