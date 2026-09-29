from fastapi import APIRouter, Form, Request

from app.auth import get_booth_admin

from app.services.menu_service import (
    create_menu,
    update_menu,
    delete_menu,
)
from app.services.payment_service import pay_menu
from app.services.transaction_service import (
    get_booth_sales,
)


router = APIRouter(
    prefix="/api/booth",
)


@router.get("/sales")
def booth_sales(request: Request):
    admin = get_booth_admin(request)

    return get_booth_sales(
        admin["booth_id"]
    )


@router.post("/menus")
def create_booth_menu(
    request: Request,
    name: str | None = Form(default=None),
    price: int | None = Form(default=None),
):
    admin = get_booth_admin(request)

    return create_menu(
        booth_id=admin["booth_id"],
        name=name,
        price=price,
    )


@router.post("/menus/{menu_id}")
def update_booth_menu(
    menu_id: str,
    request: Request,
    name: str | None = Form(default=None),
    price: int | None = Form(default=None),
):
    admin = get_booth_admin(request)

    return update_menu(
        booth_id=admin["booth_id"],
        menu_id=menu_id,
        name=name,
        price=price,
    )


@router.post("/menus/{menu_id}/delete")
def delete_booth_menu(
    menu_id: str,
    request: Request,
):
    admin = get_booth_admin(request)

    return delete_menu(
        booth_id=admin["booth_id"],
        menu_id=menu_id,
    )


@router.post("/menus/{menu_id}/pay")
def pay_booth_menu(
    menu_id: str,
    request: Request,
    nfc_serial: str | None = Form(default=None),
):
    admin = get_booth_admin(request)

    return pay_menu(
        admin=admin,
        menu_id=menu_id,
        nfc_serial=nfc_serial,
    )