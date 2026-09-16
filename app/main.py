from pathlib import Path
import logging

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.auth import (
    ADMIN_COOKIE_NAME,
    get_auth_client,
    get_current_admin,
    use_secure_cookie,
)
from app.database import get_supabase



BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="GS Pay")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")
logger = logging.getLogger(__name__)

ROLE_DASHBOARD_URLS = {
    "ADMIN": "/admin",
    "BOOTH": "/booth",
    "EXCHANGE": "/exchange",
}


def get_dashboard_url(admin: dict) -> str:
    role = str(admin.get("role", "")).upper()
    return ROLE_DASHBOARD_URLS.get(role, "/login")


def require_role(request: Request, role: str):
    admin = get_current_admin(request)
    if admin is None:
        return None, RedirectResponse(url="/login", status_code=303)

    if str(admin.get("role", "")).upper() != role:
        return admin, RedirectResponse(url=get_dashboard_url(admin), status_code=303)

    return admin, None


def get_exchange_admin(request: Request) -> dict:
    admin = get_current_admin(request)
    if admin is None or str(admin.get("role", "")).upper() != "EXCHANGE":
        raise HTTPException(status_code=403, detail="Exchange permission required")
    return admin


@app.get("/", name="home")
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"title": "GS Pay"},
    )


@app.get("/login", name="login_form")
def login_form(request: Request):
    admin = get_current_admin(request)
    if admin:
        return RedirectResponse(url=get_dashboard_url(admin), status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"title": "관리자 로그인"},
    )


@app.post("/login", name="login")
def login(
    request: Request,
    email: str = Form(),
    password: str = Form(),
):
    try:
        auth_response = get_auth_client().auth.sign_in_with_password(
            {"email": email, "password": password}
        )
        session = auth_response.session
        user = auth_response.user
        if session is None or user is None:
            raise ValueError("Missing authentication session")

        admin_response = (
            get_supabase()
            .table("admins")
            .select("id, role")
            .eq("id", str(user.id))
            .eq("status", "ACTIVE")
            .limit(1)
            .execute()
        )
        if not admin_response.data:
            raise PermissionError("Inactive or unregistered administrator")
    except Exception:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "title": "관리자 로그인",
                "error": "이메일, 비밀번호 또는 관리자 권한을 확인해주세요.",
            },
            status_code=401,
        )

    response = RedirectResponse(url=get_dashboard_url(admin_response.data[0]), status_code=303)
    response.set_cookie(
        key=ADMIN_COOKIE_NAME,
        value=session.access_token,
        max_age=60 * 60,
        httponly=True,
        secure=use_secure_cookie(),
        samesite="lax",
    )
    return response


@app.post("/logout", name="logout")
def logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(
        key=ADMIN_COOKIE_NAME,
        httponly=True,
        secure=use_secure_cookie(),
        samesite="lax",
    )
    return response


@app.get("/admin", name="admin_dashboard")
def admin_dashboard(request: Request):
    admin, redirect = require_role(request, "ADMIN")
    if redirect:
        return redirect

    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={"title": "관리자 페이지", "admin": admin},
    )


@app.get("/booth", name="booth_dashboard")
def booth_dashboard(request: Request):
    booth, redirect = require_role(request, "BOOTH")
    if redirect:
        return redirect

    return templates.TemplateResponse(
        request=request,
        name="booth.html",
        context={"title": "부스 운영 페이지", "admin": booth},
    )


@app.get("/exchange", name="exchange_dashboard")
def exchange_dashboard(request: Request):
    exchange, redirect = require_role(request, "EXCHANGE")
    if redirect:
        return redirect

    students_response = get_supabase().table("students").select("*").execute()
    students = [
        {column: value for column, value in student.items() if column != "id"}
        for student in (students_response.data or [])
    ]
    student_columns = list(students[0].keys()) if students else []

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


