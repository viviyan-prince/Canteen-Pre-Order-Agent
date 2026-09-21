import re
from app.tools import list_menu,check_wallet,get_my_orders,assess_order_risk,place_order,cancel_order,notify_student

class MenuIntelligence:
    name="Menu Intelligence"
    def run(self,message,db,student_id):
        r=list_menu(db); lines=["Current CampusBite menu:"]
        lines += [f"• {x['name']} — ₹{x['price']:.0f} ({x['portions_available']} left)" for x in r["items"]]
        return {"response":"\n".join(lines),"tools_called":["list_menu"],"delegated_to":self.name}

class OrderIntelligence:
    name="Order Intelligence"
    def run(self,message,db,student_id):
        low=message.lower()
        if "wallet" in low or "balance" in low:
            r=check_wallet(db,student_id);return {"response":f"Wallet balance: ₹{r['wallet_balance']:.2f}","tools_called":["check_wallet"],"delegated_to":self.name}
        if "my orders" in low or "order history" in low:
            r=get_my_orders(db,student_id);return {"response":str(r["orders"]) if r["orders"] else "You have no orders yet.","tools_called":["get_my_orders"],"delegated_to":self.name}
        m=re.search(r"(?:order|buy|get)\s+(\d+)\s+(.+?)(?:\s+for\s+me)?$",low)
        if m:
            q,item=int(m.group(1)),m.group(2).strip(" .?!");return self.place(db,student_id,item,q)
        c=re.search(r"cancel(?:\s+order)?\s*#?(\d+)",low)
        if c:
            oid=int(c.group(1));r=cancel_order(db,student_id,oid,f"cancel-{student_id}-{oid}");return {"response":r.get("error") or f"Order #{oid} cancelled and ₹{r.get('refund',0):.2f} refunded.","tools_called":["cancel_order"],"delegated_to":self.name}
        return {"response":"Try “check my wallet”, “show my orders”, or “order 2 samosas”.","tools_called":[],"delegated_to":self.name}
    def place(self,db,student_id,item,q):
        risk=assess_order_risk(db,item,q)
        if risk.get("flag") and risk.get("severity")=="high":return {"response":"Order blocked by Order Guardian: "+", ".join(risk["reasons"]),"tools_called":["assess_order_risk"],"delegated_to="Order Guardian"}
        r=place_order(db,student_id,item,q,f"place-{student_id}-{item}-{q}")
        tools=["assess_order_risk","place_order"]
        if not r["success"]:return {"response":r["error"],"tools_called":tools,"delegated_to":self.name}
        notify_student(student_id,f"Order #{r['order_id']} confirmed.",f"order-{r['order_id']}")
        tools.append("notify_student")
        return {"response":f"Order #{r['order_id']} confirmed: {q} × {r['item']} — ₹{r['total']:.2f}.","tools_called":tools,"delegated_to":self.name}

class SupervisorAgent:
    name="Request Interpreter"
    def __init__(self):self.menu=MenuIntelligence();self.orders=OrderIntelligence()
    def route(self,message,db,student_id=1):
        low=message.lower()
        if any(x in low for x in ("menu","food","available","samosa","dosa","rice","roll","juice","coffee")) and not any(x in low for x in ("order ","buy ","cancel")):return {**self.menu.run(message,db,student_id),"supervisor":self.name}
        return {**self.orders.run(message,db,student_id),"supervisor":self.name}

def run_agent_chat(user_message,db,student_id=1):return SupervisorAgent().route(user_message,db,student_id)
