"""Step-by-step durable execution with replayable tool effects."""
import time
from collections.abc import Callable
from app.idempotency import idempotency_key
from app.memory import Claimed,RunStore
from app.canteen_db import CanteenDb
from app.providers import AgentError
from app.agents import SupervisorAgent

MAX_STEPS=12
SYSTEM="""You are the Canteen Supervisor Agent for a college.
Student id: {student_id}.
You may delegate menu/wallet inspection to the read-only Menu Specialist.
Use tools for all menu, wallet, stock, and order facts. Never invent stock or prices.
Only place/cancel an order when the user explicitly requests that side effect.
Keep replies short and concrete."""

class LeaseLost(Exception): pass

def rebuild(store,thread_id,run_id):
    contents=[{"role":m["role"],"text":m["text"]} for m in store.load_history(thread_id)]
    seq=0; pending=[]; final_text=None
    for step in store.load_steps(run_id):
        if step["kind"]=="model":
            calls=step["tool_calls"] or []
            if not calls:
                final_text=step["text"] or ""; seq=step["seq"]; continue
            contents.append({"role":"model","text":step["text"],"tool_calls":calls})
            pending=[(step["seq"]+i+1,c) for i,c in enumerate(calls)]
            seq=step["seq"]+len(calls)
        else:
            contents.append({"role":"tool","name":step["tool_name"],"result":step["result"]})
            pending=[p for p in pending if p[0]!=step["seq"]]
    return contents,seq,pending,final_text

def call_tool(agent,db,key,name,args):
    try:
        if name in agent.tools.SIDE_EFFECTS:
            result,_=db.once(key,name,lambda:agent.tools.call(name,args))
            return result
        if name=="delegate_to_menu_specialist":
            return agent.delegate_to_menu_specialist(**args)
        return agent.tools.call(name,args)
    except Exception as e:
        return {"error":"tool_failed","hint":f"{name} failed: {type(e).__name__}"}

def execute_run(claimed,*,store,db,agent,provider,worker_id,lease_seconds,on_step=None,record_delay=0):
    run_id=claimed.run_id; thread=store.get_thread(claimed.thread_id)
    system=SYSTEM.format(student_id=thread["student_id"])
    functions=list(agent.supervisor_functions().values())
    contents,seq,pending,final_text=rebuild(store,claimed.thread_id,run_id)

    def between():
        if store.cancel_requested(run_id):
            if not store.mark_cancelled(run_id,worker_id): raise LeaseLost()
            return "cancelled"
        if not store.heartbeat(run_id,worker_id,lease_seconds): raise LeaseLost()
        return None

    if final_text is not None:
        if not store.complete(run_id,worker_id,final_text): raise LeaseLost()
        return "succeeded"

    while True:
        for step_seq,call in pending:
            if between(): return "cancelled"
            key=idempotency_key(run_id,step_seq,call["name"],call["args"])
            start=time.perf_counter()
            result=call_tool(agent,db,key,call["name"],call["args"])
            ms=round((time.perf_counter()-start)*1000)
            ok="error" not in result
            if record_delay: time.sleep(record_delay)
            store.record_tool_call(run_id,step_seq,call["name"],call["args"],result,ok,ms,key)
            contents.append({"role":"tool","name":call["name"],"result":result})
            if on_step:on_step({"kind":"tool","tool":call["name"],"result":result,"step":step_seq})
        pending=[]
        if seq>=MAX_STEPS: raise AgentError("step_limit","step limit reached",False)
        if between(): return "cancelled"
        turn=provider.generate(system,contents,functions)
        seq+=1
        calls=[{"name":c.name,"args":c.args} for c in turn.tool_calls]
        store.record_model_step(run_id,seq,turn.tokens_in,turn.tokens_out,turn.text,calls)
        if on_step:on_step({"kind":"model","step":seq,"text":turn.text,"tool_calls":calls})
        if not calls:
            if not store.complete(run_id,worker_id,turn.text or ""): raise LeaseLost()
            return "succeeded"
        contents.append({"role":"model","text":turn.text,"raw":turn.raw,"tool_calls":calls})
        pending=[(seq+i+1,c) for i,c in enumerate(calls)]
        seq+=len(calls)
