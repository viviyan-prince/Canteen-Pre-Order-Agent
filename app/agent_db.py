import sqlite3,time
from pathlib import Path
DB_PATH=Path(__file__).resolve().parents[1]/"agent.db"
def init_agent_db():
    c=sqlite3.connect(DB_PATH)
    c.executescript("""CREATE TABLE IF NOT EXISTS task_queue(id INTEGER PRIMARY KEY AUTOINCREMENT,payload TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'queued',attempts INTEGER NOT NULL DEFAULT 0,lease_until REAL,worker_id TEXT,result TEXT,created_at REAL NOT NULL,completed_at REAL);
CREATE TABLE IF NOT EXISTS agent_runs(id INTEGER PRIMARY KEY AUTOINCREMENT,task_id INTEGER,agent TEXT,delegated_to TEXT,tools_called TEXT,created_at REAL,completed_at REAL);
CREATE TABLE IF NOT EXISTS agent_memory(id INTEGER PRIMARY KEY AUTOINCREMENT,student_id INTEGER,role TEXT,message TEXT,created_at REAL);
CREATE TABLE IF NOT EXISTS idempotency_keys(key TEXT PRIMARY KEY,result TEXT NOT NULL,created_at REAL);
CREATE TABLE IF NOT EXISTS dead_letters(id INTEGER PRIMARY KEY AUTOINCREMENT,task_id INTEGER,reason TEXT,payload TEXT,created_at REAL);""")
    c.commit();c.close()
def enqueue(payload):
    init_agent_db();c=sqlite3.connect(DB_PATH);cur=c.execute("INSERT INTO task_queue(payload,created_at) VALUES (?,?)",(payload,time.time()));c.commit();i=cur.lastrowid;c.close();return i
def claim(worker_id,lease_seconds=5):
    init_agent_db();now=time.time();c=sqlite3.connect(DB_PATH)
    c.execute("UPDATE task_queue SET status='queued',worker_id=NULL,lease_until=NULL WHERE status='running' AND lease_until < ?",(now,))
    r=c.execute("SELECT id,payload,attempts FROM task_queue WHERE status='queued' ORDER BY id LIMIT 1").fetchone()
    if not r:c.close();return None
    i,p,a=r;c.execute("UPDATE task_queue SET status='running',attempts=attempts+1,worker_id=?,lease_until=? WHERE id=? AND status='queued'",(worker_id,now+lease_seconds,i));c.commit();c.close();return {"id":i,"payload":p,"attempts":a+1}
def complete(task_id,result):
    c=sqlite3.connect(DB_PATH);c.execute("UPDATE task_queue SET status='done',result=?,completed_at=?,lease_until=NULL WHERE id=?",(result,time.time(),task_id));c.commit();c.close()
def record_memory(student_id,role,message):
    init_agent_db();c=sqlite3.connect(DB_PATH);c.execute("INSERT INTO agent_memory(student_id,role,message,created_at) VALUES(?,?,?,?)",(student_id,role,message,time.time()));c.commit();c.close()
def record_run(task_id,agent,delegated,tools):
    init_agent_db();c=sqlite3.connect(DB_PATH);c.execute("INSERT INTO agent_runs(task_id,agent,delegated_to,tools_called,created_at,completed_at) VALUES(?,?,?,?,?,?)",(task_id,agent,delegated,tools,time.time(),time.time()));c.commit();c.close()
