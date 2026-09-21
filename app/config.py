import os
from app.memory import RunStore
from app.canteen_db import CanteenDb
AGENT_DB=os.environ.get("AGENT_DB","agent.db")
CANTEEN_DB=os.environ.get("CANTEEN_DB","canteen.db")
GEMINI_MODEL=os.environ.get("GEMINI_MODEL","gemini-2.5-flash")
def open_stores():
    s=CanteenDb(CANTEEN_DB); a=RunStore(AGENT_DB); a.migrate(); s.migrate(); return a,s
def make_provider(mock=False,slow=0):
    if mock:
        from app.providers import booking_mock
        return booking_mock(slow)
    from app.providers import GeminiProvider
    return GeminiProvider(GEMINI_MODEL)
