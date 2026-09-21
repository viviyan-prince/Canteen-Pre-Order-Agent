import logging,os,socket,time,uuid
from app.memory import RunStore
from app.canteen_db import CanteenDb
from app.providers import AgentError
from app.runner import LeaseLost,execute_run
from app.agents import SupervisorAgent

log=logging.getLogger("worker")

class Worker:
    def __init__(self,store,db,provider,worker_id=None,lease_seconds=30,on_step=None,record_delay=0):
        self.store,self.db,self.provider=store,db,provider
        self.worker_id=worker_id or f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:4]}"
        self.lease_seconds=lease_seconds; self.on_step=on_step; self.record_delay=record_delay
        self.agent=SupervisorAgent(__import__("app.tools.canteen_tools",fromlist=["CanteenTools"]).CanteenTools(db))
    def run_once(self):
        self.store.reap_expired()
        claimed=self.store.claim_next(self.worker_id,self.lease_seconds)
        if claimed is None:return None
        try:
            outcome=execute_run(claimed,store=self.store,db=self.db,agent=self.agent,provider=self.provider,
                                worker_id=self.worker_id,lease_seconds=self.lease_seconds,on_step=self.on_step,
                                record_delay=self.record_delay)
        except LeaseLost: outcome="lease_lost"
        except AgentError as e: outcome=self.store.fail_attempt(claimed.run_id,self.worker_id,e.code,e.retryable) or "lease_lost"
        except Exception:
            log.exception("run crashed")
            outcome=self.store.fail_attempt(claimed.run_id,self.worker_id,"internal_error",False) or "lease_lost"
        return claimed.run_id,outcome
    def run_until_idle(self):
        out=[]
        while True:
            x=self.run_once()
            if x is None:return out
            out.append(x)
    def run_forever(self,poll_seconds=1):
        while True:
            if self.run_once() is None: time.sleep(poll_seconds)
