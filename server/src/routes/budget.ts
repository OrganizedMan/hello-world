import { Router, Response } from 'express';
import { v4 as uuidv4 } from 'uuid';
import db from '../database';
import { authMiddleware, AuthRequest } from '../auth';

const router = Router();
router.use(authMiddleware);

// Get budget for a specific month
router.get('/:month', (req: AuthRequest, res: Response) => {
  const { month } = req.params; // Format: YYYY-MM

  if (!/^\d{4}-\d{2}$/.test(month)) {
    return res.status(400).json({ error: 'Month must be in YYYY-MM format' });
  }

  const groups = db.prepare(`
    SELECT * FROM category_groups
    WHERE user_id = ? AND hidden = 0
    ORDER BY sort_order, name
  `).all(req.userId) as any[];

  const categories = db.prepare(`
    SELECT * FROM categories
    WHERE user_id = ? AND hidden = 0
    ORDER BY sort_order, name
  `).all(req.userId) as any[];

  const allocations = db.prepare(`
    SELECT * FROM budget_allocations
    WHERE user_id = ? AND month = ?
  `).all(req.userId, month) as any[];

  // Calculate activity (spending) for each category this month
  const monthStart = `${month}-01`;
  const monthEnd = `${month}-31`; // Works for all months since SQLite compares strings

  const activity = db.prepare(`
    SELECT category_id, SUM(amount) as total
    FROM transactions
    WHERE user_id = ? AND date >= ? AND date <= ? AND category_id IS NOT NULL
    GROUP BY category_id
  `).all(req.userId, monthStart, monthEnd) as any[];

  const activityMap = new Map(activity.map(a => [a.category_id, a.total]));
  const allocationMap = new Map(allocations.map(a => [a.category_id, a.amount]));

  // Calculate cumulative available (all prior months allocated + activity)
  const priorAllocations = db.prepare(`
    SELECT category_id, SUM(amount) as total
    FROM budget_allocations
    WHERE user_id = ? AND month < ?
    GROUP BY category_id
  `).all(req.userId, month) as any[];

  const priorActivity = db.prepare(`
    SELECT category_id, SUM(amount) as total
    FROM transactions
    WHERE user_id = ? AND date < ? AND category_id IS NOT NULL
    GROUP BY category_id
  `).all(req.userId, monthStart) as any[];

  const priorAllocMap = new Map(priorAllocations.map(a => [a.category_id, a.total]));
  const priorActMap = new Map(priorActivity.map(a => [a.category_id, a.total]));

  // Calculate total income (all months up to and including this one)
  const totalIncome = db.prepare(`
    SELECT COALESCE(SUM(t.amount), 0) as total
    FROM transactions t
    JOIN categories c ON t.category_id = c.id
    JOIN category_groups cg ON c.group_id = cg.id
    WHERE t.user_id = ? AND t.date <= ? AND cg.is_income = 1
  `).get(req.userId, monthEnd) as any;

  // Calculate total budgeted (all months up to and including this one)
  const totalBudgeted = db.prepare(`
    SELECT COALESCE(SUM(ba.amount), 0) as total
    FROM budget_allocations ba
    JOIN categories c ON ba.category_id = c.id
    JOIN category_groups cg ON c.group_id = cg.id
    WHERE ba.user_id = ? AND ba.month <= ? AND cg.is_income = 0
  `).get(req.userId, month) as any;

  const readyToAssign = totalIncome.total - totalBudgeted.total;

  // Build response
  const categoryGroups = groups.map(group => {
    const groupCats = categories.filter(c => c.group_id === group.id);
    return {
      ...group,
      categories: groupCats.map(cat => {
        const budgeted = allocationMap.get(cat.id) || 0;
        const activityAmount = activityMap.get(cat.id) || 0;
        const priorBudgeted = priorAllocMap.get(cat.id) || 0;
        const priorActivityAmount = priorActMap.get(cat.id) || 0;
        const available = priorBudgeted + budgeted + priorActivityAmount + activityAmount;

        // Calculate goal progress
        let goalProgress = null;
        if (cat.goal_type) {
          goalProgress = calculateGoalProgress(cat, budgeted, available, month);
        }

        return {
          ...cat,
          budgeted,
          activity: activityAmount,
          available,
          goalProgress,
        };
      }),
    };
  });

  res.json({ month, categoryGroups, readyToAssign });
});

