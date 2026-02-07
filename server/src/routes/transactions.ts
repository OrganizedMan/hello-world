import { Router, Response } from 'express';
import { v4 as uuidv4 } from 'uuid';
import db from '../database';
import { authMiddleware, AuthRequest } from '../auth';

const router = Router();
router.use(authMiddleware);

// Get transactions with optional filters
router.get('/', (req: AuthRequest, res: Response) => {
  const { account_id, category_id, start_date, end_date, limit = '50', offset = '0' } = req.query;

  let where = 'WHERE t.user_id = ?';
  const params: any[] = [req.userId];

  if (account_id) {
    where += ' AND t.account_id = ?';
    params.push(account_id);
  }
  if (category_id) {
    where += ' AND t.category_id = ?';
    params.push(category_id);
  }
  if (start_date) {
    where += ' AND t.date >= ?';
    params.push(start_date);
  }
  if (end_date) {
    where += ' AND t.date <= ?';
    params.push(end_date);
  }

  params.push(Number(limit), Number(offset));

  const transactions = db.prepare(`
    SELECT t.*,
      a.name as account_name,
      a.type as account_type,
      c.name as category_name,
      ta.name as transfer_account_name
    FROM transactions t
    LEFT JOIN accounts a ON t.account_id = a.id
    LEFT JOIN categories c ON t.category_id = c.id
    LEFT JOIN accounts ta ON t.transfer_account_id = ta.id
    ${where}
    ORDER BY t.date DESC, t.created_at DESC
    LIMIT ? OFFSET ?
  `).all(...params);

  const countResult = db.prepare(`
    SELECT COUNT(*) as total FROM transactions t ${where}
  `).get(...params.slice(0, -2)) as any;

  res.json({ transactions, total: countResult.total });
});

// Create transaction
router.post('/', (req: AuthRequest, res: Response) => {
  const { account_id, category_id, date, payee, memo, amount, cleared, transfer_account_id } = req.body;

  if (!account_id || !date || amount === undefined) {
    return res.status(400).json({ error: 'account_id, date, and amount are required' });
  }

  const account = db.prepare('SELECT * FROM accounts WHERE id = ? AND user_id = ?').get(account_id, req.userId) as any;
  if (!account) {
    return res.status(404).json({ error: 'Account not found' });
  }

  const amountCents = Math.round(amount * 100);

  const result = db.transaction(() => {
    const id = uuidv4();

    // Handle credit card spending: when spending on a credit card,
    // auto-move budgeted funds from the spending category to the CC payment category
    if (account.type === 'credit_card' && amountCents < 0 && category_id) {
      const ccPaymentCat = db.prepare(`
        SELECT id FROM categories WHERE linked_account_id = ? AND user_id = ?
      `).get(account_id, req.userId) as any;

      if (ccPaymentCat) {
        const month = date.substring(0, 7);
        // Get or create the CC payment allocation for this month
        const existingAlloc = db.prepare(`
          SELECT * FROM budget_allocations WHERE category_id = ? AND month = ?
        `).get(ccPaymentCat.id, month) as any;

        const moveAmount = Math.abs(amountCents);

        if (existingAlloc) {
          db.prepare(`
            UPDATE budget_allocations SET amount = amount + ? WHERE id = ?
          `).run(moveAmount, existingAlloc.id);
        } else {
          db.prepare(`
            INSERT INTO budget_allocations (id, user_id, category_id, month, amount)
            VALUES (?, ?, ?, ?, ?)
          `).run(uuidv4(), req.userId, ccPaymentCat.id, month, moveAmount);
        }

        // Reduce the spending category allocation
        const spendAlloc = db.prepare(`
          SELECT * FROM budget_allocations WHERE category_id = ? AND month = ?
        `).get(category_id, month) as any;

        if (spendAlloc) {
          db.prepare(`
            UPDATE budget_allocations SET amount = amount - ? WHERE id = ?
          `).run(moveAmount, spendAlloc.id);
        } else {
          db.prepare(`
            INSERT INTO budget_allocations (id, user_id, category_id, month, amount)
            VALUES (?, ?, ?, ?, ?)
          `).run(uuidv4(), req.userId, category_id, month, -moveAmount);
        }
      }
    }

    // Handle transfers between accounts
    let transferTxId = null;
    if (transfer_account_id) {
      const transferAccount = db.prepare('SELECT * FROM accounts WHERE id = ? AND user_id = ?').get(transfer_account_id, req.userId);
      if (!transferAccount) {
        throw new Error('Transfer account not found');
      }

      transferTxId = uuidv4();

      // Create the matching transfer transaction
      db.prepare(`
        INSERT INTO transactions (id, user_id, account_id, date, payee, memo, amount, cleared, approved, transfer_account_id, transfer_transaction_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
      `).run(transferTxId, req.userId, transfer_account_id, date,
        `Transfer: ${account.name}`, memo || null, -amountCents, cleared ? 1 : 0,
        account_id, id);
    }

    // Update payee memory
    if (payee && category_id) {
      db.prepare(`
        INSERT INTO payees (id, user_id, name, last_category_id)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id, name) DO UPDATE SET last_category_id = ?
      `).run(uuidv4(), req.userId, payee, category_id, category_id);
    }

    db.prepare(`
      INSERT INTO transactions (id, user_id, account_id, category_id, date, payee, memo, amount, cleared, approved, transfer_account_id, transfer_transaction_id)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
    `).run(id, req.userId, account_id, category_id || null, date, payee || null, memo || null,
      amountCents, cleared ? 1 : 0, transfer_account_id || null, transferTxId);

    // Update account balance
    db.prepare('UPDATE accounts SET balance = balance + ? WHERE id = ?').run(amountCents, account_id);
    if (cleared) {
      db.prepare('UPDATE accounts SET cleared_balance = cleared_balance + ? WHERE id = ?').run(amountCents, account_id);
    }

    return db.prepare(`
      SELECT t.*, a.name as account_name, c.name as category_name
      FROM transactions t
      LEFT JOIN accounts a ON t.account_id = a.id
      LEFT JOIN categories c ON t.category_id = c.id
      WHERE t.id = ?
    `).get(id);
  })();

  res.status(201).json({ transaction: result });
});

