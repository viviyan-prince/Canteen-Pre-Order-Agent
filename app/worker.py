import json,uuid,time
from app.agent_db import claim,complete,init_agent_db,record_memory,record_run
from app.database import SessionLocal
from app.agent import run_agent_chat
def process_one(crash=False):
    init_agent_db();task=claim("worker-"+uuid.uuid4().hex[:8])
    if not task:return None
    if crash:return {"crashed_task":task["id"]}
    p=json.loads(task["payload"]);db=SessionLocal()
    try:
        r=run_agent_chat(p["message"],db,p.get("student_id",1));complete(task["id"],json.dumps(r));record_memory(p.get("student_id",1),"student",p["message"]);record_memory(p.get("student_id",1),"assistant",r["response"]);record_run(task["id"],r.get("supervisor","Request Interpreter"),r.get("delegated_to",""),",".join(r.get("tools_called",[])));return r
    finally:db.close()
def wait_for_replay(seconds=6):time.sleep(seconds);return process_one()
