import { useState } from 'react';
import { api } from '../../hooks/useApi';
import { formatCurrency } from '../../utils/format';

interface Props {
  month: string;
  category: any;
  categories: any[];
  onClose: () => void;
  onCovered: () => void;
}

export default function CoverOverspending({ month, category, categories, onClose, onCovered }: Props) {
  const overspent = Math.abs(category.available);
  const [fromCategoryId, setFromCategoryId] = useState('');
  const [amount, setAmount] = useState((overspent / 100).toFixed(2));
  const [loading, setLoading] = useState(false);

  const availableCategories = categories.filter(c =>
    c.id !== category.id && c.available > 0
  );

  async function handleCover() {
    if (!fromCategoryId || !amount) return;
    setLoading(true);
    try {
      await api.coverOverspending(month, fromCategoryId, category.id, parseFloat(amount));
      onCovered();
      onClose();
    } catch (err: any) {
      alert(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <h3>Cover Overspending</h3>
        <p className="modal-subtitle">
          <strong>{category.name}</strong> is overspent by {formatCurrency(overspent)}
        </p>

        <div className="form-group">
          <label>Move money from:</label>
          <select value={fromCategoryId} onChange={e => setFromCategoryId(e.target.value)}>
            <option value="">Select a category...</option>
            {availableCategories.map(c => (
              <option key={c.id} value={c.id}>
                {c.name} (Available: {formatCurrency(c.available)})
              </option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label>Amount to move:</label>
          <input
            type="number"
            step="0.01"
            value={amount}
            onChange={e => setAmount(e.target.value)}
          />
        </div>

        <div className="modal-actions">
          <button className="btn btn-primary" onClick={handleCover} disabled={loading || !fromCategoryId}>
            {loading ? 'Moving...' : 'Move Money'}
          </button>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
        </div>
      </div>
    </div>
  );
}
