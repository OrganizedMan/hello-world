import { useState, FormEvent } from 'react';
import { api } from '../../hooks/useApi';
import { getToday } from '../../utils/dates';

interface Props {
  transaction?: any;
  accounts: any[];
  categories: any[];
  onSaved: () => void;
  onCancel: () => void;
}

export default function TransactionForm({ transaction, accounts, categories, onSaved, onCancel }: Props) {
  const isEdit = !!transaction;
  const [date, setDate] = useState(transaction?.date || getToday());
  const [accountId, setAccountId] = useState(transaction?.account_id || accounts[0]?.id || '');
  const [payee, setPayee] = useState(transaction?.payee || '');
  const [categoryId, setCategoryId] = useState(transaction?.category_id || '');
  const [memo, setMemo] = useState(transaction?.memo || '');
  const [isOutflow, setIsOutflow] = useState(transaction ? transaction.amount < 0 : true);
  const [amount, setAmount] = useState(
    transaction ? (Math.abs(transaction.amount) / 100).toFixed(2) : ''
  );
  const [cleared, setCleared] = useState(transaction?.cleared || false);
  const [transferAccountId, setTransferAccountId] = useState('');
  const [isTransfer, setIsTransfer] = useState(false);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!accountId || !date) return;

    setLoading(true);
    const amountVal = parseFloat(amount) || 0;
    const signedAmount = isOutflow ? -amountVal : amountVal;

    try {
      if (isEdit) {
        await api.updateTransaction(transaction.id, {
          date,
          payee: isTransfer ? undefined : payee,
          category_id: isTransfer ? undefined : categoryId || null,
          memo,
          amount: signedAmount,
          cleared,
        });
      } else {
        await api.createTransaction({
          account_id: accountId,
          date,
          payee: isTransfer ? undefined : payee,
          category_id: isTransfer ? undefined : categoryId || null,
          memo,
          amount: signedAmount,
          cleared,
          transfer_account_id: isTransfer ? transferAccountId : undefined,
        });
      }
      onSaved();
    } catch (err: any) {
      alert(err.message);
    } finally {
      setLoading(false);
    }
  }

  // Group categories by their group
  const groupedCats: Record<string, any[]> = {};
  categories.forEach(c => {
    if (!groupedCats[c.groupName]) groupedCats[c.groupName] = [];
    groupedCats[c.groupName].push(c);
  });

  return (
    <form className="tx-form" onSubmit={handleSubmit}>
      <div className="tx-form-grid">
        <div className="form-group">
          <label>Date</label>
          <input type="date" value={date} onChange={e => setDate(e.target.value)} required />
        </div>

        <div className="form-group">
          <label>Account</label>
          <select value={accountId} onChange={e => setAccountId(e.target.value)} required disabled={isEdit}>
            <option value="">Select account...</option>
            {accounts.map(a => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label className="checkbox-label">
            <input type="checkbox" checked={isTransfer} onChange={e => setIsTransfer(e.target.checked)} />
            Transfer
          </label>
        </div>

        {isTransfer ? (
          <div className="form-group">
            <label>To/From Account</label>
            <select value={transferAccountId} onChange={e => setTransferAccountId(e.target.value)}>
              <option value="">Select account...</option>
              {accounts.filter(a => a.id !== accountId).map(a => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </select>
          </div>
        ) : (
          <>
            <div className="form-group">
              <label>Payee</label>
              <input type="text" value={payee} onChange={e => setPayee(e.target.value)} placeholder="Payee" />
            </div>

            <div className="form-group">
              <label>Category</label>
              <select value={categoryId} onChange={e => setCategoryId(e.target.value)}>
                <option value="">Uncategorized</option>
                {Object.entries(groupedCats).map(([group, cats]) => (
                  <optgroup key={group} label={group}>
                    {cats.map(c => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </optgroup>
                ))}
              </select>
            </div>
          </>
        )}

        <div className="form-group">
          <label>Memo</label>
          <input type="text" value={memo} onChange={e => setMemo(e.target.value)} placeholder="Memo" />
        </div>

        <div className="form-group amount-group">
          <label>Amount</label>
          <div className="amount-input-row">
            <div className="flow-toggle">
              <button
                type="button"
                className={`flow-btn ${isOutflow ? 'active outflow' : ''}`}
                onClick={() => setIsOutflow(true)}
              >
                Outflow
              </button>
              <button
                type="button"
                className={`flow-btn ${!isOutflow ? 'active inflow' : ''}`}
                onClick={() => setIsOutflow(false)}
              >
                Inflow
              </button>
            </div>
            <input
              type="number"
              step="0.01"
              min="0"
              value={amount}
              onChange={e => setAmount(e.target.value)}
              placeholder="0.00"
              required
            />
          </div>
        </div>

        <div className="form-group">
          <label className="checkbox-label">
            <input type="checkbox" checked={cleared} onChange={e => setCleared(e.target.checked)} />
            Cleared
          </label>
        </div>
      </div>

      <div className="form-actions">
        <button type="submit" className="btn btn-primary" disabled={loading}>
          {loading ? 'Saving...' : isEdit ? 'Update' : 'Add Transaction'}
        </button>
        <button type="button" className="btn btn-ghost" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  );
}
