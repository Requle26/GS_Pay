from pydantic import BaseModel


class StudentResponse(BaseModel):
    student_number: str
    name: str
    nfc_serial: str
    balance: int
    status: str