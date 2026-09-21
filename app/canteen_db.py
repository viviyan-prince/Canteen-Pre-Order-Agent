"""SQLite repository for canteen business data."""
import json
import sqlite3
import time
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
from app.domain import MenuItem, Policy

SCHEMA = Path(__file__).resolve().parent.parent / "schema" / "canteen.sql"

def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, isolation_level=None, timeout=5.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn

class CanteenDb:
    def __init__(self, path=":memory:", clock: Callable[[], float]=time.time):
        self.conn = connect(path)
        self.clock = clock

    def migrate(self, seed=True):
        self.conn.executescript(SCHEMA.read_text())
        if seed and self.conn.execute("SELECT count(*) FROM menu_item").fetchone()[0] == 0:
            self._seed()

    def _seed(self):
        now = self.clock()
        with self.transaction() as c:
            c.executemany("INSERT INTO menu_item VALUES (?,?,?,?,?,?)", [
                (1,"Veg Meals","Meals",4500,5,1),
                (2,"Chicken Rice","Meals",7000,2,1),
                (3,"Samosa","Snacks",1500,10,1),
                (4,"Fresh Lime","Drinks",2000,8,1),
                (5,"Coffee","Drinks",1200,20,1),
            ])
            c.executemany("INSERT INTO wallet VALUES (?,?)", [
                ("22CS045",20000), ("22IT017",10000), ("22EC031",6000)
            ])
            c.executemany("INSERT INTO policy VALUES (?,?)", [
                ("max_quantity_per_item","3"),
                ("minimum_wallet_balance_paise","0"),
                ("cancellation_window_minutes","10"),
            ])

    @contextmanager
    def transaction(self):
        if self.conn.in_transaction:
            yield self.conn
            return
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            yield self.conn
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise
        self.conn.execute("COMMIT")

    def count(self, table):
        assert table.isidentifier()
        return self.conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]

    def get_item(self, item_id):
        r=self.conn.execute("SELECT * FROM menu_item WHERE id=?",(item_id,)).fetchone()
        return MenuItem(r["id"],r["name"],r["category"],r["price_paise"],r["stock_count"],bool(r["active"])) if r else None

    def list_menu(self):
        rows=self.conn.execute("SELECT * FROM menu_item WHERE active=1 ORDER BY category,id").fetchall()
        return [MenuItem(r["id"],r["name"],r["category"],r["price_paise"],r["stock_count"],bool(r["active"])) for r in rows]

    def get_wallet(self, student_id):
        r=self.conn.execute("SELECT balance_paise FROM wallet WHERE student_id=?",(student_id,)).fetchone()
        return r["balance_paise"] if r else None

    def policy(self,key):
        r=self.conn.execute("SELECT value FROM policy WHERE key=?",(key,)).fetchone()
        return r["value"] if r else None

    def place_order(self, student_id, items, client_request_id):
        """Atomically validate wallet/stock/policy, decrement stock, debit wallet, create order."""
        with self.transaction() as c:
            old=c.execute("SELECT id,total_paise,status FROM canteen_order WHERE client_request_id=?",
                          (client_request_id,)).fetchone()
            if old:
                return {"order_id":old["id"],"total_paise":old["total_paise"],
                        "status":old["status"],"duplicate":True}

            balance_row=c.execute("SELECT balance_paise FROM wallet WHERE student_id=?",(student_id,)).fetchone()
            if not balance_row:
                return {"error":"unknown_student","hint":"No wallet exists for this student."}

            max_qty=int(self.policy("max_quantity_per_item") or "3")
            minimum=int(self.policy("minimum_wallet_balance_paise") or "0")
            normalized={}
            for item in items:
                item_id=int(item["item_id"]); qty=int(item["quantity"])
                if qty <= 0:
                    return {"error":"invalid_quantity","hint":"Quantity must be positive."}
                normalized[item_id]=normalized.get(item_id,0)+qty

            total=0
            details=[]
            for item_id,qty in normalized.items():
                row=c.execute("SELECT * FROM menu_item WHERE id=? AND active=1",(item_id,)).fetchone()
                if not row:
                    return {"error":"unknown_item","hint":f"Menu item {item_id} is not available."}
                if qty > max_qty:
                    return {"error":"quantity_limit","item_id":item_id,"max_quantity":max_qty,
                            "hint":"The limit comes from the policy table."}
                if row["stock_count"] < qty:
                    return {"error":"out_of_stock","item_id":item_id,"available":row["stock_count"],
                            "hint":"Choose a smaller quantity or another item."}
                total += row["price_paise"] * qty
                details.append((item_id,qty,row["price_paise"],row["name"]))

            balance=balance_row["balance_paise"]
            if balance-total < minimum:
                return {"error":"insufficient_wallet","balance_paise":balance,"total_paise":total,
                        "hint":"Top up the wallet or reduce the order."}

            cur=c.execute("""INSERT INTO canteen_order(student_id,total_paise,status,client_request_id,created_at)
                             VALUES (?,?,?,?,?)""",
                          (student_id,total,"placed",client_request_id,self.clock()))
            order_id=cur.lastrowid
            for item_id,qty,price,name in details:
                cur_stock=c.execute("UPDATE menu_item SET stock_count=stock_count-? WHERE id=? AND stock_count>=?",
                          (qty,item_id,qty))
                if cur_stock.rowcount != 1:
                    raise RuntimeError("stock_race")
                c.execute("INSERT INTO order_item VALUES (?,?,?,?)",(order_id,item_id,qty,price))
            cur_wallet=c.execute("UPDATE wallet SET balance_paise=balance_paise-? WHERE student_id=? AND balance_paise-? >= ?",
                      (total,student_id,total,minimum))
            if cur_wallet.rowcount != 1:
                raise RuntimeError("wallet_race")
            return {"order_id":order_id,"total_paise":total,"status":"placed","duplicate":False,
                    "items":[{"item_id":i,"name":n,"quantity":q,"unit_price_paise":p} for i,q,p,n in details],
                    "remaining_balance_paise":balance-total}

    def cancel_order(self, student_id, order_id):
        with self.transaction() as c:
            order=c.execute("SELECT * FROM canteen_order WHERE id=? AND student_id=?",(order_id,student_id)).fetchone()
            if not order:
                return {"error":"unknown_order","hint":"The order does not belong to this student or does not exist."}
            if order["status"]=="cancelled":
                return {"order_id":order_id,"status":"cancelled","already_cancelled":True}
            window=int(self.policy("cancellation_window_minutes") or "10")
            age_minutes=(self.clock()-order["created_at"])/60
            if age_minutes > window:
                return {"error":"cancellation_window_expired","window_minutes":window}
            cur_cancel=c.execute("UPDATE canteen_order SET status='cancelled' WHERE id=? AND status='placed'",(order_id,))
            if cur_cancel.rowcount != 1:
                return {"order_id":order_id,"status":"cancelled","already_cancelled":True}
            rows=c.execute("SELECT item_id,quantity FROM order_item WHERE order_id=?",(order_id,)).fetchall()
            for r in rows:
                c.execute("UPDATE menu_item SET stock_count=stock_count+? WHERE id=?",(r["quantity"],r["item_id"]))
            cur_refund=c.execute("UPDATE wallet SET balance_paise=balance_paise+? WHERE student_id=?",
                      (order["total_paise"],student_id))
            if cur_refund.rowcount != 1:
                raise RuntimeError("wallet_refund_race")
            return {"order_id":order_id,"status":"cancelled","refunded_paise":order["total_paise"],"already_cancelled":False}

    def record_notification(self, student_id, message, dedupe_key):
        with self.transaction() as c:
            cur=c.execute("""INSERT INTO notification(student_id,message,dedupe_key,created_at)
                             VALUES(?,?,?,?) ON CONFLICT(dedupe_key) DO NOTHING""",
                          (student_id,message,dedupe_key,self.clock()))
            if cur.rowcount==1:
                return cur.lastrowid,True
            return c.execute("SELECT id FROM notification WHERE dedupe_key=?",(dedupe_key,)).fetchone()["id"],False

    def once(self,key,tool_name,effect):
        with self.transaction() as c:
            row=c.execute("SELECT result FROM idempotency WHERE key=?",(key,)).fetchone()
            if row:
                return json.loads(row["result"]),False
            result=effect()
            c.execute("INSERT INTO idempotency VALUES (?,?,?,?)",
                      (key,tool_name,json.dumps(result,default=str),self.clock()))
            return result,True
