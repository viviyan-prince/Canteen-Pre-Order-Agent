import time
from app.agent_db import enqueue
from app.worker import process_one,wait_for_replay
task=enqueue('{"message":"Show today menu","student_id":1}')
print("Created task",task);process_one(crash=True);print("Worker crashed after lease. Waiting for expiry...");r=wait_for_replay(6);assert r;print("PASS: expired task replayed.")
