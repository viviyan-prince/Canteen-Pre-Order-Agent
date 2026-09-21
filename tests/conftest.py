import pytest
from app.canteen_db import CanteenDb
from app.memory import RunStore
from app.agents import SupervisorAgent
from app.tools.canteen_tools import CanteenTools

@pytest.fixture
def stores(tmp_path):
    db=CanteenDb(str(tmp_path/"canteen.db")); agent=RunStore(str(tmp_path/"agent.db"))
    db.migrate(); agent.migrate()
    return agent,db

@pytest.fixture
def tools(stores):
    _,db=stores
    return CanteenTools(db)
