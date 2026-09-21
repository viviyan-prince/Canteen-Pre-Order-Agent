"""Durable agent memory and queue. Business data is kept out of this database."""
import json, time, uuid
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from app.canteen_db import connect

SCHEMA=Path(__file__).resolve().parent.parent/"schema"/"agent.sql"
NOW_SQL="strftime('%Y-%m-%dT%H:%M:%fZ','now')"

@dataclass(frozen=True)
class Claimed:
    run_id:str
    thread_id:str
    attempts:int

class RunStore:
    def __init__(self,path=":memory:",clock:Callable[[],float]=time.time):
        self.conn=connect(path); self.clock=clock
    def migrate(self): self.conn.executescript(SCHEMA.read_text())
    @contextmanager
    def transaction(self):
        if self.conn.in_transaction:
            yield self.conn; return
        self.conn.execute("BEGIN IMMEDIATE")
        try: yield self.conn
        except BaseException: self.conn.execute("ROLLBACK"); raise
        self.conn.execute("COMMIT")
    def create_thread(self,student_id):
        tid=str(uuid.uuid4()); self.conn.execute("INSERT INTO thread(id,student_id) VALUES(?,?)",(tid,student_id)); return tid
    def get_thread(self,thread_id):
        r=self.conn.execute("SELECT * FROM thread WHERE id=?",(thread_id,)).fetchone()
        return dict(r) if r else None
    def append_message(self,thread_id,role,text):
        cur=self.conn.execute("""INSERT INTO message(thread_id,seq,role,text)
            VALUES(?,(SELECT COALESCE(MAX(seq),0)+1 FROM message WHERE thread_id=?),?,?)""",
            (thread_id,thread_id,role,text))
        return cur.lastrowid
    def load_history(self,thread_id):
        return [dict(r) for r in self.conn.execute("SELECT seq,role,text FROM message WHERE thread_id=? ORDER BY seq",(thread_id,))]
    def record_model_step(self,run_id,seq,tokens_in,tokens_out,text,tool_calls):
        with self.transaction() as c:
            sid=c.execute("""INSERT INTO run_step(run_id,seq,kind,tokens_in,tokens_out,text,tool_calls)
                             VALUES(?,?, 'model',?,?,?,?)""",
                          (run_id,seq,tokens_in,tokens_out,text,json.dumps(tool_calls))).lastrowid
            c.execute("UPDATE run SET tokens_in=tokens_in+?,tokens_out=tokens_out+? WHERE id=?",
                      (tokens_in,tokens_out,run_id))
            return sid
    def record_tool_call(self,run_id,seq,name,args,result,ok,latency_ms,key):
        with self.transaction() as c:
            sid=c.execute("INSERT INTO run_step(run_id,seq,kind) VALUES(?,?,'tool')",(run_id,seq)).lastrowid
            c.execute("""INSERT INTO tool_call(run_step_id,tool_name,args,result,ok,latency_ms,idempotency_key)
                         VALUES(?,?,?,?,?,?,?)""",
                      (sid,name,json.dumps(args),json.dumps(result,default=str),int(ok),latency_ms,key))
    def load_steps(self,run_id):
        rows=self.conn.execute("""SELECT s.seq,s.kind,s.text,s.tool_calls,t.tool_name,t.args,t.result,t.ok
                                  FROM run_step s LEFT JOIN tool_call t ON t.run_step_id=s.id
                                  WHERE s.run_id=? ORDER BY s.seq""",(run_id,)).fetchall()
        out=[]
        for r in rows:
            d=dict(r)
            for k in ("tool_calls","args","result"):
                d[k]=json.loads(d[k]) if d[k] else None
            out.append(d)
        return out
    def get_run(self,run_id):
        r=self.conn.execute("SELECT * FROM run WHERE id=?",(run_id,)).fetchone()
        return {**dict(r),"steps":self.load_steps(run_id)} if r else None
    def enqueue(self,thread_id,text,model,max_attempts=3):
        rid=str(uuid.uuid4())
        with self.transaction() as c:
            self.append_message(thread_id,"user",text)
            c.execute("""INSERT INTO run(id,thread_id,status,model,max_attempts,available_at)
                         VALUES(?,?, 'queued',?,?,?)""",(rid,thread_id,model,max_attempts,self.clock()))
        return rid
    def claim_next(self,worker_id,lease_seconds):
        now=self.clock()
        with self.transaction() as c:
            r=c.execute("""SELECT id,thread_id,attempts FROM run
                           WHERE status='queued' AND available_at<=?
                           ORDER BY available_at,created_at LIMIT 1""",(now,)).fetchone()
            if not r:return None
            c.execute(f"""UPDATE run SET status='running',lease_owner=?,lease_until=?,
                          attempts=attempts+1,started_at=COALESCE(started_at,{NOW_SQL})
                          WHERE id=?""",(worker_id,now+lease_seconds,r["id"]))
            return Claimed(r["id"],r["thread_id"],r["attempts"]+1)
    def heartbeat(self,run_id,worker_id,lease_seconds):
        cur=self.conn.execute("""UPDATE run SET lease_until=? WHERE id=? AND status='running' AND lease_owner=?""",
                              (self.clock()+lease_seconds,run_id,worker_id))
        return cur.rowcount==1
    def reap_expired(self):
        now=self.clock()
        with self.transaction() as c:
            rows=c.execute("SELECT id,attempts,max_attempts FROM run WHERE status='running' AND lease_until<?",(now,)).fetchall()
            for r in rows:
                if r["attempts"]>=r["max_attempts"]:
                    c.execute(f"""UPDATE run SET status='dead',error_code='lease_expired',
                                   lease_owner=NULL,lease_until=NULL,finished_at={NOW_SQL} WHERE id=?""",(r["id"],))
                else:
                    c.execute("""UPDATE run SET status='queued',error_code='lease_expired',
                                 lease_owner=NULL,lease_until=NULL,available_at=? WHERE id=?""",(now,r["id"]))
            return [r["id"] for r in rows]
    def complete(self,run_id,worker_id,reply):
        with self.transaction() as c:
            r=c.execute("SELECT thread_id FROM run WHERE id=? AND status='running' AND lease_owner=?",
                        (run_id,worker_id)).fetchone()
            if not r:return False
            self.append_message(r["thread_id"],"model",reply)
            c.execute(f"""UPDATE run SET status='succeeded',lease_owner=NULL,lease_until=NULL,
                          error_code=NULL,finished_at={NOW_SQL} WHERE id=?""",(run_id,))
            return True
    def request_cancel(self,run_id):
        with self.transaction() as c:
            r=c.execute("SELECT status FROM run WHERE id=?",(run_id,)).fetchone()
            if not r:return None
            if r["status"]=="queued":
                c.execute(f"UPDATE run SET status='cancelled',finished_at={NOW_SQL} WHERE id=?",(run_id,)); return "cancelled"
            if r["status"]=="running": c.execute("UPDATE run SET cancel_requested=1 WHERE id=?",(run_id,))
            return r["status"]
    def cancel_requested(self,run_id):
        r=self.conn.execute("SELECT cancel_requested FROM run WHERE id=?",(run_id,)).fetchone()
        return bool(r and r[0])
    def mark_cancelled(self,run_id,worker_id):
        cur=self.conn.execute(f"""UPDATE run SET status='cancelled',lease_owner=NULL,lease_until=NULL,
                                  finished_at={NOW_SQL} WHERE id=? AND status='running' AND lease_owner=?""",
                              (run_id,worker_id)); return cur.rowcount==1
    def fail_attempt(self,run_id,worker_id,error_code,retryable,backoff_seconds=1.0):
        with self.transaction() as c:
            r=c.execute("SELECT attempts,max_attempts FROM run WHERE id=? AND status='running' AND lease_owner=?",
                        (run_id,worker_id)).fetchone()
            if not r:return None
            if retryable and r["attempts"]<r["max_attempts"]:
                delay=backoff_seconds*2**(r["attempts"]-1)
                c.execute("""UPDATE run SET status='queued',error_code=?,lease_owner=NULL,lease_until=NULL,
                             available_at=? WHERE id=?""",(error_code,self.clock()+delay,run_id))
                return "queued"
            status="dead" if retryable else "failed"
            c.execute(f"""UPDATE run SET status=?,error_code=?,lease_owner=NULL,lease_until=NULL,
                          finished_at={NOW_SQL} WHERE id=?""",(status,error_code,run_id)); return status
