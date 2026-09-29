from pydantic import BaseModel


class TransactionResponse(BaseModel):
    type: str
    amount: int
    balance_after: int
    created_at: str | None = None