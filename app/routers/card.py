from fastapi import APIRouter

from app.services.student_service import (
    get_card_student,
    get_card_transactions,
)


router = APIRouter(
    prefix="/api/cards",
)


@router.get("/{serial_number}")
def get_card_balance(
    serial_number: str,
):
    return get_card_student(
        serial_number
    )


@router.get("/{serial_number}/transactions")
def get_card_transaction_history(
    serial_number: str,
):
    return get_card_transactions(
        serial_number
    )