function calculateGoalProgress(cat: any, budgeted: number, available: number, currentMonth: string) {
  const goalAmount = cat.goal_amount || 0;

  switch (cat.goal_type) {
    case 'target_balance': {
      const percentage = goalAmount > 0 ? Math.min(100, Math.round((available / goalAmount) * 100)) : 0;
      const needed = Math.max(0, goalAmount - available);
      return { type: 'target_balance', target: goalAmount, current: available, percentage, needed, complete: available >= goalAmount };
    }
    case 'target_by_date': {
      const targetDate = cat.goal_target_date;
      const monthsLeft = monthDiff(currentMonth, targetDate?.substring(0, 7) || currentMonth);
      const neededPerMonth = monthsLeft > 0 ? Math.ceil(Math.max(0, goalAmount - available + budgeted) / monthsLeft) : goalAmount;
      const percentage = goalAmount > 0 ? Math.min(100, Math.round((available / goalAmount) * 100)) : 0;
      return {
        type: 'target_by_date', target: goalAmount, current: available, percentage,
        targetDate, monthsLeft, neededPerMonth, funded: budgeted >= neededPerMonth, complete: available >= goalAmount,
      };
    }
    case 'monthly_funding': {
      const percentage = goalAmount > 0 ? Math.min(100, Math.round((budgeted / goalAmount) * 100)) : 0;
      const needed = Math.max(0, goalAmount - budgeted);
      return { type: 'monthly_funding', target: goalAmount, funded: budgeted, percentage, needed, complete: budgeted >= goalAmount };
    }
    case 'monthly_spending': {
      const percentage = goalAmount > 0 ? Math.min(100, Math.round((budgeted / goalAmount) * 100)) : 0;
      return { type: 'monthly_spending', target: goalAmount, funded: budgeted, percentage, needed: Math.max(0, goalAmount - budgeted), complete: budgeted >= goalAmount };
    }
    default:
      return null;
  }
}

function monthDiff(from: string, to: string): number {
  const [fy, fm] = from.split('-').map(Number);
  const [ty, tm] = to.split('-').map(Number);
  return (ty - fy) * 12 + (tm - fm);
}

// Set budget allocation for a category in a month
router.post('/:month/allocate', (req: AuthRequest, res: Response) => {
  const { month } = req.params;
  const { category_id, amount } = req.body;

  if (!category_id || amount === undefined) {
    return res.status(400).json({ error: 'category_id and amount are required' });
  }

  const amountCents = Math.round(amount * 100);

  const existing = db.prepare(`
    SELECT * FROM budget_allocations WHERE category_id = ? AND month = ? AND user_id = ?
  `).get(category_id, month, req.userId);

  if (existing) {
    db.prepare('UPDATE budget_allocations SET amount = ? WHERE category_id = ? AND month = ?').run(amountCents, category_id, month);
  } else {
    db.prepare(`
      INSERT INTO budget_allocations (id, user_id, category_id, month, amount)
      VALUES (?, ?, ?, ?, ?)
    `).run(uuidv4(), req.userId, category_id, month, amountCents);
  }

  res.json({ success: true, category_id, month, amount: amountCents });
});

