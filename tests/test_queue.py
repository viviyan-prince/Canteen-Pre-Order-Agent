def test_enqueue_claim_complete(stores):
    s,d=stores
    tid=s.create_thread("22CS045"); rid=s.enqueue(tid,"hello","mock")
    c=s.claim_next("w1",30)
    assert c.run_id==rid and c.attempts==1
    assert s.complete(rid,"w1","done")
    assert s.get_run(rid)["status"]=="succeeded"

def test_lease_replay(stores):
    s,d=stores
    now=[100.0]
    s.clock=lambda:now[0]
    tid=s.create_thread("22CS045"); rid=s.enqueue(tid,"hello","mock")
    c=s.claim_next("w1",2)
    now[0]=103
    assert s.reap_expired()==[rid]
    assert s.get_run(rid)["status"]=="queued"
    c2=s.claim_next("w2",2)
    assert c2.attempts==2

def test_cancel_queued(stores):
    s,d=stores
    tid=s.create_thread("22CS045"); rid=s.enqueue(tid,"hello","mock")
    assert s.request_cancel(rid)=="cancelled"
    assert s.get_run(rid)["status"]=="cancelled"

def test_retry_backoff(stores):
    s,d=stores
    now=[0.0]; s.clock=lambda:now[0]
    tid=s.create_thread("22CS045"); rid=s.enqueue(tid,"hello","mock")
    s.claim_next("w1",10)
    assert s.fail_attempt(rid,"w1","temporary",True,2)=="queued"
    assert s.get_run(rid)["available_at"]==2.0
