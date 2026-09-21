def test_once_only(stores):
    s,d=stores; calls=[]
    a,_=d.once("k","x",lambda:(calls.append(1) or {"ok":1}))
    b,_=d.once("k","x",lambda:(calls.append(1) or {"ok":2}))
    assert a==b=={"ok":1} and len(calls)==1
def test_notification_key_stored(tools,stores):
    _,db=stores
    tools.notify_student("22CS045","hello")
    assert db.count("idempotency")==0
    assert db.count("notification")==1
