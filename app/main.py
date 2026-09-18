from pathlib import Path
import logging
import os
import secrets

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.auth import (
    ADMIN_COOKIE_NAME,
    get_auth_client,
    get_current_admin,
    revoke_access_token,
    use_secure_cookie,
)
from app.database import get_supabase
from app.security import (
    MAX_CHARGE_AMOUNT,
    enforce_same_origin,
    server_error,
    validate_balance_value,
    validate_charge_amount,
    validate_menu_price,
)



BASE_DIR = Path(__file__).resolve().parent

_enable_docs = os.getenv("ENABLE_DOCS", "false").lower() in {"1", "true", "yes"}
app = FastAPI(
    title="GS Pay",
    docs_url="/docs" if _enable_docs else None,
    redoc_url="/redoc" if _enable_docs else None,
    openapi_url="/openapi.json" if _enable_docs else None,
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")
logger = logging.getLogger(__name__)

ROLE_DASHBOARD_URLS = {
    "ADMIN": "/admin",
    "BOOTH": "/booth",
    "EXCHANGE": "/exchange",
}

STUDENT_LIST_COLUMNS = [
    "student_number",
    "name",
    "nfc_serial",
    "balance",
    "status",
    "created_at",
    "updated_at",
]


@app.middleware("http")
async def csrf_origin_middleware(request: Request, call_next):
    try:
        enforce_same_origin(request)
    except HTTPException as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    return await call_next(request)


@app.middleware("http")
async def content_security_policy_middleware(request: Request, call_next):
    """Attach a per-response CSP nonce before rendering templates."""
    nonce = secrets.token_urlsafe(16)
    request.state.csp_nonce = nonce
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        f"script-src 'self' 'nonce-{nonce}'; "
        "style-src 'self'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "font-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none'"
    )
    return response


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


def get_booth_admin(request: Request) -> dict:
    admin = get_current_admin(request)
    if (
        admin is None
        or str(admin.get("role", "")).upper() != "BOOTH"
        or not admin.get("booth_id")
    ):
        raise HTTPException(status_code=403, detail="Booth permission required")
    return admin


def get_system_admin(request: Request) -> dict:
    admin = get_current_admin(request)
    if admin is None or str(admin.get("role", "")).upper() != "ADMIN":
        raise HTTPException(status_code=403, detail="Admin permission required")
    return admin


def load_admin_overview() -> dict:
    response = get_supabase().rpc("get_admin_dashboard_overview").execute()
    if not response.data:
        raise RuntimeError("관리 데이터를 불러오지 못했습니다.")
    return response.data


@app.get("/api/booth/sales")
def get_booth_sales(request: Request):
    admin = get_booth_admin(request)
    response = (
        get_supabase()
        .table("transactions")
        .select("id, amount, balance_after, description, created_at")
        .eq("booth_id", admin["booth_id"])
        .eq("type", "SPEND")
        .order("created_at", desc=True)
        .limit(100)
        .execute()
    )
    transactions = response.data or []
    total_sales = sum(int(transaction.get("amount") or 0) for transaction in transactions)
    return {
        "total_sales": total_sales,
        "transaction_count": len(transactions),
        "transactions": transactions,
    }


def insert_transaction(
    admin: dict,
    student_id: str,
    transaction_type: str,
    amount: int,
    balance_after: int,
    description: str,
) -> None:
    transaction_response = (
        get_supabase()
        .table("transactions")
        .insert(
            {
                "student_id": student_id,
                "booth_id": admin.get("booth_id"),
                "admin_id": admin["id"],
                "type": transaction_type,
                "amount": amount,
                "balance_after": balance_after,
                "description": description,
            }
        )
        .execute()
    )
    if not transaction_response.data:
        raise RuntimeError("거래 내역이 저장되지 않았습니다.")


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
def logout(request: Request):
    access_token = request.cookies.get(ADMIN_COOKIE_NAME)
    if access_token:
        revoke_access_token(access_token)

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
        logger.exception("Admin dashboard data loading failed")
        admin_load_error = "관리 데이터를 불러오지 못했습니다. Supabase 권한을 확인해주세요."

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


