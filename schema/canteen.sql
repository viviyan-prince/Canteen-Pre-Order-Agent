-- canteen.db: business data. Agent memory/queue lives in agent.db.

CREATE TABLE IF NOT EXISTS wallet (
    student_id TEXT PRIMARY KEY,
    balance_paise INTEGER NOT NULL CHECK (balance_paise >= 0)
);

CREATE TABLE IF NOT EXISTS menu_item (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    price_paise INTEGER NOT NULL CHECK (price_paise >= 0),
    stock_count INTEGER NOT NULL CHECK (stock_count >= 0),
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0,1))
);

CREATE TABLE IF NOT EXISTS policy (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS canteen_order (
    id INTEGER PRIMARY KEY,
    student_id TEXT NOT NULL,
    total_paise INTEGER NOT NULL CHECK (total_paise >= 0),
    status TEXT NOT NULL CHECK (status IN ('placed','cancelled')),
    client_request_id TEXT NOT NULL UNIQUE,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS order_item (
    order_id INTEGER NOT NULL REFERENCES canteen_order(id),
    item_id INTEGER NOT NULL REFERENCES menu_item(id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price_paise INTEGER NOT NULL CHECK (unit_price_paise >= 0),
    PRIMARY KEY (order_id, item_id)
);

CREATE TABLE IF NOT EXISTS notification (
    id INTEGER PRIMARY KEY,
    student_id TEXT NOT NULL,
    message TEXT NOT NULL,
    dedupe_key TEXT NOT NULL UNIQUE,
    created_at REAL NOT NULL
);

-- Durable idempotency ledger: effect + key commit in the same transaction.
CREATE TABLE IF NOT EXISTS idempotency (
    key TEXT PRIMARY KEY,
    tool_name TEXT NOT NULL,
    result TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_menu_active ON menu_item(active);
CREATE INDEX IF NOT EXISTS idx_order_student ON canteen_order(student_id);
