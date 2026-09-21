from app.providers import booking_mock
from app.worker import Worker

def test_full_demo_run(stores):
    s,d=stores; tid=s.create_thread("22CS045")
    rid=s.enqueue(tid,"Order food and notify me","mock")
    w=Worker(s,d,booking_mock(),worker_id="test")
    assert w.run_until_idle()[0][1]=="succeeded"
    assert s.get_run(rid)["status"]=="succeeded"
    assert d.count("canteen_order")==1
    assert d.count("notification")==1
def test_run_idempotency_replay(stores):
    s,d=stores; tid=s.create_thread("22CS045")
    rid=s.enqueue(tid,"Order food","mock")
    w=Worker(s,d,booking_mock(),worker_id="test")
    w.run_until_idle()
    # Same request is independently safe in the business DB.
    assert d.count("canteen_order")==1