@app.post("/api/admin/booths")
def create_admin_booth(
    request: Request,
    name: str | None = Form(default=None),
):
    get_system_admin(request)
    name = (name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="부스 이름은 필수입니다.")

    try:
        response = (
            get_supabase()
            .table("booths")
            .insert({"name": name, "status": "ACTIVE"})
            .execute()
        )
    except Exception as error:
        logger.exception("Booth create failed")
        raise server_error("부스를 추가하지 못했습니다. Supabase 권한을 확인해주세요.") from error
    if not response.data:
        raise HTTPException(status_code=500, detail="부스를 추가하지 못했습니다.")
    return {"booth": response.data[0]}


@app.post("/api/admin/booths/{booth_id}")
def update_admin_booth(
    booth_id: str,
    request: Request,
    name: str | None = Form(default=None),
    status: str | None = Form(default=None),
):
    get_system_admin(request)
    name = (name or "").strip()
    status = (status or "").strip().upper()
    if not name:
        raise HTTPException(status_code=400, detail="부스 이름은 필수입니다.")
    if status not in {"ACTIVE", "INACTIVE"}:
        raise HTTPException(status_code=400, detail="부스 상태가 올바르지 않습니다.")

    try:
        response = (
            get_supabase()
            .table("booths")
            .update({"name": name, "status": status})
            .eq("id", booth_id)
            .select("id, name, status")
            .execute()
        )
    except Exception as error:
        logger.exception("Booth update failed")
        raise server_error("부스를 수정하지 못했습니다. Supabase 권한을 확인해주세요.") from error
    if not response.data:
        raise HTTPException(status_code=404, detail="부스를 찾을 수 없습니다.")
    return {"booth": response.data[0]}


@app.post("/api/admin/accounts")
def create_admin_account(
    request: Request,
    email: str | None = Form(default=None),
    password: str | None = Form(default=None),
    username: str | None = Form(default=None),
    role: str | None = Form(default=None),
    booth_id: str | None = Form(default=None),
):
    get_system_admin(request)
    email = (email or "").strip()
    password = password or ""
    username = (username or "").strip()
    role = (role or "").strip().upper()
    booth_id = (booth_id or "").strip() or None

    if not email or not password or not username:
        raise HTTPException(status_code=400, detail="이메일, 비밀번호, 이름은 필수입니다.")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="비밀번호는 6자 이상이어야 합니다.")
    if role not in {"ADMIN", "EXCHANGE", "BOOTH"}:
        raise HTTPException(status_code=400, detail="역할이 올바르지 않습니다.")
    if role == "BOOTH" and not booth_id:
        raise HTTPException(status_code=400, detail="부스 계정은 부스 연결이 필요합니다.")
    if role != "BOOTH":
        booth_id = None

    if booth_id:
        booth_response = (
            get_supabase()
            .table("booths")
            .select("id")
            .eq("id", booth_id)
            .limit(1)
            .execute()
        )
        if not booth_response.data:
            raise HTTPException(status_code=404, detail="연결할 부스를 찾을 수 없습니다.")

    try:
        auth_response = get_supabase().auth.admin.create_user(
            {
                "email": email,
                "password": password,
                "email_confirm": True,
            }
        )
        user = auth_response.user
        if user is None:
            raise RuntimeError("Auth user was not created")
        user_id = str(user.id)
    except HTTPException:
        raise
    except Exception as error:
        logger.exception("Admin account auth creation failed")
        raise server_error("인증 계정을 만들지 못했습니다. 이메일 중복 여부를 확인해주세요.") from error

    try:
        insert_response = (
            get_supabase()
            .table("admins")
            .insert(
                {
                    "id": user_id,
                    "username": username,
                    "role": role,
                    "booth_id": booth_id,
                    "status": "ACTIVE",
                }
            )
            .execute()
        )
    except Exception as error:
        logger.exception("Admin account profile insert failed")
        try:
            get_supabase().auth.admin.delete_user(user_id)
        except Exception:
            logger.exception("Auth user rollback after admin insert failure failed")
        raise server_error("관리자 프로필을 저장하지 못했습니다.") from error

    if not insert_response.data:
        try:
            get_supabase().auth.admin.delete_user(user_id)
        except Exception:
            logger.exception("Auth user rollback after empty admin insert failed")
        raise HTTPException(status_code=500, detail="관리자 프로필을 저장하지 못했습니다.")

    return {"admin": insert_response.data[0]}


