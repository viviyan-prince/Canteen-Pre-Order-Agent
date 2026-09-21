"""Multi-agent layer.

Supervisor owns the write-capable canteen tools.
MenuSpecialist is deliberately read-only and can be called by the supervisor.
"""
from app.tools.canteen_tools import CanteenTools, MenuSpecialist

class SupervisorAgent:
    def __init__(self,tools:CanteenTools):
        self.tools=tools
        self.menu_specialist=MenuSpecialist(tools)

    def delegate_to_menu_specialist(self,question:str)->dict:
        """Delegate menu/wallet questions to the read-only Menu Specialist.
        Use when the request needs menu or wallet facts. Do NOT use it to place/cancel orders."""
        return self.menu_specialist.consult(question)

    def supervisor_functions(self):
        return {**self.tools.functions(),
                "delegate_to_menu_specialist":self.delegate_to_menu_specialist}

    @property
    def write_tools(self):
        return set(self.tools.SIDE_EFFECTS)
