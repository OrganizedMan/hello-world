/**
 * Print a NYPENN_USERS entry for a username and password.
 *
 * Usage: npm run adduser -w @nypenn/server -- alice 'their password'
 *
 * Prints to stdout for you to paste into .env; it deliberately does not write
 * the file itself, so a password never lands anywhere by surprise.
 */
import { hashPassword } from './auth.js';

const [username, password] = process.argv.slice(2);

if (!username || !password) {
  console.error("Usage: npm run adduser -w @nypenn/server -- <username> '<password>'");
  process.exit(1);
}

const { salt, hash } = hashPassword(password);
console.log(`\nAppend to NYPENN_USERS in nypenn/.env (comma-separate multiple accounts):\n`);
console.log(`${username}:${salt}:${hash}\n`);