@app.post("/api/admin/accounts/{admin_id}")
def update_admin_account(
    admin_id: str,
    request: Request,
    username: str | None = Form(default=None),
    role: str | None = Form(default=None),
    booth_id: str | None = Form(default=None),
    status: str | None = Form(default=None),
):
    current_admin = get_system_admin(request)
    username = (username or "").strip()
    role = (role or "").strip().upper()
    status = (status or "").strip().upper()
    booth_raw = booth_id if booth_id is not None else ""
    booth_id = booth_raw.strip() or None

    if not username:
        raise HTTPException(status_code=400, detail="계정 이름은 필수입니다.")
    if role not in {"ADMIN", "EXCHANGE", "BOOTH"}:
        raise HTTPException(status_code=400, detail="역할이 올바르지 않습니다.")
    if status not in {"ACTIVE", "INACTIVE"}:
        raise HTTPException(status_code=400, detail="계정 상태가 올바르지 않습니다.")
    if role == "BOOTH" and not booth_id:
        raise HTTPException(status_code=400, detail="부스 계정은 부스 연결이 필요합니다.")
    if role != "BOOTH":
        booth_id = None
    if admin_id == current_admin["id"] and status != "ACTIVE":
        raise HTTPException(status_code=400, detail="현재 로그인 계정은 비활성화할 수 없습니다.")
    if admin_id == current_admin["id"] and role != "ADMIN":
        raise HTTPException(status_code=400, detail="현재 로그인 계정의 역할은 변경할 수 없습니다.")

    if booth_id:
        booth_response = (
            get_supabase()
            .table("booths")
            .select("id")
            .eq("id", booth_id)
            .limit(1)
            .execute()
        )
        if not booth_response.data:
            raise HTTPException(status_code=404, detail="연결할 부스를 찾을 수 없습니다.")

    try:
        response = (
            get_supabase()
            .table("admins")
            .update(
                {
                    "username": username,
                    "role": role,
                    "booth_id": booth_id,
                    "status": status,
                }
            )
            .eq("id", admin_id)
            .select("id, username, role, booth_id, status")
            .execute()
        )
    except Exception as error:
        logger.exception("Admin account update failed")
        raise server_error("계정을 수정하지 못했습니다. Supabase 권한을 확인해주세요.") from error
    if not response.data:
        raise HTTPException(status_code=404, detail="계정을 찾을 수 없습니다.")
    return {"admin": response.data[0]}


@app.get("/api/admin/overview")
def get_admin_overview(request: Request):
    get_system_admin(request)
    try:
        return load_admin_overview()
    except Exception as error:
        logger.exception("Admin overview refresh failed")
        raise server_error("관리 데이터를 불러오지 못했습니다.") from error


@app.get("/booth", name="booth_dashboard")
def booth_dashboard(request: Request):
    booth = get_current_admin(request)
    if booth is None:
        return RedirectResponse(url="/login", status_code=303)
    if str(booth.get("role", "")).upper() != "BOOTH":
        return RedirectResponse(url=get_dashboard_url(booth), status_code=303)

    booth_record = {
        "id": booth["booth_id"],
        "name": "부스",
        "status": "ACTIVE",
    }
    menus = []
    booth_load_error = None
    try:
        booth_response = (
            get_supabase()
            .table("booths")
            .select("id, name, status")
            .eq("id", booth["booth_id"])
            .limit(1)
            .execute()
        )
        if booth_response.data:
            booth_record = booth_response.data[0]

        menus_response = (
            get_supabase()
            .table("menus")
            .select("id, name, price, status")
            .eq("booth_id", booth["booth_id"])
            .eq("status", "ACTIVE")
            .order("created_at")
            .execute()
        )
        menus = menus_response.data or []
    except Exception as error:
        logger.exception("Booth dashboard data loading failed")
        booth_load_error = "부스 데이터를 불러오지 못했습니다. Supabase 권한을 확인해주세요."

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


