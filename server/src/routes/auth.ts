import { Router, Request, Response } from 'express';
import bcrypt from 'bcryptjs';
import { v4 as uuidv4 } from 'uuid';
import db from '../database';
import { generateToken, authMiddleware, AuthRequest } from '../auth';

const router = Router();

router.post('/register', (req: Request, res: Response) => {
  const { email, password, name } = req.body;

  if (!email || !password || !name) {
    return res.status(400).json({ error: 'Email, password, and name are required' });
  }

  if (password.length < 8) {
    return res.status(400).json({ error: 'Password must be at least 8 characters' });
  }

  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(email)) {
    return res.status(400).json({ error: 'Invalid email format' });
  }

  const existing = db.prepare('SELECT id FROM users WHERE email = ?').get(email.toLowerCase());
  if (existing) {
    return res.status(409).json({ error: 'Email already registered' });
  }

  const userId = uuidv4();
  const passwordHash = bcrypt.hashSync(password, 12);

  db.prepare('INSERT INTO users (id, email, password_hash, name) VALUES (?, ?, ?, ?)').run(
    userId,
    email.toLowerCase(),
    passwordHash,
    name
  );

  // Create default category groups and categories
  const setupDefaults = db.transaction(() => {
    const groups = [
      { name: 'Immediate Obligations', categories: ['Rent/Mortgage', 'Electric', 'Water', 'Internet', 'Phone', 'Insurance'] },
      { name: 'True Expenses', categories: ['Auto Maintenance', 'Home Maintenance', 'Medical', 'Clothing', 'Gifts'] },
      { name: 'Debt Payments', categories: [] },
      { name: 'Quality of Life', categories: ['Groceries', 'Dining Out', 'Entertainment', 'Personal Care', 'Education'] },
      { name: 'Savings Goals', categories: ['Emergency Fund', 'Vacation', 'Retirement'] },
    ];

    groups.forEach((group, gi) => {
      const groupId = uuidv4();
      db.prepare('INSERT INTO category_groups (id, user_id, name, sort_order) VALUES (?, ?, ?, ?)').run(
        groupId, userId, group.name, gi
      );
      group.categories.forEach((cat, ci) => {
        db.prepare('INSERT INTO categories (id, group_id, user_id, name, sort_order) VALUES (?, ?, ?, ?, ?)').run(
          uuidv4(), groupId, userId, cat, ci
        );
      });
    });

    // Create "Ready to Assign" as a special income group
    const incomeGroupId = uuidv4();
    db.prepare('INSERT INTO category_groups (id, user_id, name, is_income, sort_order) VALUES (?, ?, ?, 1, -1)').run(
      incomeGroupId, userId, 'Income'
    );
    db.prepare('INSERT INTO categories (id, group_id, user_id, name, sort_order) VALUES (?, ?, ?, ?, ?)').run(
      uuidv4(), incomeGroupId, userId, 'Ready to Assign', 0
    );
  });

  setupDefaults();

  const token = generateToken(userId);
  res.status(201).json({ token, user: { id: userId, email: email.toLowerCase(), name } });
});

router.post('/login', (req: Request, res: Response) => {
  const { email, password } = req.body;

  if (!email || !password) {
    return res.status(400).json({ error: 'Email and password are required' });
  }

  const user = db.prepare('SELECT id, email, password_hash, name FROM users WHERE email = ?').get(email.toLowerCase()) as any;
  if (!user) {
    return res.status(401).json({ error: 'Invalid credentials' });
  }

  if (!bcrypt.compareSync(password, user.password_hash)) {
    return res.status(401).json({ error: 'Invalid credentials' });
  }

  const token = generateToken(user.id);
  res.json({ token, user: { id: user.id, email: user.email, name: user.name } });
});

router.get('/me', authMiddleware, (req: AuthRequest, res: Response) => {
  const user = db.prepare('SELECT id, email, name, created_at FROM users WHERE id = ?').get(req.userId) as any;
  if (!user) {
    return res.status(404).json({ error: 'User not found' });
  }
  res.json({ user });
});

export default router;
