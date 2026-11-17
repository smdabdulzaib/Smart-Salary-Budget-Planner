# Smart Salary Budget Planner & Daily Expense Management System

Flask + MySQL application to enter salary and fixed commitments, calculate daily budgets, and track expenses by category.

## Features
- Register/login with password hashing
- Monthly salary, rent, EMI, bills, other fixed expenses, and savings budget
- Daily baseline and remaining-budget-aware allowance
- Add and delete categorised expenses
- Dashboard, monthly history, category doughnut chart
- User-specific records using SQLAlchemy and MySQL

## Setup (Windows PowerShell)
1. Install MySQL 8 and create the database:
   `CREATE DATABASE salary_budget CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;`
2. Create environment and install:
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env`, then set your MySQL password in `DATABASE_URL`.
4. Run `python app.py` and visit http://127.0.0.1:5000.

Example: ₹30,000 salary − ₹12,000 commitments = ₹18,000 variable budget. In a 30-day month, baseline allowance is ₹600/day. If you log ₹300 today, the dashboard shows today's spend and remaining recommended allowance.

Never commit `.env` or real credentials. For production, disable debug mode, use a strong secret, add CSRF protection, and configure HTTPS.