@app.post("/api/booth/menus")
def create_booth_menu(
    request: Request,
    name: str | None = Form(default=None),
    price: int | None = Form(default=None),
):
    admin = get_booth_admin(request)
    name = (name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="메뉴 이름은 필수입니다.")
    if price is None or price <= 0:
        raise HTTPException(status_code=400, detail="메뉴 가격은 1원 이상이어야 합니다.")
    validate_menu_price(price)

    response = (
        get_supabase()
        .table("menus")
        .insert({
            "booth_id": admin["booth_id"],
            "name": name,
            "price": price,
            "status": "ACTIVE",
        })
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=500, detail="메뉴를 추가하지 못했습니다.")
    return {"menu": response.data[0]}


@app.post("/api/booth/menus/{menu_id}")
def update_booth_menu(
    menu_id: str,
    request: Request,
    name: str | None = Form(default=None),
    price: int | None = Form(default=None),
):
    admin = get_booth_admin(request)
    name = (name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="메뉴 이름은 필수입니다.")
    if price is None or price <= 0:
        raise HTTPException(status_code=400, detail="메뉴 가격은 1원 이상이어야 합니다.")
    validate_menu_price(price)

    response = (
        get_supabase()
        .table("menus")
        .update({"name": name, "price": price})
        .eq("id", menu_id)
        .eq("booth_id", admin["booth_id"])
        .select("id, booth_id, name, price, status")
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="메뉴를 찾을 수 없습니다.")
    return {"menu": response.data[0]}


@app.post("/api/booth/menus/{menu_id}/delete")
def delete_booth_menu(menu_id: str, request: Request):
    admin = get_booth_admin(request)
    response = (
        get_supabase()
        .table("menus")
        .delete()
        .eq("id", menu_id)
        .eq("booth_id", admin["booth_id"])
        .select("id")
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="메뉴를 찾을 수 없습니다.")
    return {"deleted": True, "menu_id": menu_id}

