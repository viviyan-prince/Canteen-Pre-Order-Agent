from typing import Any,Dict,Optional
from sqlalchemy.orm import Session
from app.models import MenuItem,Order,OrderItem,Student

def list_menu(db:Session,category:Optional[str]=None)->Dict[str,Any]:
    """Read-only menu lookup. Never use for mutations. Changes nothing."""
    q=db.query(MenuItem).filter(MenuItem.active==True)
    if category:q=q.filter(MenuItem.category.ilike(f"%{category}%"))
    return {"success":True,"items":[{"id":i.id,"name":i.name,"category":i.category,"price":i.price,"portions_available":i.portions_available} for i in q.order_by(MenuItem.category,MenuItem.name).all()]}

def check_wallet(db:Session,student_id:int=1)->Dict[str,Any]:
    """Read-only wallet lookup. Never debit/refund. Changes nothing."""
    s=db.query(Student).filter(Student.id==student_id).first()
    return {"success":bool(s),"student":s.name if s else None,"wallet_balance":s.wallet_balance if s else None}

def get_my_orders(db:Session,student_id:int=1)->Dict[str,Any]:
    """Read-only order history. Never create/cancel. Changes nothing."""
    os=db.query(Order).filter(Order.student_id==student_id).order_by(Order.id.desc()).all()
    return {"success":True,"orders":[{"id":o.id,"total":o.total,"status":o.status,"items":[{"name":x.menu_item.name,"quantity":x.quantity} for x in o.items]} for o in os]}

def assess_order_risk(db:Session,item_name:str,quantity:int)->Dict[str,Any]:
    """Preflight safety check. Read-only; flags unusual size, low stock, or impossible quantity."""
    item=db.query(MenuItem).filter(MenuItem.name.ilike(item_name.strip())).first()
    if not item:return {"success":False,"flag":True,"severity":"high","reasons":["unknown item"]}
    reasons=[]
    if quantity>5:reasons.append("large quantity")
    if item.portions_available<=3:reasons.append("low stock")
    if quantity>item.portions_available:reasons.append("quantity exceeds stock")
    severity="high" if "quantity exceeds stock" in reasons else ("medium" if reasons else "low")
    return {"success":True,"flag":bool(reasons),"severity":severity,"reasons":reasons,"available":item.portions_available}

def place_order(db:Session,student_id:int,item_name:str,quantity:int,idempotency_key:str)->Dict[str,Any]:
    """Side effect. Use only for explicit orders. Enforces stock, wallet and idempotency."""
    old=db.query(Order).filter(Order.idempotency_key==idempotency_key).first()
    if old:return {"success":True,"replayed":True,"order_id":old.id,"total":old.total,"status":old.status}
    if quantity<=0:return {"success":False,"error":"Quantity must be positive."}
    s=db.query(Student).filter(Student.id==student_id).first();item=db.query(MenuItem).filter(MenuItem.name.ilike(item_name.strip())).first()
    if not s or not item:return {"success":False,"error":"Student or menu item not found."}
    total=round(item.price*quantity,2)
    if item.portions_available<quantity:return {"success":False,"error":f"Only {item.portions_available} portion(s) remain."}
    if s.wallet_balance<total:return {"success":False,"error":f"Insufficient wallet balance. Need ₹{total:.2f}, have ₹{s.wallet_balance:.2f}."}
    item.portions_available-=quantity;s.wallet_balance=round(s.wallet_balance-total,2)
    o=Order(student_id=s.id,total=total,idempotency_key=idempotency_key);db.add(o);db.flush();db.add(OrderItem(order_id=o.id,menu_item_id=item.id,quantity=quantity,unit_price=item.price));db.commit()
    return {"success":True,"order_id":o.id,"item":item.name,"quantity":quantity,"total":total,"wallet_balance":s.wallet_balance}

def cancel_order(db:Session,student_id:int,order_id:int,idempotency_key:str)->Dict[str,Any]:
    """Side effect. Use only for explicit cancellation. Restores stock and refunds wallet; repeat-safe."""
    o=db.query(Order).filter(Order.id==order_id,Order.student_id==student_id).first()
    if not o:return {"success":False,"error":"Order not found."}
    if o.status=="cancelled":return {"success":True,"replayed":True,"order_id":o.id,"status":"cancelled"}
    s=db.query(Student).filter(Student.id==student_id).first()
    for x in o.items:x.menu_item.portions_available+=x.quantity
    s.wallet_balance=round(s.wallet_balance+o.total,2);o.status="cancelled";db.commit()
    return {"success":True,"order_id":o.id,"status":"cancelled","refund":o.total,"wallet_balance":s.wallet_balance}

def notify_student(student_id:int,message:str,idempotency_key:str)->Dict[str,Any]:
    """Side effect. Use after meaningful events. Durable idempotency is stored in agent.db."""
    import json,sqlite3
    from app.agent_db import DB_PATH,init_agent_db
    init_agent_db();c=sqlite3.connect(DB_PATH);k="notify:"+idempotency_key;r=c.execute("SELECT result FROM idempotency_keys WHERE key=?",(k,)).fetchone()
    if r:c.close();return {**json.loads(r[0]),"replayed":True}
    result={"success":True,"notification_id":idempotency_key,"student_id":student_id,"message":message};c.execute("INSERT INTO idempotency_keys VALUES(?,?,strftime('%s','now'))",(k,json.dumps(result)));c.commit();c.close();return result

TOOL_DEFINITIONS=["list_menu","check_wallet","get_my_orders","assess_order_risk","place_order","cancel_order","notify_student"]
