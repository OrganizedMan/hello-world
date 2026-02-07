import { useState, useEffect, useCallback } from 'react';
import { api } from '../../hooks/useApi';
import { formatCurrency } from '../../utils/format';
import { getCurrentMonth, getMonthName, getPreviousMonth, getNextMonth } from '../../utils/dates';
import CategoryRow from './CategoryRow';
import CategoryForm from './CategoryForm';
import CoverOverspending from './CoverOverspending';
import AutoBudget from './AutoBudget';

export default function BudgetPage() {
  const [month, setMonth] = useState(getCurrentMonth());
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [showAddCategory, setShowAddCategory] = useState<string | null>(null);
  const [showAddGroup, setShowAddGroup] = useState(false);
  const [newGroupName, setNewGroupName] = useState('');
  const [showCover, setShowCover] = useState<any>(null);
  const [showAutoBudget, setShowAutoBudget] = useState(false);
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set());

  const loadBudget = useCallback(async () => {
    setLoading(true);
    try {
      const result = await api.getBudget(month);
      setData(result);
    } catch (err) {
      console.error('Failed to load budget:', err);
    } finally {
      setLoading(false);
    }
  }, [month]);

  useEffect(() => { loadBudget(); }, [loadBudget]);

  async function handleAllocate(categoryId: string, amount: number) {
    try {
      await api.allocateBudget(month, categoryId, amount);
      await loadBudget();
    } catch (err: any) {
      alert(err.message);
    }
  }

  async function handleAddGroup() {
    if (!newGroupName.trim()) return;
    try {
      await api.createCategoryGroup({ name: newGroupName.trim() });
      setNewGroupName('');
      setShowAddGroup(false);
      await loadBudget();
    } catch (err: any) {
      alert(err.message);
    }
  }

  async function handleDeleteGroup(groupId: string) {
    if (!confirm('Delete this category group and all its categories?')) return;
    try {
      await api.deleteCategoryGroup(groupId);
      await loadBudget();
    } catch (err: any) {
      alert(err.message);
    }
  }

  async function handleDeleteCategory(categoryId: string) {
    if (!confirm('Delete this category?')) return;
    try {
      await api.deleteCategory(categoryId);
      await loadBudget();
    } catch (err: any) {
      alert(err.message);
    }
  }

  function toggleGroup(groupId: string) {
    setCollapsedGroups(prev => {
      const next = new Set(prev);
      if (next.has(groupId)) next.delete(groupId);
      else next.add(groupId);
      return next;
    });
  }

  if (loading && !data) {
    return <div className="page-loading"><div className="spinner" /></div>;
  }

  const readyToAssign = data?.readyToAssign || 0;
  const rtaClass = readyToAssign > 0 ? 'positive' : readyToAssign < 0 ? 'negative' : 'zero';

  return (
    <div className="budget-page">
      <div className="budget-header">
        <div className="month-nav">
          <button className="btn btn-ghost" onClick={() => setMonth(getPreviousMonth(month))}>←</button>
          <h2 className="month-title">{getMonthName(month)}</h2>
          <button className="btn btn-ghost" onClick={() => setMonth(getNextMonth(month))}>→</button>
        </div>

        <div className={`ready-to-assign ${rtaClass}`}>
          <span className="rta-amount">{formatCurrency(readyToAssign)}</span>
          <span className="rta-label">Ready to Assign</span>
        </div>

        <div className="budget-actions">
          <button className="btn btn-secondary btn-sm" onClick={() => setShowAutoBudget(true)}>
            Auto-Budget
          </button>
          <button className="btn btn-secondary btn-sm" onClick={() => setShowAddGroup(true)}>
            + Group
          </button>
        </div>
      </div>

      {showAutoBudget && (
        <AutoBudget
          month={month}
          onClose={() => setShowAutoBudget(false)}
          onApplied={loadBudget}
        />
      )}

      {showAddGroup && (
        <div className="inline-form">
          <input
            type="text"
            value={newGroupName}
            onChange={e => setNewGroupName(e.target.value)}
            placeholder="Group name"
            autoFocus
            onKeyDown={e => e.key === 'Enter' && handleAddGroup()}
          />
          <button className="btn btn-primary btn-sm" onClick={handleAddGroup}>Add</button>
          <button className="btn btn-ghost btn-sm" onClick={() => setShowAddGroup(false)}>Cancel</button>
        </div>
      )}

      <div className="budget-table">
        <div className="budget-table-header">
          <div className="col-category">Category</div>
          <div className="col-budgeted">Budgeted</div>
          <div className="col-activity">Activity</div>
          <div className="col-available">Available</div>
        </div>

        {data?.categoryGroups
          ?.filter((g: any) => !g.is_income)
          .map((group: any) => {
            const isCollapsed = collapsedGroups.has(group.id);
            const groupBudgeted = group.categories.reduce((s: number, c: any) => s + c.budgeted, 0);
            const groupActivity = group.categories.reduce((s: number, c: any) => s + c.activity, 0);
            const groupAvailable = group.categories.reduce((s: number, c: any) => s + c.available, 0);

            return (
              <div key={group.id} className="category-group">
                <div className="group-header" onClick={() => toggleGroup(group.id)}>
                  <div className="col-category">
                    <span className={`collapse-icon ${isCollapsed ? 'collapsed' : ''}`}>▼</span>
                    <span className="group-name">{group.name}</span>
                    <button
                      className="btn btn-ghost btn-xs"
                      onClick={e => { e.stopPropagation(); setShowAddCategory(group.id); }}
                      title="Add category"
                    >+</button>
                    <button
                      className="btn btn-ghost btn-xs btn-danger-hover"
                      onClick={e => { e.stopPropagation(); handleDeleteGroup(group.id); }}
                      title="Delete group"
                    >×</button>
                  </div>
                  <div className="col-budgeted">{formatCurrency(groupBudgeted)}</div>
                  <div className="col-activity">{formatCurrency(groupActivity)}</div>
                  <div className={`col-available ${groupAvailable < 0 ? 'negative' : groupAvailable > 0 ? 'positive' : ''}`}>
                    {formatCurrency(groupAvailable)}
                  </div>
                </div>

                {showAddCategory === group.id && (
                  <CategoryForm
                    groupId={group.id}
                    onSaved={() => { setShowAddCategory(null); loadBudget(); }}
                    onCancel={() => setShowAddCategory(null)}
                  />
                )}

                {!isCollapsed && group.categories.map((cat: any) => (
                  <CategoryRow
                    key={cat.id}
                    category={cat}
                    onAllocate={handleAllocate}
                    onDelete={() => handleDeleteCategory(cat.id)}
                    onCover={() => setShowCover(cat)}
                    onUpdated={loadBudget}
                  />
                ))}
              </div>
            );
          })}
      </div>

      {showCover && (
        <CoverOverspending
          month={month}
          category={showCover}
          categories={data?.categoryGroups?.flatMap((g: any) => g.categories) || []}
          onClose={() => setShowCover(null)}
          onCovered={loadBudget}
        />
      )}
    </div>
  );
}
