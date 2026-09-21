from dataclasses import dataclass, field
from typing import Any

class AgentError(Exception):
    def __init__(self,code,message,retryable=False):
        super().__init__(message); self.code=code; self.message=message; self.retryable=retryable

@dataclass
class ToolCall:
    name:str
    args:dict

@dataclass
class ModelTurn:
    text:str|None
    tool_calls:list[ToolCall]=field(default_factory=list)
    tokens_in:int=0
    tokens_out:int=0
    raw:Any=None

class GeminiProvider:
    def __init__(self,model):
        from google import genai
        self.client=genai.Client()
        self.model=model
    def _to_gemini(self,contents):
        from google.genai import types
        out=[]
        for c in contents:
            if c["role"]=="user":
                out.append(types.Content(role="user",parts=[types.Part.from_text(text=c["text"])]))
            elif c["role"]=="model":
                if c.get("raw") is not None: out.append(c["raw"]); continue
                parts=[types.Part.from_text(text=c["text"])] if c.get("text") else []
                parts += [types.Part.from_function_call(name=t["name"],args=t["args"]) for t in c.get("tool_calls",[])]
                out.append(types.Content(role="model",parts=parts))
            elif c["role"]=="tool":
                part=types.Part.from_function_response(name=c["name"],response=c["result"])
                if out and out[-1].role=="user" and all(p.function_response for p in out[-1].parts):
                    out[-1].parts.append(part)
                else: out.append(types.Content(role="user",parts=[part]))
        return out
    def generate(self,system,contents,tools):
        from google.genai import errors,types
        cfg=types.GenerateContentConfig(system_instruction=system,tools=tools,temperature=0,
             automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True))
        try: resp=self.client.models.generate_content(model=self.model,contents=self._to_gemini(contents),config=cfg)
        except errors.APIError as e:
            if e.code==429: raise AgentError("provider_rate_limited","Model quota exhausted.",True)
            if e.code and e.code>=500: raise AgentError("provider_unavailable","Provider unavailable.",True)
            raise AgentError("provider_error",str(e),False)
        content=resp.candidates[0].content if resp.candidates else None
        parts=(content.parts or []) if content else []
        text="".join(p.text for p in parts if p.text and not p.thought) or None
        calls=[ToolCall(fc.name,dict(fc.args or {})) for fc in (resp.function_calls or [])]
        usage=resp.usage_metadata
        return ModelTurn(text=text,tool_calls=calls,
            tokens_in=(usage.prompt_token_count or 0) if usage else 0,
            tokens_out=(usage.candidates_token_count or 0) if usage else 0,raw=content)

class PositionalMock:
    """Crash-safe scripted model. It chooses the next turn by the number of recorded model turns."""
    model="mock"
    def __init__(self,turns,slow=0.0):
        self.turns=turns; self.slow=slow; self.calls=[]
    def generate(self,system,contents,tools):
        import time
        self.calls.append([dict(c) for c in contents])
        last_user=max(i for i,c in enumerate(contents) if c["role"]=="user")
        position=sum(1 for c in contents[last_user:] if c["role"]=="model")
        if self.slow: time.sleep(self.slow)
        if position>=len(self.turns): return ModelTurn(text="(mock) script exhausted")
        return self.turns[position]

def booking_mock(slow=0.0):
    return PositionalMock([
        ModelTurn(None,[ToolCall("delegate_to_menu_specialist",{"question":"Show today's menu for student 22CS045"})],50,10),
        ModelTurn(None,[ToolCall("check_wallet",{"student_id":"22CS045"})],60,10),
        ModelTurn(None,[ToolCall("place_order",{"student_id":"22CS045","items":[{"item_id":1,"quantity":1},{"item_id":3,"quantity":2}],"client_request_id":"demo-order-001"})],120,15),
        ModelTurn(None,[ToolCall("notify_student",{"student_id":"22CS045","message":"Your canteen order is confirmed."})],80,12),
        ModelTurn(text="Done. Your canteen order is confirmed and the notification was queued.",tokens_in=100,tokens_out=20)
    ],slow=slow)
