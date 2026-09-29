from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth import (
    ADMIN_COOKIE_NAME,
    get_auth_client,
    get_dashboard_url,
    get_current_admin,
    revoke_access_token,
    use_secure_cookie,
)
from app.database import get_supabase


router = APIRouter()

templates = Jinja2Templates(
    directory="app/templates"
)


@router.post("/login", name="login")
def login(
    request: Request,
    email: str = Form(),
    password: str = Form(),
):
    try:
        auth_response = (
            get_auth_client()
            .auth
            .sign_in_with_password(
                {
                    "email": email,
                    "password": password,
                }
            )
        )

        session = auth_response.session
        user = auth_response.user

        if session is None or user is None:
            raise ValueError(
                "Missing authentication session"
            )

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
            raise PermissionError(
                "Inactive or unregistered administrator"
            )

    except Exception:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "title": "관리자 로그인",
                "error": (
                    "이메일, 비밀번호 또는 "
                    "관리자 권한을 확인해주세요."
                ),
            },
            status_code=401,
        )

    response = RedirectResponse(
        url=get_dashboard_url(
            admin_response.data[0]
        ),
        status_code=303,
    )

    response.set_cookie(
        key=ADMIN_COOKIE_NAME,
        value=session.access_token,
        max_age=60 * 60,
        httponly=True,
        secure=use_secure_cookie(),
        samesite="lax",
    )

    return response


@router.post("/logout", name="logout")
def logout(request: Request):
    access_token = request.cookies.get(
        ADMIN_COOKIE_NAME
    )

    if access_token:
        revoke_access_token(access_token)

    response = RedirectResponse(
        url="/",
        status_code=303,
    )

    response.delete_cookie(
        key=ADMIN_COOKIE_NAME,
        httponly=True,
        secure=use_secure_cookie(),
        samesite="lax",
    )

    return response