# ZeroBudget

A zero-based budgeting app where every dollar gets a job. Built with React + Express + SQLite.

## Quick Start

```bash
npm run install:all
npm run dev
```

Server runs on `http://localhost:3001`, client on `http://localhost:5173`.

## Features

- **Zero-based budgeting** — allocate every dollar of income to categories
- **Budget into future months** — plan ahead by navigating to upcoming months
- **Auto-budget** — fill categories based on last month's spending, averages, or goals
- **Category goals** — target balance, target by date, monthly funding, monthly spending
- **Cover overspending** — move money between categories when one goes negative
- **Credit card handling** — spending on a credit card automatically moves budgeted funds to the CC payment category
- **Transaction management** — add, edit, delete transactions with payee memory
- **Account tracking** — checking, savings, credit cards, investments, loans
- **Reports** — net worth, spending breakdown, income vs expenses, age of money
- **Multi-device** — persistent SQLite database, JWT auth for secure access
- **Responsive** — mobile-first design with bottom nav, fully usable on desktop

## Tech Stack

- **Frontend:** React 18, TypeScript, Vite, React Router
- **Backend:** Express 4, TypeScript, better-sqlite3
- **Auth:** bcrypt + JWT (30-day tokens)
- **Security:** Helmet, CORS, rate limiting, input validation

## Production Build

```bash
npm run build
npm start
```

Set `JWT_SECRET` and `CORS_ORIGIN` environment variables in production.
