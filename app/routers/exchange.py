from fastapi import APIRouter, Form, Request

from app.auth import get_exchange_admin
from app.services.student_service import (
    create_student,
    get_student_for_exchange,
    charge_student,
    update_student_balance,
    update_student_profile,
    suspend_student,
    unsuspend_student,
)


router = APIRouter(
    prefix="/api/exchange",
)


@router.get("/students/{serial_number}")
def get_exchange_student(
    serial_number: str,
    request: Request,
):
    get_exchange_admin(request)

    return get_student_for_exchange(
        serial_number
    )


@router.post("/students")
def create_exchange_student(
    request: Request,
    nfc_serial: str | None = Form(default=None),
    student_number: str | None = Form(default=None),
    name: str | None = Form(default=None),
    amount: int | None = Form(default=None),
):
    admin = get_exchange_admin(request)

    return create_student(
        admin=admin,
        nfc_serial=nfc_serial,
        student_number=student_number,
        name=name,
        amount=amount,
    )


@router.post("/students/{serial_number}/charge")
def charge_exchange_student(
    serial_number: str,
    request: Request,
    amount: int | None = Form(default=None),
):
    admin = get_exchange_admin(request)

    return charge_student(
        admin=admin,
        serial_number=serial_number,
        amount=amount,
    )


@router.post("/students/{serial_number}/balance")
def update_exchange_student_balance(
    serial_number: str,
    request: Request,
    balance: int | None = Form(default=None),
):
    admin = get_exchange_admin(request)

    return update_student_balance(
        admin=admin,
        serial_number=serial_number,
        balance=balance,
    )


@router.post("/students/{serial_number}/profile")
def update_exchange_student_profile(
    serial_number: str,
    request: Request,
    student_number: str | None = Form(default=None),
    name: str | None = Form(default=None),
):
    admin = get_exchange_admin(request)

    return update_student_profile(
        admin=admin,
        serial_number=serial_number,
        student_number=student_number,
        name=name,
    )


@router.post("/students/{serial_number}/suspend")
def suspend_exchange_student(
    serial_number: str,
    request: Request,
):
    admin = get_exchange_admin(request)

    return suspend_student(
        admin=admin,
        serial_number=serial_number,
    )


@router.post("/students/{serial_number}/unsuspend")
def unsuspend_exchange_student(
    serial_number: str,
    request: Request,
):
    admin = get_exchange_admin(request)

    return unsuspend_student(
        admin=admin,
        serial_number=serial_number,
    )