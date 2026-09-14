from datetime import datetime

from pydantic import BaseModel


class Observation(BaseModel):
    """One dispatch interval for one NEM region."""

    settlement_date: datetime
    region_id: str
    total_demand: float
    price: float
    scheduled_generation: float
    semi_scheduled_generation: float

    def key(self) -> tuple[str, str]:
        """Identity for deduplication. Two observations with the same key
        describe the same interval and must never both be stored."""
        return (self.settlement_date.isoformat(), self.region_id)
