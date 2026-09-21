import argparse
from app.config import open_stores,make_provider
from app.worker import Worker
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--mock",action="store_true"); p.add_argument("--slow",type=float,default=0)
    p.add_argument("--lease",type=float,default=30); p.add_argument("--id",default=None)
    p.add_argument("--once",action="store_true"); p.add_argument("--gap",type=float,default=0)
    a=p.parse_args()
    s,d=open_stores(); w=Worker(s,d,make_provider(a.mock,a.slow),worker_id=a.id,lease_seconds=a.lease,record_delay=a.gap)
    print(w.run_once() if a.once else w.run_until_idle())
if __name__=="__main__": main()
