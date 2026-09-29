import logging

from fastapi import HTTPException

from app.database import get_supabase
from app.security import (
    MAX_CHARGE_AMOUNT,
    validate_balance_value,
    validate_charge_amount,
    server_error,
)
from app.services.transaction_service import (
    insert_transaction,
)


logger = logging.getLogger(__name__)


def get_exchange_students():
    response = (
        get_supabase()
        .table("students")
        .select(
            "student_number, name, nfc_serial, "
            "balance, status, created_at, updated_at"
        )
        .execute()
    )

    return response.data or []


def get_student_for_exchange(
    serial_number: str,
):
    serial_number = serial_number.strip()

    if not serial_number:
        raise HTTPException(
            status_code=400,
            detail="시리얼 번호를 입력해주세요.",
        )

    response = (
        get_supabase()
        .table("students")
        .select(
            "student_number, name, nfc_serial, "
            "balance, status, created_at, updated_at, id"
        )
        .eq("nfc_serial", serial_number)
        .limit(1)
        .execute()
    )

    if not response.data:
        return {
            "exists": False,
            "student": None,
        }

    student = response.data[0]

    student.pop("id", None)

    return {
        "exists": True,
        "can_charge": (
            str(
                student.get("status", "")
            ).upper()
            == "ACTIVE"
        ),
        "student": student,
    }


def create_student(
    admin: dict,
    nfc_serial: str | None,
    student_number: str | None,
    name: str | None,
    amount: int | None,
):
    nfc_serial = (nfc_serial or "").strip()
    student_number = (student_number or "").strip()
    name = (name or "").strip()

    if (
        not nfc_serial
        or not student_number
        or not name
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "학생증, 학번, 이름은 필수입니다."
            ),
        )

    if amount is None or amount < 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "충전 금액은 0원 이상이어야 합니다."
            ),
        )

    if amount > 0:
        validate_charge_amount(amount)

    validate_balance_value(amount)

    try:
        existing_response = (
            get_supabase()
            .table("students")
            .select("id")
            .eq("nfc_serial", nfc_serial)
            .limit(1)
            .execute()
        )

        if existing_response.data:
            raise HTTPException(
                status_code=409,
                detail="이미 등록된 학생증입니다.",
            )

        insert_response = (
            get_supabase()
            .table("students")
            .insert(
                {
                    "nfc_serial": nfc_serial,
                    "student_number": student_number,
                    "name": name,
                    "balance": amount,
                    "status": "ACTIVE",
                }
            )
            .execute()
        )

    except HTTPException:
        raise

    except Exception as error:
        logger.exception(
            "Student registration failed"
        )

        raise server_error(
            "학생 정보를 저장하지 못했습니다."
        ) from error

    if not insert_response.data:
        raise HTTPException(
            status_code=500,
            detail="학생 정보를 저장하지 못했습니다.",
        )

    student_record = insert_response.data[0]
    student_id = student_record.get("id")

    if not student_id:
        raise HTTPException(
            status_code=500,
            detail="학생 ID를 확인하지 못했습니다.",
        )

    if amount > 0:
        try:
            insert_transaction(
                admin=admin,
                student_id=str(student_id),
                transaction_type="CHARGE",
                amount=amount,
                balance_after=amount,
                description="신규 학생증 등록 초기 충전",
            )

        except Exception as error:
            logger.exception(
                "Initial charge transaction failed"
            )

            try:
                (
                    get_supabase()
                    .table("students")
                    .delete()
                    .eq("id", student_id)
                    .execute()
                )
            except Exception:
                logger.exception(
                    "Student rollback failed"
                )

            raise server_error(
                "충전 거래 내역을 저장하지 못했습니다."
            ) from error

    student = {
        column: value
        for column, value in student_record.items()
        if column != "id"
    }

    return {
        "student": student,
    }


