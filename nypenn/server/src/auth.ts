import { randomBytes, scryptSync, timingSafeEqual } from 'node:crypto';
import type { NextFunction, Request, Response } from 'express';
import jwt from 'jsonwebtoken';

const TOKEN_TTL = '30d';

/**
 * Two-account auth for a private board.
 *
 * Credentials come from the environment as `user:scrypthash` pairs rather
 * than a database: there are exactly two of us, and a users table would be
 * more moving parts than the problem has.
 */
export interface Account {
  username: string;
  salt: string;
  hash: string;
}

/** Parse NYPENN_USERS, formatted `alice:salt:hash,bob:salt:hash`. */
export function parseAccounts(raw: string | undefined): Account[] {
  if (!raw?.trim()) return [];
  return raw
    .split(',')
    .map((entry) => entry.trim())
    .filter(Boolean)
    .map((entry) => {
      const [username, salt, hash] = entry.split(':');
      if (!username || !salt || !hash) {
        throw new Error(`Malformed NYPENN_USERS entry: "${entry}"`);
      }
      return { username, salt, hash };
    });
}

/** Derive a password hash. Used by the credential-generation script. */
export function hashPassword(password: string, salt = randomBytes(16).toString('hex')) {
  const hash = scryptSync(password, salt, 64).toString('hex');
  return { salt, hash };
}

/** Constant-time credential check. */
export function verify(account: Account, password: string): boolean {
  const candidate = scryptSync(password, account.salt, 64);
  const expected = Buffer.from(account.hash, 'hex');
  if (candidate.length !== expected.length) return false;
  return timingSafeEqual(candidate, expected);
}

export function issueToken(username: string, secret: string): string {
  return jwt.sign({ sub: username }, secret, { expiresIn: TOKEN_TTL });
}

/** Reject anything without a valid bearer token. */
export function requireAuth(secret: string) {
  return (req: Request, res: Response, next: NextFunction): void => {
    const header = req.headers.authorization;
    const token = header?.startsWith('Bearer ') ? header.slice(7) : null;

    if (!token) {
      res.status(401).json({ error: 'authentication required' });
      return;
    }

    try {
      const payload = jwt.verify(token, secret) as { sub?: string };
      (req as Request & { username?: string }).username = payload.sub;
      next();
    } catch {
      res.status(401).json({ error: 'invalid or expired token' });
    }
  };
}
