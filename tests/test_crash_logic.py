from app.idempotency import idempotency_key
def test_crash_replay_key_is_stable():
    a=idempotency_key("run","5","place_order",{"x":1})
    b=idempotency_key("run","5","place_order",{"x":1})
    assert a==b
def test_crash_replay_side_effect_is_exactly_once(stores):
    s,d=stores
    key="crash-key"
    args={"student_id":"22CS045","items":[{"item_id":3,"quantity":1}],"client_request_id":"crash-1"}
    first,_=d.once(key,"place_order",lambda:d.place_order(**args))
    second,_=d.once(key,"place_order",lambda:d.place_order(**args))
    assert first["order_id"]==second["order_id"]
    assert d.count("canteen_order")==1
