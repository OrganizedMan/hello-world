import { useState, useRef, useEffect } from 'react';
import { formatCurrency, formatCurrencyInput } from '../../utils/format';
import { api } from '../../hooks/useApi';

interface Props {
  category: any;
  onAllocate: (categoryId: string, amount: number) => void;
  onDelete: () => void;
  onCover: () => void;
  onUpdated: () => void;
}

export default function CategoryRow({ category, onAllocate, onDelete, onCover, onUpdated }: Props) {
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState('');
  const [showGoalEdit, setShowGoalEdit] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.select();
    }
  }, [editing]);

  function startEdit() {
    setEditValue(formatCurrencyInput(category.budgeted));
    setEditing(true);
  }

  function commitEdit() {
    const val = parseFloat(editValue) || 0;
    onAllocate(category.id, val);
    setEditing(false);
  }

  const avail = category.available;
  const availClass = avail < 0 ? 'negative' : avail > 0 ? 'positive' : 'zero';
  const goal = category.goalProgress;

  return (
    <>
      <div className="category-row">
        <div className="col-category">
          <span className="category-name">{category.name}</span>
          {goal && (
            <div className="goal-progress-bar">
              <div
                className={`goal-fill ${goal.complete ? 'complete' : goal.percentage >= 50 ? 'partial' : 'low'}`}
                style={{ width: `${Math.min(100, goal.percentage)}%` }}
              />
            </div>
          )}
          <div className="category-actions">
            {category.available < 0 && (
              <button className="btn btn-ghost btn-xs" onClick={onCover} title="Cover overspending">Cover</button>
            )}
            <button className="btn btn-ghost btn-xs" onClick={() => setShowGoalEdit(!showGoalEdit)} title="Set goal">Goal</button>
            <button className="btn btn-ghost btn-xs btn-danger-hover" onClick={onDelete} title="Delete">×</button>
          </div>
        </div>
        <div className="col-budgeted" onClick={startEdit}>
          {editing ? (
            <input
              ref={inputRef}
              type="number"
              step="0.01"
              value={editValue}
              onChange={e => setEditValue(e.target.value)}
              onBlur={commitEdit}
              onKeyDown={e => {
                if (e.key === 'Enter') commitEdit();
                if (e.key === 'Escape') setEditing(false);
              }}
              className="budget-input"
            />
          ) : (
            <span className="budget-value clickable">{formatCurrency(category.budgeted)}</span>
          )}
        </div>
        <div className="col-activity">{formatCurrency(category.activity)}</div>
        <div className={`col-available ${availClass}`}>
          {formatCurrency(avail)}
        </div>
      </div>

      {goal && (
        <div className="goal-detail">
          {goal.type === 'target_balance' && (
            <span>{formatCurrency(goal.current)} of {formatCurrency(goal.target)} — {goal.needed > 0 ? `${formatCurrency(goal.needed)} needed` : 'Funded!'}</span>
          )}
          {goal.type === 'target_by_date' && (
            <span>{formatCurrency(goal.neededPerMonth)}/mo needed — {goal.monthsLeft} months left</span>
          )}
          {goal.type === 'monthly_funding' && (
            <span>{formatCurrency(goal.funded)} of {formatCurrency(goal.target)} funded this month</span>
          )}
          {goal.type === 'monthly_spending' && (
            <span>{formatCurrency(goal.funded)} of {formatCurrency(goal.target)} budgeted for spending</span>
          )}
        </div>
      )}

      {showGoalEdit && (
        <GoalEditor
          category={category}
          onSave={() => { setShowGoalEdit(false); onUpdated(); }}
          onCancel={() => setShowGoalEdit(false)}
        />
      )}
    </>
  );
}

function GoalEditor({ category, onSave, onCancel }: { category: any; onSave: () => void; onCancel: () => void }) {
  const [goalType, setGoalType] = useState(category.goal_type || '');
  const [goalAmount, setGoalAmount] = useState(category.goal_amount ? (category.goal_amount / 100).toString() : '');
  const [goalDate, setGoalDate] = useState(category.goal_target_date || '');

  async function handleSave() {
    try {
      await api.updateCategory(category.id, {
        goal_type: goalType || null,
        goal_amount: goalAmount ? parseFloat(goalAmount) : null,
        goal_target_date: goalDate || null,
      });
      onSave();
    } catch (err: any) {
      alert(err.message);
    }
  }

  return (
    <div className="goal-editor">
      <div className="form-row">
        <select value={goalType} onChange={e => setGoalType(e.target.value)}>
          <option value="">No Goal</option>
          <option value="target_balance">Target Balance</option>
          <option value="target_by_date">Target by Date</option>
          <option value="monthly_funding">Monthly Funding</option>
          <option value="monthly_spending">Monthly Spending Target</option>
        </select>
      </div>
      {goalType && (
        <div className="form-row">
          <input
            type="number"
            step="0.01"
            placeholder="Amount"
            value={goalAmount}
            onChange={e => setGoalAmount(e.target.value)}
          />
        </div>
      )}
      {goalType === 'target_by_date' && (
        <div className="form-row">
          <input type="date" value={goalDate} onChange={e => setGoalDate(e.target.value)} />
        </div>
      )}
      <div className="form-row form-actions">
        <button className="btn btn-primary btn-sm" onClick={handleSave}>Save</button>
        <button className="btn btn-ghost btn-sm" onClick={onCancel}>Cancel</button>
      </div>
    </div>
  );
}
