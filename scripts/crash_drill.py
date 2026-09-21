"""Crash/replay proof: kill worker after an order effect but before its run-step record."""
import os,sys,subprocess,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
def main():
    tmp=tempfile.mkdtemp(prefix="canteen-crash-")
    env={**os.environ,"AGENT_DB":os.path.join(tmp,"agent.db"),"CANTEEN_DB":os.path.join(tmp,"canteen.db")}
    from app.memory import RunStore
    from app.canteen_db import CanteenDb
    s=CanteenDb(env["CANTEEN_DB"]); a=RunStore(env["AGENT_DB"]); a.migrate(); s.migrate()
    tid=a.create_thread("22CS045")
    rid=a.enqueue(tid,"Place my canteen order and notify me.","mock")
    cmd=[sys.executable,"-m","scripts.worker","--mock","--slow","0.2","--lease","2","--id","worker-A","--gap","1.5"]
    first=subprocess.Popen(cmd,cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    deadline=time.time()+15
    while s.count("canteen_order")==0:
        if time.time()>deadline:
            first.kill(); print("FAIL: first worker never placed order"); return 1
        time.sleep(.05)
    first.kill(); first.wait()
    print("killed worker-A after side effect, before recording step")
    time.sleep(2.5)
    subprocess.run([sys.executable,"-m","scripts.worker","--mock","--lease","5","--id","worker-B","--once"],
                   cwd=ROOT,env=env,check=True,stdout=subprocess.DEVNULL)
    run=a.get_run(rid)
    counts=(s.count("canteen_order"),s.count("notification"))
    ok=run["status"]=="succeeded" and counts==(1,1)
    print("runs:",run["status"],"attempts:",run["attempts"],"orders:",counts[0],"notifications:",counts[1])
    print("PASS: crash replay produced exactly one order and one notification" if ok else "FAIL: duplicate side effect")
    return 0 if ok else 1
if __name__=="__main__": sys.exit(main())
