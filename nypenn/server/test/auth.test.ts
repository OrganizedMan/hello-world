import assert from 'node:assert/strict';
import { test } from 'node:test';
import { hashPassword, issueToken, parseAccounts, verify } from '../src/auth.js';
import jwt from 'jsonwebtoken';

test('a correct password verifies and a wrong one does not', () => {
  const { salt, hash } = hashPassword('correct horse battery staple');
  const account = { username: 'alice', salt, hash };

  assert.equal(verify(account, 'correct horse battery staple'), true);
  assert.equal(verify(account, 'wrong password'), false);
  assert.equal(verify(account, ''), false);
});

test('each hash uses a fresh salt', () => {
  const a = hashPassword('same password');
  const b = hashPassword('same password');
  assert.notEqual(a.salt, b.salt);
  assert.notEqual(a.hash, b.hash, 'identical passwords must not produce identical hashes');
});

test('accounts parse from the environment format', () => {
  const accounts = parseAccounts('alice:s1:h1,bob:s2:h2');
  assert.equal(accounts.length, 2);
  assert.deepEqual(accounts[0], { username: 'alice', salt: 's1', hash: 'h1' });
});

test('an empty or absent user list yields no accounts rather than a crash', () => {
  assert.deepEqual(parseAccounts(undefined), []);
  assert.deepEqual(parseAccounts('   '), []);
});

test('a malformed entry is rejected loudly', () => {
  assert.throws(() => parseAccounts('alice:missing-hash'), /Malformed/);
});

test('an issued token carries the username and verifies under the secret', () => {
  const token = issueToken('alice', 'test-secret');
  const payload = jwt.verify(token, 'test-secret') as { sub: string };
  assert.equal(payload.sub, 'alice');
});

test('a token does not verify under a different secret', () => {
  const token = issueToken('alice', 'test-secret');
  assert.throws(() => jwt.verify(token, 'other-secret'));
});
