import { Router, Response } from 'express';
import { v4 as uuidv4 } from 'uuid';
import db from '../database';
import { authMiddleware, AuthRequest } from '../auth';

const router = Router();
router.use(authMiddleware);

// Get all category groups with categories
router.get('/', (req: AuthRequest, res: Response) => {
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

  const result = groups.map(group => ({
    ...group,
    categories: categories.filter(c => c.group_id === group.id),
  }));

  res.json({ categoryGroups: result });
});

// Create category group
router.post('/groups', (req: AuthRequest, res: Response) => {
  const { name } = req.body;
  if (!name) {
    return res.status(400).json({ error: 'Name is required' });
  }

  const id = uuidv4();
  const maxOrder = db.prepare('SELECT MAX(sort_order) as m FROM category_groups WHERE user_id = ?').get(req.userId) as any;

  db.prepare('INSERT INTO category_groups (id, user_id, name, sort_order) VALUES (?, ?, ?, ?)').run(
    id, req.userId, name, (maxOrder?.m ?? -1) + 1
  );

  const group = db.prepare('SELECT * FROM category_groups WHERE id = ?').get(id);
  res.status(201).json({ group });
});

// Update category group
router.put('/groups/:id', (req: AuthRequest, res: Response) => {
  const { name, sort_order, hidden } = req.body;
  const group = db.prepare('SELECT * FROM category_groups WHERE id = ? AND user_id = ?').get(req.params.id, req.userId);
  if (!group) {
    return res.status(404).json({ error: 'Category group not found' });
  }

  db.prepare(`
    UPDATE category_groups SET
      name = COALESCE(?, name),
      sort_order = COALESCE(?, sort_order),
      hidden = COALESCE(?, hidden)
    WHERE id = ?
  `).run(name ?? null, sort_order ?? null, hidden ?? null, req.params.id);

  const updated = db.prepare('SELECT * FROM category_groups WHERE id = ?').get(req.params.id);
  res.json({ group: updated });
});

// Delete category group
router.delete('/groups/:id', (req: AuthRequest, res: Response) => {
  const group = db.prepare('SELECT * FROM category_groups WHERE id = ? AND user_id = ?').get(req.params.id, req.userId) as any;
  if (!group) {
    return res.status(404).json({ error: 'Category group not found' });
  }
  if (group.is_income) {
    return res.status(400).json({ error: 'Cannot delete income group' });
  }

  db.transaction(() => {
    const cats = db.prepare('SELECT id FROM categories WHERE group_id = ?').all(req.params.id) as any[];
    for (const cat of cats) {
      db.prepare('DELETE FROM budget_allocations WHERE category_id = ?').run(cat.id);
      db.prepare("UPDATE transactions SET category_id = NULL WHERE category_id = ?").run(cat.id);
    }
    db.prepare('DELETE FROM categories WHERE group_id = ?').run(req.params.id);
    db.prepare('DELETE FROM category_groups WHERE id = ?').run(req.params.id);
  })();

  res.json({ success: true });
});

// Create category
router.post('/', (req: AuthRequest, res: Response) => {
  const { name, group_id, goal_type, goal_amount, goal_target_date, goal_cadence } = req.body;

  if (!name || !group_id) {
    return res.status(400).json({ error: 'Name and group_id are required' });
  }

  const group = db.prepare('SELECT * FROM category_groups WHERE id = ? AND user_id = ?').get(group_id, req.userId);
  if (!group) {
    return res.status(404).json({ error: 'Category group not found' });
  }

  const id = uuidv4();
  const maxOrder = db.prepare('SELECT MAX(sort_order) as m FROM categories WHERE group_id = ?').get(group_id) as any;

  db.prepare(`
    INSERT INTO categories (id, group_id, user_id, name, sort_order, goal_type, goal_amount, goal_target_date, goal_cadence)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
  `).run(
    id, group_id, req.userId, name, (maxOrder?.m ?? -1) + 1,
    goal_type ?? null, goal_amount ? Math.round(goal_amount * 100) : null,
    goal_target_date ?? null, goal_cadence ?? 'monthly'
  );

  const category = db.prepare('SELECT * FROM categories WHERE id = ?').get(id);
  res.status(201).json({ category });
});

// Update category
router.put('/:id', (req: AuthRequest, res: Response) => {
  const { name, sort_order, group_id, hidden, goal_type, goal_amount, goal_target_date, goal_cadence } = req.body;

  const category = db.prepare('SELECT * FROM categories WHERE id = ? AND user_id = ?').get(req.params.id, req.userId);
  if (!category) {
    return res.status(404).json({ error: 'Category not found' });
  }

  db.prepare(`
    UPDATE categories SET
      name = COALESCE(?, name),
      sort_order = COALESCE(?, sort_order),
      group_id = COALESCE(?, group_id),
      hidden = COALESCE(?, hidden),
      goal_type = ?,
      goal_amount = ?,
      goal_target_date = ?,
      goal_cadence = COALESCE(?, goal_cadence)
    WHERE id = ?
  `).run(
    name ?? null, sort_order ?? null, group_id ?? null, hidden ?? null,
    goal_type ?? null, goal_amount != null ? Math.round(goal_amount * 100) : null,
    goal_target_date ?? null, goal_cadence ?? null, req.params.id
  );

  const updated = db.prepare('SELECT * FROM categories WHERE id = ?').get(req.params.id);
  res.json({ category: updated });
});

// Delete category
router.delete('/:id', (req: AuthRequest, res: Response) => {
  const category = db.prepare('SELECT * FROM categories WHERE id = ? AND user_id = ?').get(req.params.id, req.userId) as any;
  if (!category) {
    return res.status(404).json({ error: 'Category not found' });
  }

  db.transaction(() => {
    db.prepare('DELETE FROM budget_allocations WHERE category_id = ?').run(req.params.id);
    db.prepare("UPDATE transactions SET category_id = NULL WHERE category_id = ?").run(req.params.id);
    db.prepare('DELETE FROM categories WHERE id = ?').run(req.params.id);
  })();

  res.json({ success: true });
});

export default router;
