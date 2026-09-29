from fastapi import HTTPException

from app.database import get_supabase
from app.security import validate_menu_price


def get_booth_dashboard_data(
    booth_id: str,
):
    supabase = get_supabase()

    booth_response = (
        supabase
        .table("booths")
        .select("id, name, status")
        .eq("id", booth_id)
        .limit(1)
        .execute()
    )

    booth = (
        booth_response.data[0]
        if booth_response.data
        else {
            "id": booth_id,
            "name": "부스",
            "status": "ACTIVE",
        }
    )

    menus_response = (
        supabase
        .table("menus")
        .select(
            "id, name, price, status"
        )
        .eq("booth_id", booth_id)
        .eq("status", "ACTIVE")
        .order("created_at")
        .execute()
    )

    return booth, menus_response.data or []


def create_menu(
    booth_id: str,
    name: str | None,
    price: int | None,
):
    name = (name or "").strip()

    if not name:
        raise HTTPException(
            status_code=400,
            detail="메뉴 이름은 필수입니다.",
        )

    if price is None:
        raise HTTPException(
            status_code=400,
            detail="메뉴 가격은 1원 이상이어야 합니다.",
        )

    validate_menu_price(price)

    response = (
        get_supabase()
        .table("menus")
        .insert(
            {
                "booth_id": booth_id,
                "name": name,
                "price": price,
                "status": "ACTIVE",
            }
        )
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=500,
            detail="메뉴를 추가하지 못했습니다.",
        )

    return {
        "menu": response.data[0],
    }


def update_menu(
    booth_id: str,
    menu_id: str,
    name: str | None,
    price: int | None,
):
    name = (name or "").strip()

    if not name:
        raise HTTPException(
            status_code=400,
            detail="메뉴 이름은 필수입니다.",
        )

    if price is None:
        raise HTTPException(
            status_code=400,
            detail="메뉴 가격은 1원 이상이어야 합니다.",
        )

    validate_menu_price(price)

    response = (
        get_supabase()
        .table("menus")
        .update(
            {
                "name": name,
                "price": price,
            }
        )
        .eq("id", menu_id)
        .eq("booth_id", booth_id)
        .select(
            "id, booth_id, name, price, status"
        )
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=404,
            detail="메뉴를 찾을 수 없습니다.",
        )

    return {
        "menu": response.data[0],
    }


def delete_menu(
    booth_id: str,
    menu_id: str,
):
    response = (
        get_supabase()
        .table("menus")
        .delete()
        .eq("id", menu_id)
        .eq("booth_id", booth_id)
        .select("id")
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=404,
            detail="메뉴를 찾을 수 없습니다.",
        )

    return {
        "deleted": True,
        "menu_id": menu_id,
    }