// Auto-budget: fill based on last month's spending or average budgeted
router.post('/:month/auto-budget', (req: AuthRequest, res: Response) => {
  const { month } = req.params;
  const { strategy, category_ids } = req.body;
  // strategy: 'last_month_budgeted' | 'last_month_spent' | 'average_budgeted' | 'average_spent' | 'goal'

  if (!strategy) {
    return res.status(400).json({ error: 'Strategy is required' });
  }

  const categories = category_ids
    ? db.prepare(`SELECT * FROM categories WHERE user_id = ? AND id IN (${category_ids.map(() => '?').join(',')})`)
        .all(req.userId, ...category_ids) as any[]
    : db.prepare(`
        SELECT c.* FROM categories c
        JOIN category_groups cg ON c.group_id = cg.id
        WHERE c.user_id = ? AND cg.is_income = 0 AND c.hidden = 0
      `).all(req.userId) as any[];

  const [year, mon] = month.split('-').map(Number);
  const prevMonth = `${mon === 1 ? year - 1 : year}-${String(mon === 1 ? 12 : mon - 1).padStart(2, '0')}`;

  const results = db.transaction(() => {
    const allocated: any[] = [];

    for (const cat of categories) {
      let amount = 0;

      switch (strategy) {
        case 'last_month_budgeted': {
          const prev = db.prepare('SELECT amount FROM budget_allocations WHERE category_id = ? AND month = ?').get(cat.id, prevMonth) as any;
          amount = prev?.amount || 0;
          break;
        }
        case 'last_month_spent': {
          const prevStart = `${prevMonth}-01`;
          const prevEnd = `${prevMonth}-31`;
          const spent = db.prepare('SELECT COALESCE(SUM(ABS(amount)), 0) as total FROM transactions WHERE category_id = ? AND date >= ? AND date <= ? AND amount < 0').get(cat.id, prevStart, prevEnd) as any;
          amount = spent?.total || 0;
          break;
        }
        case 'average_budgeted': {
          const avg = db.prepare('SELECT AVG(amount) as avg_amount FROM budget_allocations WHERE category_id = ? AND month < ?').get(cat.id, month) as any;
          amount = Math.round(avg?.avg_amount || 0);
          break;
        }
        case 'average_spent': {
          const avgSpent = db.prepare(`
            SELECT AVG(monthly_total) as avg_amount FROM (
              SELECT substr(date, 1, 7) as m, SUM(ABS(amount)) as monthly_total
              FROM transactions
              WHERE category_id = ? AND amount < 0 AND date < ?
              GROUP BY m
            )
          `).get(cat.id, `${month}-01`) as any;
          amount = Math.round(avgSpent?.avg_amount || 0);
          break;
        }
        case 'goal': {
          if (cat.goal_type && cat.goal_amount) {
            if (cat.goal_type === 'monthly_funding' || cat.goal_type === 'monthly_spending') {
              amount = cat.goal_amount;
            } else if (cat.goal_type === 'target_by_date' && cat.goal_target_date) {
              const monthsLeft = monthDiff(month, cat.goal_target_date.substring(0, 7));
              const available = calculateAvailable(cat.id, req.userId!, month);
              amount = monthsLeft > 0 ? Math.ceil(Math.max(0, cat.goal_amount - available) / monthsLeft) : Math.max(0, cat.goal_amount - available);
            } else if (cat.goal_type === 'target_balance') {
              const available = calculateAvailable(cat.id, req.userId!, month);
              amount = Math.max(0, cat.goal_amount - available);
            }
          }
          break;
        }
      }

      if (amount > 0) {
        const existing = db.prepare('SELECT * FROM budget_allocations WHERE category_id = ? AND month = ?').get(cat.id, month);
        if (existing) {
          db.prepare('UPDATE budget_allocations SET amount = ? WHERE category_id = ? AND month = ?').run(amount, cat.id, month);
        } else {
          db.prepare('INSERT INTO budget_allocations (id, user_id, category_id, month, amount) VALUES (?, ?, ?, ?, ?)').run(
            uuidv4(), req.userId, cat.id, month, amount
          );
        }
        allocated.push({ category_id: cat.id, name: cat.name, amount });
      }
    }

    return allocated;
  })();

  res.json({ success: true, allocated: results });
});

function calculateAvailable(categoryId: string, userId: string, upToMonth: string): number {
  const alloc = db.prepare('SELECT COALESCE(SUM(amount), 0) as total FROM budget_allocations WHERE category_id = ? AND user_id = ? AND month <= ?').get(categoryId, userId, upToMonth) as any;
  const spent = db.prepare("SELECT COALESCE(SUM(amount), 0) as total FROM transactions WHERE category_id = ? AND user_id = ? AND date <= ?").get(categoryId, userId, `${upToMonth}-31`) as any;
  return (alloc?.total || 0) + (spent?.total || 0);
}

// Cover overspending: move money from one category to another
router.post('/:month/cover', (req: AuthRequest, res: Response) => {
  const { month } = req.params;
  const { from_category_id, to_category_id, amount } = req.body;

  if (!from_category_id || !to_category_id || !amount) {
    return res.status(400).json({ error: 'from_category_id, to_category_id, and amount are required' });
  }

  const amountCents = Math.round(amount * 100);

  db.transaction(() => {
    // Decrease from source category
    const fromAlloc = db.prepare('SELECT * FROM budget_allocations WHERE category_id = ? AND month = ?').get(from_category_id, month) as any;
    if (fromAlloc) {
      db.prepare('UPDATE budget_allocations SET amount = amount - ? WHERE category_id = ? AND month = ?').run(amountCents, from_category_id, month);
    } else {
      db.prepare('INSERT INTO budget_allocations (id, user_id, category_id, month, amount) VALUES (?, ?, ?, ?, ?)').run(
        uuidv4(), req.userId, from_category_id, month, -amountCents
      );
    }

    // Increase to destination category
    const toAlloc = db.prepare('SELECT * FROM budget_allocations WHERE category_id = ? AND month = ?').get(to_category_id, month) as any;
    if (toAlloc) {
      db.prepare('UPDATE budget_allocations SET amount = amount + ? WHERE category_id = ? AND month = ?').run(amountCents, to_category_id, month);
    } else {
      db.prepare('INSERT INTO budget_allocations (id, user_id, category_id, month, amount) VALUES (?, ?, ?, ?, ?)').run(
        uuidv4(), req.userId, to_category_id, month, amountCents
      );
    }
  })();

  res.json({ success: true });
});

export default router;
