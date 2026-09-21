import threading
from app.canteen_db import CanteenDb

def test_two_threads_cannot_oversell(tmp_path):
    path=str(tmp_path/"race.db")
    seed=CanteenDb(path); seed.migrate()
    # Item 1 has 5 portions; each worker asks for 3. At most one full order can win,
    # and total sold can never exceed stock.
    results=[]
    def work(i):
        db=CanteenDb(path); 
        try: results.append(db.place_order("22CS045",[{"item_id":1,"quantity":3}],f"race-{i}"))
        except Exception as e: results.append({"error":str(e)})
    ts=[threading.Thread(target=work,args=(i,)) for i in range(2)]
    [t.start() for t in ts]; [t.join() for t in ts]
    fresh=CanteenDb(path)
    assert fresh.get_item(1).stock_count>=0
    assert sum(1 for r in results if r.get("status")=="placed")<=1