@app.get("/api/cards/{serial_number}")
def get_card_balance(serial_number: str):
    response = (
        get_supabase()
        .table("students")
        .select("balance")
        .eq("nfc_serial", serial_number)
        .eq("status", "ACTIVE")
        .limit(1)
        .execute()
    )

    if not response.data:
        raise HTTPException(status_code=404, detail="Card information not found")

    return {"balance": response.data[0]["balance"]}


@app.get("/api/exchange/students/{serial_number}")
def get_exchange_student(serial_number: str, request: Request):
    get_exchange_admin(request)
    serial_number = serial_number.strip()
    if not serial_number:
        raise HTTPException(status_code=400, detail="시리얼 번호를 입력해주세요.")

    response = (
        get_supabase()
        .table("students")
        .select("*")
        .eq("nfc_serial", serial_number)
        .limit(1)
        .execute()
    )

    if not response.data:
        return {"exists": False, "student": None}

    student = {
        column: value
        for column, value in response.data[0].items()
        if column != "id"
    }
    return {
        "exists": True,
        "can_charge": str(student.get("status", "")).upper() == "ACTIVE",
        "student": student,
    }


@app.post("/api/exchange/students")
def create_exchange_student(
    request: Request,
    nfc_serial: str | None = Form(default=None),
    student_number: str | None = Form(default=None),
    name: str | None = Form(default=None),
    amount: int | None = Form(default=None),
):
    get_exchange_admin(request)

    nfc_serial = (nfc_serial or "").strip()
    student_number = (student_number or "").strip()
    name = (name or "").strip()
    if not nfc_serial or not student_number or not name:
        raise HTTPException(status_code=400, detail="학생증, 학번, 이름은 필수입니다.")
    if amount is None or amount < 0:
        raise HTTPException(status_code=400, detail="충전 금액은 0원 이상이어야 합니다.")

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
            raise HTTPException(status_code=409, detail="이미 등록된 학생증입니다.")

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
        logger.exception("Student registration failed")
        raise HTTPException(
            status_code=500,
            detail=f"학생 정보를 저장하지 못했습니다: {error}",
        ) from error
    if not insert_response.data:
        raise HTTPException(status_code=500, detail="학생 정보를 저장하지 못했습니다.")

    student = {
        column: value
        for column, value in insert_response.data[0].items()
        if column != "id"
    }
    return {"student": student}


@app.post("/api/exchange/students/{serial_number}/charge")
def charge_exchange_student(
    serial_number: str,
    request: Request,
    amount: int | None = Form(default=None),
):
    get_exchange_admin(request)
    serial_number = serial_number.strip()
    if amount is None or amount <= 0:
        raise HTTPException(status_code=400, detail="충전 금액은 1원 이상이어야 합니다.")

    try:
        student_response = (
            get_supabase()
            .table("students")
            .select("*")
            .eq("nfc_serial", serial_number)
            .eq("status", "ACTIVE")
            .limit(1)
            .execute()
        )
    except Exception as error:
        logger.exception("Student lookup before charge failed")
        raise HTTPException(
            status_code=500,
            detail=f"학생 잔액을 확인하지 못했습니다: {error}",
        ) from error

    if not student_response.data:
        raise HTTPException(status_code=404, detail="등록된 학생증이 아닙니다.")

    student = student_response.data[0]
    try:
        current_balance = int(student.get("balance") or 0)
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=500, detail="현재 잔액 형식이 올바르지 않습니다.") from error

    try:
        update_response = (
            get_supabase()
            .table("students")
            .update({"balance": current_balance + amount})
            .eq("nfc_serial", serial_number)
            .eq("status", "ACTIVE")
            .eq("balance", current_balance)
            .select("*")
            .execute()
        )
    except Exception as error:
        logger.exception("Student charge update failed")
        raise HTTPException(
            status_code=500,
            detail=f"충전 정보를 저장하지 못했습니다: {error}",
        ) from error

    if not update_response.data:
        raise HTTPException(
            status_code=409,
            detail="잔액이 변경되었습니다. 학생증을 다시 조회한 뒤 충전해주세요.",
        )

    updated_student = {
        column: value
        for column, value in update_response.data[0].items()
        if column != "id"
    }
    return {"student": updated_student}
