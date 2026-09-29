from pydantic import BaseModel


class PaymentResponse(BaseModel):
    menu: dict
    student: dict