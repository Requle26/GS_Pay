import logging

from fastapi import HTTPException

from app.database import get_supabase


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
    
    try:
        rpc_response = supabase.rpc(
            "process_payment",
            {
                "p_student_id": str(student["id"]),
                "p_booth_id": str(admin["booth_id"]),
                "p_admin_id": str(admin["id"]),
                "p_menu_id": str(menu_id),
            },
        ).execute()

    except Exception as error:
        logger.exception("Booth payment RPC failed")
        raise HTTPException(
            status_code=500,
            detail="결제 처리에 실패했습니다.",
        ) from error

    return {
        "menu": menu,
        "student": rpc_response.data["student"],
    }