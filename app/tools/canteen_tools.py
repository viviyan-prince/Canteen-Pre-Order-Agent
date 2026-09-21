from datetime import datetime, timezone
from app.canteen_db import CanteenDb
from app.idempotency import notification_dedupe_key
from app.tools.dispatch import dispatch

def _money(paise): return round(paise/100,2)

class CanteenTools:
    READ_ONLY=("list_menu","check_wallet","get_my_orders")
    SIDE_EFFECTS=("place_order","cancel_order","notify_student")
    TOOL_NAMES=READ_ONLY+SIDE_EFFECTS

    def __init__(self,repo:CanteenDb,clock=lambda:datetime.now(timezone.utc)):
        self.repo=repo; self.clock=clock

    def functions(self): return {n:getattr(self,n) for n in self.TOOL_NAMES}
    def call(self,name,args): return dispatch(self.functions(),name,args)

    def list_menu(self)->dict:
        """List currently active canteen items and remaining stock.
        Use when the user asks what food is available or wants to choose items.
        Do NOT use to place an order. Read-only: changes nothing."""
        return {"items":[{"item_id":x.id,"name":x.name,"category":x.category,
                         "price":_money(x.price_paise),"available_portions":x.stock_count}
                     for x in self.repo.list_menu()]}

    def check_wallet(self,student_id:str)->dict:
        """Read a student's current wallet balance.
        Use when the user asks how much money is available or before explaining an insufficient-wallet error.
        Do NOT use to debit the wallet. Read-only: changes nothing."""
        b=self.repo.get_wallet(student_id)
        if b is None:return {"error":"unknown_student","hint":"No wallet found for this student."}
        return {"student_id":student_id,"balance":_money(b),"balance_paise":b}

    def get_my_orders(self,student_id:str)->dict:
        """List this student's recent canteen orders.
        Use when the user asks what they ordered or whether an order exists.
        Do NOT use to create/cancel an order. Read-only: changes nothing."""
        rows=self.repo.conn.execute("""SELECT id,total_paise,status,created_at FROM canteen_order
                                       WHERE student_id=? ORDER BY id DESC LIMIT 10""",(student_id,)).fetchall()
        return {"orders":[{"order_id":r["id"],"total":_money(r["total_paise"]),
                           "status":r["status"],"created_at":r["created_at"]} for r in rows]}

    def place_order(self,student_id:str,items:list,client_request_id:str)->dict:
        """Place one canteen pre-order and debit the wallet.
        Use ONLY when the user clearly asks to order specific items. Do NOT use for menu browsing,
        price questions, or checking balance. Side effect: creates an order, decrements stock, and debits wallet.
        The database re-checks stock, wallet, and policy even if the model skips prior checks.
        client_request_id makes a repeated direct call safe."""
        if not items:return {"error":"empty_order","hint":"Provide at least one item."}
        return self.repo.place_order(student_id,items,client_request_id)

    def cancel_order(self,student_id:str,order_id:int)->dict:
        """Cancel an existing order within the configured cancellation window.
        Use ONLY when the user explicitly asks to cancel. Do NOT use to inspect order status.
        Side effect: marks the order cancelled, restores stock, and refunds the wallet.
        Repeating cancellation is safe and returns already_cancelled."""
        return self.repo.cancel_order(student_id,order_id)

    def notify_student(self,student_id:str,message:str)->dict:
        """Send a short order/reminder notification.
        Use ONLY when the user explicitly asks to notify, remind, or message them.
        Do NOT use merely to answer a question. Side effect: records a notification; identical
        message to the same student on the same day is deduplicated."""
        if not message.strip() or len(message)>160:
            return {"error":"invalid_message","hint":"message must be 1 to 160 characters"}
        if self.repo.get_wallet(student_id) is None:
            return {"error":"unknown_student","hint":"No wallet found for this student."}
        key=notification_dedupe_key(student_id,message,self.clock().date())
        nid,created=self.repo.record_notification(student_id,message,key)
        return {"notification_id":nid,"status":"queued","duplicate":not created}

class MenuSpecialist:
    """Least-privilege specialist: it has NO write tools."""
    TOOL_NAMES=("list_menu","check_wallet")
    def __init__(self,tools:CanteenTools): self.tools=tools
    def functions(self): return {n:getattr(self.tools,n) for n in self.TOOL_NAMES}
    def consult(self,question:str)->dict:
        q=question.lower()
        if any(w in q for w in ("menu","food","available","price","stock")):
            return self.tools.list_menu()
        if "wallet" in q or "balance" in q:
            # The supervisor supplies student_id through the question in the scripted demo.
            return {"specialist":"menu","answer":"Use check_wallet(student_id) when a student id is known."}
        return {"specialist":"menu","answer":"I can only inspect menu and wallet information."}