def charge_student(
    admin: dict,
    serial_number: str,
    amount: int | None,
):
    serial_number = serial_number.strip()

    if amount is None or amount <= 0:
        raise HTTPException(
            status_code=400,
            detail="충전 금액은 1원 이상이어야 합니다.",
        )

    validate_charge_amount(amount)

    try:
        student_response = (
            get_supabase()
            .table("students")
            .select(
                "id, student_number, name, "
                "nfc_serial, balance, status"
            )
            .eq("nfc_serial", serial_number)
            .eq("status", "ACTIVE")
            .limit(1)
            .execute()
        )

    except Exception as error:
        logger.exception(
            "Student lookup before charge failed"
        )

        raise server_error(
            "학생 잔액을 확인하지 못했습니다."
        ) from error

    if not student_response.data:
        raise HTTPException(
            status_code=404,
            detail="등록된 학생증이 아닙니다.",
        )

    student = student_response.data[0]
    student_id = student.get("id")

    if not student_id:
        raise HTTPException(
            status_code=500,
            detail="학생 ID를 확인하지 못했습니다.",
        )

    try:
        current_balance = int(
            student.get("balance") or 0
        )
    except (TypeError, ValueError) as error:
        raise HTTPException(
            status_code=500,
            detail="현재 잔액 형식이 올바르지 않습니다.",
        ) from error

    updated_balance = current_balance + amount

    validate_balance_value(
        updated_balance
    )

    try:
        update_response = (
            get_supabase()
            .table("students")
            .update(
                {
                    "balance": updated_balance,
                }
            )
            .eq("nfc_serial", serial_number)
            .eq("status", "ACTIVE")
            .eq("balance", current_balance)
            .select(
                "id, student_number, name, "
                "nfc_serial, balance, status"
            )
            .execute()
        )

    except Exception as error:
        logger.exception(
            "Student charge update failed"
        )

        raise server_error(
            "충전 정보를 저장하지 못했습니다."
        ) from error

    if not update_response.data:
        raise HTTPException(
            status_code=409,
            detail=(
                "잔액이 변경되었습니다. "
                "학생증을 다시 조회한 뒤 "
                "충전해주세요."
            ),
        )

    try:
        insert_transaction(
            admin=admin,
            student_id=str(student_id),
            transaction_type="CHARGE",
            amount=amount,
            balance_after=updated_balance,
            description="환전소 포인트 충전",
        )

    except Exception as error:
        logger.exception(
            "Charge transaction insert failed"
        )

        try:
            (
                get_supabase()
                .table("students")
                .update(
                    {
                        "balance": current_balance,
                    }
                )
                .eq("id", student_id)
                .eq("balance", updated_balance)
                .execute()
            )
        except Exception:
            logger.exception(
                "Balance rollback failed"
            )

        raise server_error(
            "충전 거래 내역을 저장하지 못했습니다."
        ) from error

    updated_student = {
        column: value
        for column, value
        in update_response.data[0].items()
        if column != "id"
    }

    return {
        "student": updated_student,
    }


