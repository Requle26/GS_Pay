from pydantic import BaseModel


class MenuResponse(BaseModel):
    id: str
    booth_id: str
    name: str
    price: int
    status: str