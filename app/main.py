from pathlib import Path

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


@app.get("/", name="home")
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"title": "GS Pay"},
    )


@app.get("/login", name="login_form")
def login_form(request: Request):
    if get_current_admin(request):
        return RedirectResponse(url="/admin", status_code=303)

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
            .select("id")
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

    response = RedirectResponse(url="/admin", status_code=303)
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
    admin = get_current_admin(request)
    if admin is None:
        return RedirectResponse(url="/login", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={"title": "관리자 페이지", "admin": admin},
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