def update_student_balance(
    admin: dict,
    serial_number: str,
    balance: int | None,
):
    serial_number = serial_number.strip()

    if not serial_number:
        raise HTTPException(
            status_code=400,
            detail="시리얼 번호를 입력해주세요.",
        )

    if balance is None or balance < 0:
        raise HTTPException(
            status_code=400,
            detail="잔액은 0원 이상이어야 합니다.",
        )

    validate_balance_value(balance)

    try:
        student_response = (
            get_supabase()
            .table("students")
            .select(
                "id, student_number, name, "
                "nfc_serial, balance, status"
            )
            .eq("nfc_serial", serial_number)
            .eq("status", "ACTIVE")
            .limit(1)
            .execute()
        )

    except Exception as error:
        logger.exception(
            "Student lookup before balance adjustment failed"
        )

        raise server_error(
            "학생 잔액을 확인하지 못했습니다."
        ) from error

    if not student_response.data:
        raise HTTPException(
            status_code=404,
            detail="등록된 학생증이 아닙니다.",
        )

    student = student_response.data[0]
    student_id = student.get("id")

    try:
        current_balance = int(
            student.get("balance") or 0
        )
    except (TypeError, ValueError) as error:
        raise HTTPException(
            status_code=500,
            detail="현재 잔액 형식이 올바르지 않습니다.",
        ) from error

    if balance == current_balance:
        raise HTTPException(
            status_code=400,
            detail=(
                "현재 잔액과 다른 금액을 "
                "입력해주세요."
            ),
        )

    balance_delta = balance - current_balance

    if abs(balance_delta) > MAX_CHARGE_AMOUNT:
        raise HTTPException(
            status_code=400,
            detail=(
                f"1회 잔액 조정 한도는 "
                f"{MAX_CHARGE_AMOUNT:,}원입니다."
            ),
        )

    try:
        update_response = (
            get_supabase()
            .table("students")
            .update(
                {
                    "balance": balance,
                }
            )
            .eq("id", student_id)
            .eq("status", "ACTIVE")
            .eq("balance", current_balance)
            .select(
                "id, student_number, name, "
                "nfc_serial, balance, status"
            )
            .execute()
        )

    except Exception as error:
        logger.exception(
            "Student balance adjustment failed"
        )

        raise server_error(
            "잔액을 수정하지 못했습니다."
        ) from error

    if not update_response.data:
        raise HTTPException(
            status_code=409,
            detail=(
                "잔액이 변경되었습니다. "
                "학생증을 다시 조회한 뒤 "
                "수정해주세요."
            ),
        )

    try:
        insert_transaction(
            admin=admin,
            student_id=str(student_id),
            transaction_type="ADJUSTMENT",
            amount=balance_delta,
            balance_after=balance,
            description="환전소 잔액 직접 수정",
        )

    except Exception as error:
        logger.exception(
            "Balance adjustment transaction insert failed"
        )

        try:
            (
                get_supabase()
                .table("students")
                .update(
                    {
                        "balance": current_balance,
                    }
                )
                .eq("id", student_id)
                .eq("balance", balance)
                .execute()
            )
        except Exception:
            logger.exception(
                "Balance rollback failed"
            )

        raise server_error(
            "잔액 수정 거래 내역을 저장하지 못했습니다."
        ) from error

    updated_student = {
        column: value
        for column, value
        in update_response.data[0].items()
        if column != "id"
    }

    return {
        "student": updated_student,
    }


def update_student_profile(
    admin: dict,
    serial_number: str,
    student_number: str | None,
    name: str | None,
):
    serial_number = serial_number.strip()
    student_number = (student_number or "").strip()
    name = (name or "").strip()

    if not serial_number:
        raise HTTPException(
            status_code=400,
            detail="시리얼 번호를 입력해주세요.",
        )

    if not student_number or not name:
        raise HTTPException(
            status_code=400,
            detail="학번과 이름은 필수입니다.",
        )

    try:
        student_response = (
            get_supabase()
            .table("students")
            .select(
                "id, student_number, name, "
                "nfc_serial, balance, status"
            )
            .eq("nfc_serial", serial_number)
            .limit(1)
            .execute()
        )

    except Exception as error:
        logger.exception(
            "Student lookup before profile update failed"
        )

        raise server_error(
            "학생 정보를 확인하지 못했습니다."
        ) from error

    if not student_response.data:
        raise HTTPException(
            status_code=404,
            detail="등록된 학생증이 아닙니다.",
        )

    student_id = student_response.data[0].get("id")

    if not student_id:
        raise HTTPException(
            status_code=500,
            detail="학생 ID를 확인하지 못했습니다.",
        )

    try:
        update_response = (
            get_supabase()
            .table("students")
            .update(
                {
                    "student_number": student_number,
                    "name": name,
                }
            )
            .eq("id", student_id)
            .eq("nfc_serial", serial_number)
            .select(
                "id, student_number, name, "
                "nfc_serial, balance, status"
            )
            .execute()
        )

    except Exception as error:
        logger.exception(
            "Student profile update failed"
        )

        raise server_error(
            "학생 정보를 수정하지 못했습니다."
        ) from error

    if not update_response.data:
        raise HTTPException(
            status_code=500,
            detail="학생 정보가 수정되지 않았습니다.",
        )

    updated_student = {
        column: value
        for column, value
        in update_response.data[0].items()
        if column != "id"
    }

    return {
        "student": updated_student,
    }


