import { Router, Response } from 'express';
import db from '../database';
import { authMiddleware, AuthRequest } from '../auth';

const router = Router();
router.use(authMiddleware);

// Net worth report
router.get('/net-worth', (req: AuthRequest, res: Response) => {
  const { start_date, end_date } = req.query;

  // Get all accounts with their current balances
  const accounts = db.prepare(`
    SELECT a.id, a.name, a.type,
      COALESCE((SELECT SUM(t.amount) FROM transactions t WHERE t.account_id = a.id), 0) as balance
    FROM accounts a
    WHERE a.user_id = ? AND a.is_closed = 0
    ORDER BY a.type, a.name
  `).all(req.userId) as any[];

  const assets = accounts.filter(a => !['credit_card', 'loan', 'mortgage'].includes(a.type));
  const liabilities = accounts.filter(a => ['credit_card', 'loan', 'mortgage'].includes(a.type));

  const totalAssets = assets.reduce((sum, a) => sum + a.balance, 0);
  const totalLiabilities = liabilities.reduce((sum, a) => sum + Math.abs(a.balance), 0);
  const netWorth = totalAssets - totalLiabilities;

  // Net worth over time (monthly snapshots)
  const months = db.prepare(`
    SELECT DISTINCT substr(date, 1, 7) as month
    FROM transactions
    WHERE user_id = ?
    ORDER BY month
  `).all(req.userId) as any[];

  const timeline = months.map(m => {
    const endOfMonth = `${m.month}-31`;
    const monthAccounts = db.prepare(`
      SELECT a.id, a.type,
        COALESCE((SELECT SUM(t.amount) FROM transactions t WHERE t.account_id = a.id AND t.date <= ?), 0) as balance
      FROM accounts a
      WHERE a.user_id = ? AND a.is_closed = 0
    `).all(endOfMonth, req.userId) as any[];

    const mAssets = monthAccounts.filter(a => !['credit_card', 'loan', 'mortgage'].includes(a.type));
    const mLiab = monthAccounts.filter(a => ['credit_card', 'loan', 'mortgage'].includes(a.type));

    return {
      month: m.month,
      assets: mAssets.reduce((s, a) => s + a.balance, 0),
      liabilities: mLiab.reduce((s, a) => s + Math.abs(a.balance), 0),
      netWorth: mAssets.reduce((s, a) => s + a.balance, 0) - mLiab.reduce((s, a) => s + Math.abs(a.balance), 0),
    };
  });

  res.json({
    accounts: { assets, liabilities },
    totals: { assets: totalAssets, liabilities: totalLiabilities, netWorth },
    timeline,
  });
});

// Spending report by category
router.get('/spending', (req: AuthRequest, res: Response) => {
  const { month, start_date, end_date } = req.query;

  let dateFilter: string;
  let params: any[];

  if (month) {
    dateFilter = "AND t.date >= ? AND t.date <= ?";
    params = [req.userId, `${month}-01`, `${month}-31`];
  } else if (start_date && end_date) {
    dateFilter = "AND t.date >= ? AND t.date <= ?";
    params = [req.userId, start_date, end_date];
  } else {
    // Default: current month
    const now = new Date();
    const currentMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
    dateFilter = "AND t.date >= ? AND t.date <= ?";
    params = [req.userId, `${currentMonth}-01`, `${currentMonth}-31`];
  }

  const spending = db.prepare(`
    SELECT
      cg.name as group_name,
      c.id as category_id,
      c.name as category_name,
      SUM(CASE WHEN t.amount < 0 THEN ABS(t.amount) ELSE 0 END) as total_spent,
      COUNT(*) as transaction_count
    FROM transactions t
    JOIN categories c ON t.category_id = c.id
    JOIN category_groups cg ON c.group_id = cg.id
    WHERE t.user_id = ? ${dateFilter} AND t.amount < 0 AND cg.is_income = 0
    GROUP BY c.id
    ORDER BY total_spent DESC
  `).all(...params) as any[];

  const totalSpent = spending.reduce((sum, s) => sum + s.total_spent, 0);

  // Group by category group
  const grouped: Record<string, any> = {};
  for (const item of spending) {
    if (!grouped[item.group_name]) {
      grouped[item.group_name] = { name: item.group_name, total: 0, categories: [] };
    }
    grouped[item.group_name].total += item.total_spent;
    grouped[item.group_name].categories.push(item);
  }

  // Monthly spending trend
  const trend = db.prepare(`
    SELECT substr(t.date, 1, 7) as month,
      SUM(CASE WHEN t.amount < 0 THEN ABS(t.amount) ELSE 0 END) as spent,
      SUM(CASE WHEN t.amount > 0 AND cg.is_income = 1 THEN t.amount ELSE 0 END) as income
    FROM transactions t
    LEFT JOIN categories c ON t.category_id = c.id
    LEFT JOIN category_groups cg ON c.group_id = cg.id
    WHERE t.user_id = ?
    GROUP BY month
    ORDER BY month
  `).all(req.userId) as any[];

  res.json({
    spending: Object.values(grouped),
    totalSpent,
    trend,
  });
});

