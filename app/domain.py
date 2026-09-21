from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class MenuItem:
    id: int
    name: str
    category: str
    price_paise: int
    stock_count: int
    active: bool

    @property
    def price_rupees(self) -> float:
        return self.price_paise / 100

@dataclass(frozen=True)
class Policy:
    key: str
    value: str
