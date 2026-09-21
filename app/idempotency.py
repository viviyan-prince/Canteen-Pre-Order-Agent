import hashlib, json
from datetime import date

def canonical_json(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False,default=str)

def idempotency_key(run_id,step_seq,tool_name,args):
    return hashlib.sha256(canonical_json([run_id,step_seq,tool_name,args]).encode()).hexdigest()

def notification_dedupe_key(student_id,message,day:date):
    return hashlib.sha256(canonical_json([student_id," ".join(message.split()),day.isoformat()]).encode()).hexdigest()
