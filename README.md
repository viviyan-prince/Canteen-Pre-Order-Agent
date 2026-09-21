# Canteen Agent — Weekend Project

## Domain
College canteen pre-orders. The scarce resource is **menu portions**. The system also sends notifications.

## Architecture
```text
User
  |
  v
agent.db: thread -> run queue -> lease
  |
  v
Supervisor Agent
  |----------------------------|
  |                            |
  v                            v
Menu Specialist            Write-capable tools
(read-only)                place_order / cancel_order / notify_student
  |                            |
  v                            v
                     canteen.db: menu, wallet, orders,
                     policy, notifications, idempotency
```

Two SQLite databases are deliberate:
- `canteen.db` = business data.
- `agent.db` = memory, queue, leases and run/tool history.

## Requirements covered
1. Two SQLite DBs + seed data.
2. Six tools: 3 read-only and 3 side-effect tools. Every tool docstring states when to use, when not to use, and what it changes.
3. `policy` table stores `max_quantity_per_item`, `minimum_wallet_balance_paise`, and `cancellation_window_minutes`. `place_order` enforces these rules in the database layer, not only in the prompt.
4. Queue + worker + lease + expired-lease replay.
5. Side effects pass through the idempotency ledger. `cancel_order` is independently repeat-safe; `place_order` is independently repeat-safe with `client_request_id`; notifications are deduplicated.
6. Supervisor delegates menu/wallet inspection to `MenuSpecialist`, which has no write tools.
7. Scripted model demo, crash demo, and tests require no API key.
8. Race test is included for higher grade.

## Run
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
python -m scripts.demo
python -m scripts.crash_drill
pytest -q
```

Real Gemini is optional:
```bash
set GEMINI_API_KEY=YOUR_KEY
python -m scripts.worker
```

Do not submit `.venv`, `*.db`, `__pycache__`, or secrets.