@app.post("/api/booth/menus/{menu_id}/pay")
def pay_booth_menu(
    menu_id: str,
    request: Request,
    nfc_serial: str | None = Form(default=None),
):
    admin = get_booth_admin(request)
    nfc_serial = (nfc_serial or "").strip()
    if not nfc_serial:
        raise HTTPException(status_code=400, detail="학생증을 인식해주세요.")

    try:
        # ★ Supabase RPC 호출: get_supabase().rpc("함수이름", {매개변수})
        response = get_supabase().rpc(
            "process_booth_payment",
            {
                "p_nfc_serial": nfc_serial,
                "p_menu_id": menu_id,
                "p_booth_id": admin["booth_id"],
                "p_admin_id": admin["id"],
            }
        ).execute()

        # 결과 반환
        return response.data

    except Exception as error:
        # SQL에서 RAISE EXCEPTION으로 던진 에러 메시지가 error 객체에 포함되어 옵니다.
        error_msg = str(error)
        logger.warning(f"Payment failed: {error_msg}")
        
        # 클라이언트에게 에러 메시지 전달
        raise HTTPException(status_code=400, detail="결제 실패: " + error_msg)

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
    student_columns = [
        column for column in STUDENT_LIST_COLUMNS
        if not students or any(column in student for student in students)
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


@app.get("/api/cards/{serial_number}")
def get_card_balance(serial_number: str):
    serial_number = serial_number.strip()
    if not serial_number:
        raise HTTPException(status_code=400, detail="Card serial number is required")

    response = (
        get_supabase()
        .table("students")
        .select("student_number, name, balance, status")
        .eq("nfc_serial", serial_number)
        .limit(1)
        .execute()
    )

    if not response.data:
        raise HTTPException(status_code=404, detail="Card information not found")

    student = response.data[0]
    if str(student.get("status", "")).upper() == "SUSPEND":
        raise HTTPException(
            status_code=403,
            detail="이용 정지된 학생증입니다.",
            headers={"X-Card-Status": "SUSPEND"},
        )

    if str(student.get("status", "")).upper() != "ACTIVE":
        raise HTTPException(status_code=403, detail="사용할 수 없는 학생증입니다.")

    return {
        "student_number": student["student_number"],
        "name": student["name"],
        "balance": student["balance"],
        "status": student["status"],
    }


@app.get("/api/cards/{serial_number}/transactions")
def get_card_transactions(serial_number: str):
    serial_number = serial_number.strip()
    if not serial_number:
        raise HTTPException(status_code=400, detail="Card serial number is required")

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
        raise HTTPException(status_code=404, detail="Card information not found")

    transactions_response = (
        get_supabase()
        .table("transactions")
        .select("type, amount, balance_after, created_at")
        .eq("student_id", student_response.data[0]["id"])
        .order("created_at", desc=True)
        .limit(20)
        .execute()
    )
    return {"transactions": transactions_response.data or []}


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
    exchange_admin = get_exchange_admin(request)

    nfc_serial = (nfc_serial or "").strip()
    student_number = (student_number or "").strip()
    name = (name or "").strip()
    if not nfc_serial or not student_number or not name:
        raise HTTPException(status_code=400, detail="학생증, 학번, 이름은 필수입니다.")
    if amount is None or amount < 0:
        raise HTTPException(status_code=400, detail="충전 금액은 0원 이상이어야 합니다.")
    if amount > 0:
        validate_charge_amount(amount)
    validate_balance_value(amount)

    try:
        response = get_supabase().rpc(
            "register_student_card",
            {
                "p_nfc_serial": nfc_serial,
                "p_student_number": student_number,
                "p_name": name,
                "p_initial_amount": amount,
                "p_admin_id": exchange_admin["id"],
            }
        ).execute()
    except Exception as error:
        logger.exception("Student registration RPC failed")
        err_msg = str(error)
        detail = "학생 등록에 실패했습니다."
        if hasattr(error, "message"):
            detail = error.message
        elif "message" in err_msg:
            detail = err_msg
        raise HTTPException(status_code=400, detail=detail)

    if not response.data:
        raise HTTPException(status_code=500, detail="학생 정보를 저장하지 못했습니다.")

    return {"student": response.data}

@app.post("/api/exchange/students/{serial_number}/charge")
def charge_exchange_student(
    serial_number: str,
    request: Request,
    amount: int | None = Form(default=None),
):
    exchange_admin = get_exchange_admin(request)
    serial_number = serial_number.strip()
    if amount is None or amount <= 0:
        raise HTTPException(status_code=400, detail="충전 금액은 1원 이상이어야 합니다.")
    validate_charge_amount(amount)

    try:
        response = get_supabase().rpc(
            "process_student_charge",
            {
                "p_nfc_serial": serial_number,
                "p_amount": amount,
                "p_admin_id": exchange_admin["id"],
            }
        ).execute()
    except Exception as error:
        logger.exception("Student charge RPC failed")
        err_msg = str(error)
        detail = "충전에 실패했습니다."
        if hasattr(error, "message"):
            detail = error.message
        elif "message" in err_msg:
            detail = err_msg
        raise HTTPException(status_code=400, detail=detail)

    if not response.data:
        raise HTTPException(status_code=500, detail="충전 정보를 저장하지 못했습니다.")

    return {"student": response.data}

@app.post("/api/exchange/students/{serial_number}/balance")
def update_exchange_student_balance(
    serial_number: str,
    request: Request,
    balance: int | None = Form(default=None),
):
    exchange_admin = get_exchange_admin(request)
    serial_number = serial_number.strip()
    if not serial_number:
        raise HTTPException(status_code=400, detail="시리얼 번호를 입력해주세요.")
    if balance is None or balance < 0:
        raise HTTPException(status_code=400, detail="잔액은 0원 이상이어야 합니다.")
    validate_balance_value(balance)

    try:
        response = get_supabase().rpc(
            "process_student_balance_adjustment",
            {
                "p_nfc_serial": serial_number,
                "p_new_balance": balance,
                "p_admin_id": exchange_admin["id"],
                "p_max_delta": MAX_CHARGE_AMOUNT,
            }
        ).execute()
    except Exception as error:
        logger.exception("Student balance adjustment RPC failed")
        err_msg = str(error)
        detail = "잔액 수정에 실패했습니다."
        if hasattr(error, "message"):
            detail = error.message
        elif "message" in err_msg:
            detail = err_msg
        raise HTTPException(status_code=400, detail=detail)

    if not response.data:
        raise HTTPException(status_code=500, detail="잔액을 수정하지 못했습니다.")

    return {"student": response.data}


@app.post("/api/exchange/students/{serial_number}/profile")
def update_exchange_student_profile(
    serial_number: str,
    request: Request,
    student_number: str | None = Form(default=None),
    name: str | None = Form(default=None),
):
    get_exchange_admin(request)
    serial_number = serial_number.strip()
    student_number = (student_number or "").strip()
    name = (name or "").strip()
    if not serial_number:
        raise HTTPException(status_code=400, detail="시리얼 번호를 입력해주세요.")
    if not student_number or not name:
        raise HTTPException(status_code=400, detail="학번과 이름은 필수입니다.")

    try:
        student_response = (
            get_supabase()
            .table("students")
            .select("*")
            .eq("nfc_serial", serial_number)
            .limit(1)
            .execute()
        )
    except Exception as error:
        logger.exception("Student lookup before profile update failed")
        raise server_error("학생 정보를 확인하지 못했습니다.") from error

    if not student_response.data:
        raise HTTPException(status_code=404, detail="등록된 학생증이 아닙니다.")

    student = student_response.data[0]
    student_id = student.get("id")
    if not student_id:
        raise HTTPException(status_code=500, detail="학생 ID를 확인하지 못했습니다.")

    try:
        update_response = (
            get_supabase()
            .table("students")
            .update({"student_number": student_number, "name": name})
            .eq("id", student_id)
            .eq("nfc_serial", serial_number)
            .select("*")
            .execute()
        )
    except Exception as error:
        logger.exception("Student profile update failed")
        raise server_error("학생 정보를 수정하지 못했습니다.") from error

    if not update_response.data:
        raise HTTPException(status_code=500, detail="학생 정보가 수정되지 않았습니다.")

    updated_student = {
        column: value
        for column, value in update_response.data[0].items()
        if column != "id"
    }
    return {"student": updated_student}


@app.post("/api/exchange/students/{serial_number}/suspend")
def suspend_exchange_student(serial_number: str, request: Request):
    get_exchange_admin(request)
    serial_number = serial_number.strip()
    if not serial_number:
        raise HTTPException(status_code=400, detail="시리얼 번호를 입력해주세요.")

    try:
        update_response = (
            get_supabase()
            .table("students")
            .update({"status": "SUSPEND"})
            .eq("nfc_serial", serial_number)
            .eq("status", "ACTIVE")
            .select("*")
            .execute()
        )
    except Exception as error:
        logger.exception("Student suspension failed")
        raise server_error("학생증 이용 정지에 실패했습니다.") from error

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
            raise HTTPException(status_code=404, detail="등록된 학생증이 아닙니다.")
        raise HTTPException(status_code=409, detail="이미 정지되었거나 상태가 변경되었습니다.")

    student = {
        column: value
        for column, value in update_response.data[0].items()
        if column != "id"
    }
    return {"student": student}


@app.post("/api/exchange/students/{serial_number}/unsuspend")
def unsuspend_exchange_student(serial_number: str, request: Request):
    get_exchange_admin(request)
    serial_number = serial_number.strip()
    if not serial_number:
        raise HTTPException(status_code=400, detail="시리얼 번호를 입력해주세요.")

    try:
        update_response = (
            get_supabase()
            .table("students")
            .update({"status": "ACTIVE"})
            .eq("nfc_serial", serial_number)
            .eq("status", "SUSPEND")
            .select("*")
            .execute()
        )
    except Exception as error:
        logger.exception("Student unsuspension failed")
        raise server_error("학생증 이용 정지 해제에 실패했습니다.") from error

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
            raise HTTPException(status_code=404, detail="등록된 학생증이 아닙니다.")
        raise HTTPException(status_code=409, detail="정지 상태가 아니거나 상태가 변경되었습니다.")

    student = {
        column: value
        for column, value in update_response.data[0].items()
        if column != "id"
    }
    return {"student": student}
