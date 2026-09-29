from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth import get_current_admin, require_role
from app.services.student_service import (
    get_exchange_students,
)
from app.services.menu_service import (
    get_booth_dashboard_data,
)
from app.services.transaction_service import (
    load_admin_overview,
)


BASE_DIR = Path(__file__).resolve().parents[1]

templates = Jinja2Templates(
    directory=BASE_DIR / "templates"
)

router = APIRouter()


STUDENT_LIST_COLUMNS = [
    "student_number",
    "name",
    "nfc_serial",
    "balance",
    "status",
    "created_at",
    "updated_at",
]


@router.get("/", name="home")
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "title": "GS Pay",
        },
    )


@router.get("/login", name="login_form")
def login_form(request: Request):
    admin = get_current_admin(request)

    if admin:
        from app.auth import get_dashboard_url

        return RedirectResponse(
            url=get_dashboard_url(admin),
            status_code=303,
        )

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "title": "관리자 로그인",
        },
    )


@router.get("/admin", name="admin_dashboard")
def admin_dashboard(request: Request):
    admin, redirect = require_role(
        request,
        "ADMIN",
    )

    if redirect:
        return redirect

    overview = {
        "stats": {
            "student_count": 0,
            "active_student_count": 0,
            "total_balance": 0,
            "total_charge": 0,
            "total_spend": 0,
            "booth_count": 0,
            "admin_count": 0,
            "transaction_count": 0,
        },
        "booths": [],
        "admins": [],
        "transactions": [],
    }

    admin_load_error = None

    try:
        overview = load_admin_overview()

    except Exception:
        import logging

        logging.getLogger(__name__).exception(
            "Admin dashboard data loading failed"
        )

        admin_load_error = (
            "관리 데이터를 불러오지 못했습니다. "
            "Supabase 권한을 확인해주세요."
        )

    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "title": "관리자 페이지",
            "admin": admin,
            "stats": overview["stats"],
            "booths": overview["booths"],
            "admins": overview["admins"],
            "transactions": overview["transactions"],
            "admin_load_error": admin_load_error,
        },
    )


@router.get("/booth", name="booth_dashboard")
def booth_dashboard(request: Request):
    booth, redirect = require_role(
        request,
        "BOOTH",
    )

    if redirect:
        return redirect

    booth_record = {
        "id": booth["booth_id"],
        "name": "부스",
        "status": "ACTIVE",
    }

    menus = []
    booth_load_error = None

    try:
        booth_record, menus = get_booth_dashboard_data(
            booth["booth_id"]
        )

    except Exception:
        import logging

        logging.getLogger(__name__).exception(
            "Booth dashboard data loading failed"
        )

        booth_load_error = (
            "부스 데이터를 불러오지 못했습니다. "
            "Supabase 권한을 확인해주세요."
        )

    return templates.TemplateResponse(
        request=request,
        name="booth.html",
        context={
            "title": "부스 운영 페이지",
            "admin": booth,
            "booth": booth_record,
            "menus": menus,
            "booth_load_error": booth_load_error,
        },
    )


@router.get("/exchange", name="exchange_dashboard")
def exchange_dashboard(request: Request):
    exchange, redirect = require_role(
        request,
        "EXCHANGE",
    )

    if redirect:
        return redirect

    students = get_exchange_students()

    student_columns = [
        column
        for column in STUDENT_LIST_COLUMNS
        if not students
        or any(column in student for student in students)
    ]

    return templates.TemplateResponse(
        request=request,
        name="exchange.html",
        context={
            "title": "환전소 페이지",
            "admin": exchange,
            "students": students,
            "student_columns": student_columns,
        },
    )