// Income vs Expense report
router.get('/income-expense', (req: AuthRequest, res: Response) => {
  const months = db.prepare(`
    SELECT substr(t.date, 1, 7) as month,
      SUM(CASE WHEN t.amount > 0 THEN t.amount ELSE 0 END) as income,
      SUM(CASE WHEN t.amount < 0 THEN ABS(t.amount) ELSE 0 END) as expenses,
      SUM(t.amount) as net
    FROM transactions t
    WHERE t.user_id = ?
    GROUP BY month
    ORDER BY month
  `).all(req.userId) as any[];

  res.json({ months });
});

// Age of Money report
router.get('/age-of-money', (req: AuthRequest, res: Response) => {
  // Age of Money = how many days ago did you earn the money you're spending today
  // Approximation: total cash on hand / average daily spending over last 30 days

  const cashAccounts = db.prepare(`
    SELECT COALESCE(SUM(balance), 0) as total
    FROM accounts
    WHERE user_id = ? AND type IN ('checking', 'savings', 'cash') AND is_closed = 0
  `).get(req.userId) as any;

  const totalCash = cashAccounts.total;

  // Average daily outflow over the last 30 days
  const thirtyDaysAgo = new Date();
  thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);
  const thirtyDaysAgoStr = thirtyDaysAgo.toISOString().split('T')[0];

  const recentSpending = db.prepare(`
    SELECT COALESCE(SUM(ABS(amount)), 0) as total
    FROM transactions
    WHERE user_id = ? AND amount < 0 AND date >= ?
  `).get(req.userId, thirtyDaysAgoStr) as any;

  const avgDailySpending = recentSpending.total / 30;
  const ageOfMoney = avgDailySpending > 0 ? Math.round(totalCash / avgDailySpending) : 0;

  // Historical age of money
  const history = db.prepare(`
    SELECT DISTINCT substr(date, 1, 7) as month FROM transactions WHERE user_id = ? ORDER BY month
  `).all(req.userId) as any[];

  const ageHistory = history.map(h => {
    const monthEnd = `${h.month}-31`;
    const monthStart = `${h.month}-01`;
    const thirtyBefore = new Date(monthStart);
    thirtyBefore.setDate(thirtyBefore.getDate() - 30);
    const thirtyBeforeStr = thirtyBefore.toISOString().split('T')[0];

    const cash = db.prepare(`
      SELECT COALESCE(SUM(balance), 0) as total FROM accounts
      WHERE user_id = ? AND type IN ('checking', 'savings', 'cash') AND is_closed = 0
    `).get(req.userId) as any;

    const spent = db.prepare(`
      SELECT COALESCE(SUM(ABS(amount)), 0) as total FROM transactions
      WHERE user_id = ? AND amount < 0 AND date >= ? AND date <= ?
    `).get(req.userId, thirtyBeforeStr, monthEnd) as any;

    const dailyAvg = spent.total / 30;
    return {
      month: h.month,
      ageOfMoney: dailyAvg > 0 ? Math.round(cash.total / dailyAvg) : 0,
    };
  });

  res.json({
    currentAge: ageOfMoney,
    totalCash,
    avgDailySpending,
    history: ageHistory,
  });
});

export default router;