// Update transaction
router.put('/:id', (req: AuthRequest, res: Response) => {
  const { category_id, date, payee, memo, amount, cleared } = req.body;

  const existing = db.prepare('SELECT * FROM transactions WHERE id = ? AND user_id = ?').get(req.params.id, req.userId) as any;
  if (!existing) {
    return res.status(404).json({ error: 'Transaction not found' });
  }

  const newAmountCents = amount !== undefined ? Math.round(amount * 100) : existing.amount;
  const amountDiff = newAmountCents - existing.amount;
  const newCleared = cleared !== undefined ? (cleared ? 1 : 0) : existing.cleared;
  const clearedDiff = newCleared !== existing.cleared;

  db.transaction(() => {
    db.prepare(`
      UPDATE transactions SET
        category_id = COALESCE(?, category_id),
        date = COALESCE(?, date),
        payee = COALESCE(?, payee),
        memo = COALESCE(?, memo),
        amount = ?,
        cleared = ?
      WHERE id = ?
    `).run(category_id ?? null, date ?? null, payee ?? null, memo ?? null, newAmountCents, newCleared, req.params.id);

    // Update account balance if amount changed
    if (amountDiff !== 0) {
      db.prepare('UPDATE accounts SET balance = balance + ? WHERE id = ?').run(amountDiff, existing.account_id);
    }
    if (clearedDiff || amountDiff !== 0) {
      if (clearedDiff && newCleared) {
        db.prepare('UPDATE accounts SET cleared_balance = cleared_balance + ? WHERE id = ?').run(newAmountCents, existing.account_id);
      } else if (clearedDiff && !newCleared) {
        db.prepare('UPDATE accounts SET cleared_balance = cleared_balance - ? WHERE id = ?').run(existing.amount, existing.account_id);
      } else if (newCleared) {
        db.prepare('UPDATE accounts SET cleared_balance = cleared_balance + ? WHERE id = ?').run(amountDiff, existing.account_id);
      }
    }
  })();

  const updated = db.prepare(`
    SELECT t.*, a.name as account_name, c.name as category_name
    FROM transactions t
    LEFT JOIN accounts a ON t.account_id = a.id
    LEFT JOIN categories c ON t.category_id = c.id
    WHERE t.id = ?
  `).get(req.params.id);

  res.json({ transaction: updated });
});

// Delete transaction
router.delete('/:id', (req: AuthRequest, res: Response) => {
  const existing = db.prepare('SELECT * FROM transactions WHERE id = ? AND user_id = ?').get(req.params.id, req.userId) as any;
  if (!existing) {
    return res.status(404).json({ error: 'Transaction not found' });
  }

  db.transaction(() => {
    // Update account balance
    db.prepare('UPDATE accounts SET balance = balance - ? WHERE id = ?').run(existing.amount, existing.account_id);
    if (existing.cleared) {
      db.prepare('UPDATE accounts SET cleared_balance = cleared_balance - ? WHERE id = ?').run(existing.amount, existing.account_id);
    }

    // Delete paired transfer transaction
    if (existing.transfer_transaction_id) {
      const paired = db.prepare('SELECT * FROM transactions WHERE id = ?').get(existing.transfer_transaction_id) as any;
      if (paired) {
        db.prepare('UPDATE accounts SET balance = balance - ? WHERE id = ?').run(paired.amount, paired.account_id);
        if (paired.cleared) {
          db.prepare('UPDATE accounts SET cleared_balance = cleared_balance - ? WHERE id = ?').run(paired.amount, paired.account_id);
        }
        db.prepare('DELETE FROM transactions WHERE id = ?').run(paired.id);
      }
    }

    db.prepare('DELETE FROM transactions WHERE id = ?').run(req.params.id);
  })();

  res.json({ success: true });
});

// Get payees for autocomplete
router.get('/payees', (req: AuthRequest, res: Response) => {
  const payees = db.prepare(`
    SELECT p.*, c.name as category_name
    FROM payees p
    LEFT JOIN categories c ON p.last_category_id = c.id
    WHERE p.user_id = ?
    ORDER BY p.name
  `).all(req.userId);
  res.json({ payees });
});

export default router;
