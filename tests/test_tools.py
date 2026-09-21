from app.agents import SupervisorAgent
from app.tools.canteen_tools import CanteenTools
def test_list_menu(tools):
    r=tools.list_menu(); assert len(r["items"])==5
def test_check_wallet(tools):
    assert tools.check_wallet("22CS045")["balance"]==200
def test_unknown_wallet(tools):
    assert tools.check_wallet("XX")["error"]=="unknown_student"
def test_quantity_policy(tools):
    r=tools.place_order("22CS045",[{"item_id":1,"quantity":4}],"x-1")
    assert r["error"]=="quantity_limit"
def test_out_of_stock(tools):
    r=tools.place_order("22CS045",[{"item_id":2,"quantity":3}],"x-2")
    assert r["error"]=="out_of_stock"
def test_insufficient_wallet(tools):
    r=tools.place_order("22EC031",[{"item_id":2,"quantity":1}],"x-3")
    assert r["error"]=="insufficient_wallet"
def test_place_order_debits_and_stock(tools,stores):
    _,db=stores
    before=db.get_wallet("22CS045")
    r=tools.place_order("22CS045",[{"item_id":1,"quantity":1}],"x-4")
    assert r["status"]=="placed"
    assert db.get_wallet("22CS045")==before-4500
    assert db.get_item(1).stock_count==4
def test_place_order_direct_repeat_safe(tools):
    a=tools.place_order("22CS045",[{"item_id":1,"quantity":1}],"same-key")
    b=tools.place_order("22CS045",[{"item_id":1,"quantity":1}],"same-key")
    assert a["order_id"]==b["order_id"] and b["duplicate"] is True
def test_cancel_repeat_safe(tools):
    a=tools.place_order("22CS045",[{"item_id":3,"quantity":1}],"cancel-key")
    b=tools.cancel_order("22CS045",a["order_id"])
    c=tools.cancel_order("22CS045",a["order_id"])
    assert b["status"]=="cancelled" and c["already_cancelled"] is True
def test_notification_dedupe(tools,stores):
    r1=tools.notify_student("22CS045","Order ready")
    r2=tools.notify_student("22CS045","Order ready")
    assert r1["duplicate"] is False and r2["duplicate"] is True
def test_specialist_has_no_writes(stores):
    from app.tools.canteen_tools import CanteenTools,MenuSpecialist
    _,db=stores
    s=MenuSpecialist(CanteenTools(db))
    assert set(s.TOOL_NAMES).isdisjoint(set(CanteenTools.SIDE_EFFECTS))
def test_supervisor_delegates(stores):
    _,db=stores
    s=SupervisorAgent(CanteenTools(db))
    r=s.delegate_to_menu_specialist("show menu")
    assert "items" in r