def suspend_student(
    admin: dict,
    serial_number: str,
):
    serial_number = serial_number.strip()

    if not serial_number:
        raise HTTPException(
            status_code=400,
            detail="시리얼 번호를 입력해주세요.",
        )

    try:
        update_response = (
            get_supabase()
            .table("students")
            .update(
                {
                    "status": "SUSPEND",
                }
            )
            .eq("nfc_serial", serial_number)
            .eq("status", "ACTIVE")
            .select(
                "id, student_number, name, "
                "nfc_serial, balance, status"
            )
            .execute()
        )

    except Exception as error:
        logger.exception(
            "Student suspension failed"
        )

        raise server_error(
            "학생증 이용 정지에 실패했습니다."
        ) from error

    if not update_response.data:
        student_response = (
            get_supabase()
            .table("students")
            .select("status")
            .eq("nfc_serial", serial_number)
            .limit(1)
            .execute()
        )

        if not student_response.data:
            raise HTTPException(
                status_code=404,
                detail="등록된 학생증이 아닙니다.",
            )

        raise HTTPException(
            status_code=409,
            detail=(
                "이미 정지되었거나 "
                "상태가 변경되었습니다."
            ),
        )

    student = {
        column: value
        for column, value
        in update_response.data[0].items()
        if column != "id"
    }

    return {
        "student": student,
    }


def unsuspend_student(
    admin: dict,
    serial_number: str,
):
    serial_number = serial_number.strip()

    if not serial_number:
        raise HTTPException(
            status_code=400,
            detail="시리얼 번호를 입력해주세요.",
        )

    try:
        update_response = (
            get_supabase()
            .table("students")
            .update(
                {
                    "status": "ACTIVE",
                }
            )
            .eq("nfc_serial", serial_number)
            .eq("status", "SUSPEND")
            .select(
                "id, student_number, name, "
                "nfc_serial, balance, status"
            )
            .execute()
        )

    except Exception as error:
        logger.exception(
            "Student unsuspension failed"
        )

        raise server_error(
            "학생증 이용 정지 해제에 실패했습니다."
        ) from error

    if not update_response.data:
        student_response = (
            get_supabase()
            .table("students")
            .select("status")
            .eq("nfc_serial", serial_number)
            .limit(1)
            .execute()
        )

        if not student_response.data:
            raise HTTPException(
                status_code=404,
                detail="등록된 학생증이 아닙니다.",
            )

        raise HTTPException(
            status_code=409,
            detail=(
                "정지 상태가 아니거나 "
                "상태가 변경되었습니다."
            ),
        )

    student = {
        column: value
        for column, value
        in update_response.data[0].items()
        if column != "id"
    }

    return {
        "student": student,
    }


def get_card_student(
    serial_number: str,
):
    serial_number = serial_number.strip()

    if not serial_number:
        raise HTTPException(
            status_code=400,
            detail="Card serial number is required",
        )

    response = (
        get_supabase()
        .table("students")
        .select(
            "student_number, name, "
            "balance, status"
        )
        .eq("nfc_serial", serial_number)
        .limit(1)
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=404,
            detail="Card information not found",
        )

    student = response.data[0]

    status = str(
        student.get("status", "")
    ).upper()

    if status == "SUSPEND":
        raise HTTPException(
            status_code=403,
            detail="이용 정지된 학생증입니다.",
            headers={
                "X-Card-Status": "SUSPEND"
            },
        )

    if status != "ACTIVE":
        raise HTTPException(
            status_code=403,
            detail="사용할 수 없는 학생증입니다.",
        )

    return student


def get_card_transactions(
    serial_number: str,
):
    serial_number = serial_number.strip()

    if not serial_number:
        raise HTTPException(
            status_code=400,
            detail="Card serial number is required",
        )

    student_response = (
        get_supabase()
        .table("students")
        .select("id")
        .eq("nfc_serial", serial_number)
        .eq("status", "ACTIVE")
        .limit(1)
        .execute()
    )

    if not student_response.data:
        raise HTTPException(
            status_code=404,
            detail="Card information not found",
        )

    transactions_response = (
        get_supabase()
        .table("transactions")
        .select(
            "type, amount, "
            "balance_after, created_at"
        )
        .eq(
            "student_id",
            student_response.data[0]["id"],
        )
        .order(
            "created_at",
            desc=True,
        )
        .limit(20)
        .execute()
    )

    return {
        "transactions": (
            transactions_response.data or []
        ),
    }