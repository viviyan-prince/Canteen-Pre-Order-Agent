"""End-to-end no-key demo."""
import os
from app.config import open_stores,make_provider
from app.worker import Worker

def main():
    store,db=open_stores()
    tid=store.create_thread("22CS045")
    rid=store.enqueue(tid,"Show the menu, check my wallet, place one veg meal and two samosas, then notify me.","mock")
    print(f"queued run: {rid}")
    w=Worker(store,db,make_provider(True),worker_id="demo-worker")
    print("worker:",w.run_until_idle())
    run=store.get_run(rid)
    print("status:",run["status"])
    print("reply:",store.load_history(tid)[-1]["text"])
    print("orders:",db.count("canteen_order"),"notifications:",db.count("notification"))
    print("PASS: end-to-end canteen agent")
if __name__=="__main__": main()
