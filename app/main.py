import json,os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from app.database import init_db
from app.agent_db import init_agent_db,enqueue
from app.worker import process_one
class ChatRequest(BaseModel):
    message:str
    student_id:int=1
@asynccontextmanager
async def lifespan(app):
    init_db();init_agent_db();yield
app=FastAPI(title="CampusBite AI")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["*"],allow_headers=["*"])
@app.post("/agent/chat")
def chat(req:ChatRequest):
    task=enqueue(json.dumps({"message":req.message,"student_id":req.student_id}));r=process_one()
    return r or {"response":f"Request queued as task #{task}","tools_called":[]}
@app.get("/health")
def health():return {"status":"ok","domain_db":"canteen.db","agent_db":"agent.db"}
static_dir=os.path.join(os.path.dirname(__file__),"static")
app.mount("/static",StaticFiles(directory=static_dir),name="static")
@app.get("/",include_in_schema=False)
def home():return FileResponse(os.path.join(static_dir,"index.html"))
