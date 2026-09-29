import logging

from fastapi import HTTPException

from app.database import get_supabase
from app.security import server_error
from app.services.transaction_service import insert_transaction


logger = logging.getLogger(__name__)


def pay_menu(
    admin: dict,
    menu_id: str,
    nfc_serial: str | None,
):
    nfc_serial = (nfc_serial or "").strip()

    if not nfc_serial:
        raise HTTPException(
            status_code=400,
            detail="학생증을 인식해주세요.",
        )

    supabase = get_supabase()

    menu_response = (
        supabase
        .table("menus")
        .select(
            "id, booth_id, name, price, status"
        )
        .eq("id", menu_id)
        .eq("booth_id", admin["booth_id"])
        .eq("status", "ACTIVE")
        .limit(1)
        .execute()
    )

    if not menu_response.data:
        raise HTTPException(
            status_code=404,
            detail="판매 중인 메뉴가 아닙니다.",
        )

    menu = menu_response.data[0]

    student_response = (
        supabase
        .table("students")
        .select(
            "id, name, balance, status"
        )
        .eq("nfc_serial", nfc_serial)
        .limit(1)
        .execute()
    )

    if not student_response.data:
        raise HTTPException(
            status_code=404,
            detail="등록되지 않은 학생증입니다.",
        )

    student = student_response.data[0]

    status = str(
        student.get("status", "")
    ).upper()

    if status == "SUSPEND":
        raise HTTPException(
            status_code=403,
            detail="이용 정지된 학생증입니다.",
        )

    if status != "ACTIVE":
        raise HTTPException(
            status_code=403,
            detail="사용할 수 없는 학생증입니다.",
        )

    price = int(menu["price"])
    current_balance = int(
        student.get("balance") or 0
    )

    if current_balance < price:
        raise HTTPException(
            status_code=409,
            detail=(
                f"잔액이 부족합니다. "
                f"현재 잔액: {current_balance:,}원"
            ),
        )

    balance_after = current_balance - price

    update_response = (
        supabase
        .table("students")
        .update(
            {
                "balance": balance_after,
            }
        )
        .eq("id", student["id"])
        .eq("status", "ACTIVE")
        .eq("balance", current_balance)
        .select(
            "id, name, balance, status"
        )
        .execute()
    )

    if not update_response.data:
        raise HTTPException(
            status_code=409,
            detail=(
                "잔액이 변경되었습니다. "
                "다시 결제해주세요."
            ),
        )

    try:
        insert_transaction(
            admin=admin,
            student_id=str(student["id"]),
            transaction_type="SPEND",
            amount=price,
            balance_after=balance_after,
            description=f"{menu['name']} 결제",
        )

    except Exception as error:
        logger.exception(
            "Booth payment transaction insert failed"
        )

        try:
            (
                supabase
                .table("students")
                .update(
                    {
                        "balance": current_balance,
                    }
                )
                .eq("id", student["id"])
                .eq("balance", balance_after)
                .execute()
            )

        except Exception:
            logger.exception(
                "Payment balance rollback failed"
            )

        raise server_error(
            "결제 내역을 저장하지 못했습니다."
        ) from error

    return {
        "menu": menu,
        "student": update_response.data[0],
    }