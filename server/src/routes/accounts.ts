import { Router, Response } from 'express';
import { v4 as uuidv4 } from 'uuid';
import db from '../database';
import { authMiddleware, AuthRequest } from '../auth';

const router = Router();
router.use(authMiddleware);

router.get('/', (req: AuthRequest, res: Response) => {
  const accounts = db.prepare(`
    SELECT a.*,
      COALESCE((SELECT SUM(t.amount) FROM transactions t WHERE t.account_id = a.id), 0) as working_balance
    FROM accounts a
    WHERE a.user_id = ? AND a.is_closed = 0
    ORDER BY a.sort_order, a.name
  `).all(req.userId);
  res.json({ accounts });
});

router.post('/', (req: AuthRequest, res: Response) => {
  const { name, type, balance } = req.body;

  if (!name || !type) {
    return res.status(400).json({ error: 'Name and type are required' });
  }

  const validTypes = ['checking', 'savings', 'credit_card', 'cash', 'investment', 'mortgage', 'loan', 'other'];
  if (!validTypes.includes(type)) {
    return res.status(400).json({ error: 'Invalid account type' });
  }

  const id = uuidv4();
  const initialBalance = Math.round((balance || 0) * 100); // Store as cents

  const isBudget = ['checking', 'savings', 'credit_card', 'cash'].includes(type) ? 1 : 0;

  const result = db.transaction(() => {
    const maxOrder = db.prepare('SELECT MAX(sort_order) as max_order FROM accounts WHERE user_id = ?').get(req.userId) as any;

    db.prepare(`
      INSERT INTO accounts (id, user_id, name, type, balance, cleared_balance, is_budget, sort_order)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `).run(id, req.userId, name, type, initialBalance, initialBalance, isBudget, (maxOrder?.max_order ?? -1) + 1);

    // For credit cards, always create the payment category
    if (type === 'credit_card') {
      const debtGroup = db.prepare(
        "SELECT id FROM category_groups WHERE user_id = ? AND name = 'Debt Payments'"
      ).get(req.userId) as any;

      if (debtGroup) {
        const catId = uuidv4();
        db.prepare(`
          INSERT INTO categories (id, group_id, user_id, name, sort_order, is_credit_card_payment, linked_account_id)
          VALUES (?, ?, ?, ?, ?, 1, ?)
        `).run(catId, debtGroup.id, req.userId, `${name} Payment`, 0, id);
      }
    }

    // Create initial balance transaction
    if (initialBalance !== 0) {
      const txId = uuidv4();
      const today = new Date().toISOString().split('T')[0];

      db.prepare(`
        INSERT INTO transactions (id, user_id, account_id, date, payee, amount, cleared, approved)
        VALUES (?, ?, ?, ?, ?, ?, 1, 1)
      `).run(txId, req.userId, id, today, 'Starting Balance', initialBalance);
    }

    return db.prepare('SELECT * FROM accounts WHERE id = ?').get(id);
  })();

  res.status(201).json({ account: result });
});

router.put('/:id', (req: AuthRequest, res: Response) => {
  const { name, is_closed, sort_order } = req.body;
  const account = db.prepare('SELECT * FROM accounts WHERE id = ? AND user_id = ?').get(req.params.id, req.userId) as any;

  if (!account) {
    return res.status(404).json({ error: 'Account not found' });
  }

  db.prepare(`
    UPDATE accounts SET
      name = COALESCE(?, name),
      is_closed = COALESCE(?, is_closed),
      sort_order = COALESCE(?, sort_order)
    WHERE id = ? AND user_id = ?
  `).run(name ?? null, is_closed ?? null, sort_order ?? null, req.params.id, req.userId);

  const updated = db.prepare('SELECT * FROM accounts WHERE id = ?').get(req.params.id);
  res.json({ account: updated });
});

router.delete('/:id', (req: AuthRequest, res: Response) => {
  const account = db.prepare('SELECT * FROM accounts WHERE id = ? AND user_id = ?').get(req.params.id, req.userId);
  if (!account) {
    return res.status(404).json({ error: 'Account not found' });
  }

  db.transaction(() => {
    db.prepare('DELETE FROM transactions WHERE account_id = ?').run(req.params.id);
    db.prepare('DELETE FROM accounts WHERE id = ?').run(req.params.id);
  })();

  res.json({ success: true });
});

export default router;
