import logging
import os
from typing import Any

import httpx
from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse
from supabase import create_client

from app.database import get_supabase


ADMIN_COOKIE_NAME = "gs_pay_admin_token"

logger = logging.getLogger(__name__)

ROLE_DASHBOARD_URLS = {
    "ADMIN": "/admin",
    "BOOTH": "/booth",
    "EXCHANGE": "/exchange",
}


def get_auth_client():
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_PUBLISHABLE_KEY"],
    )


def revoke_access_token(access_token: str) -> None:
    url = (
        os.environ["SUPABASE_URL"].rstrip("/")
        + "/auth/v1/logout"
    )

    headers = {
        "Authorization": f"Bearer {access_token}",
        "apikey": os.environ["SUPABASE_PUBLISHABLE_KEY"],
    }

    try:
        with httpx.Client(timeout=5.0) as client:
            client.post(
                url,
                headers=headers,
                params={"scope": "global"},
            )
    except Exception:
        logger.exception(
            "Failed to revoke Supabase session on logout"
        )


def get_current_admin(
    request: Request,
) -> dict[str, Any] | None:

    access_token = request.cookies.get(ADMIN_COOKIE_NAME)

    if not access_token:
        return None

    try:
        user_response = get_auth_client().auth.get_user(
            access_token
        )

        user = user_response.user

        if user is None:
            return None

        response = (
            get_supabase()
            .table("admins")
            .select(
                "id, username, role, booth_id, status"
            )
            .eq("id", str(user.id))
            .eq("status", "ACTIVE")
            .limit(1)
            .execute()
        )

    except Exception:
        return None

    return response.data[0] if response.data else None


def get_dashboard_url(admin: dict) -> str:
    role = str(admin.get("role", "")).upper()

    return ROLE_DASHBOARD_URLS.get(
        role,
        "/login",
    )


def require_role(
    request: Request,
    role: str,
):
    admin = get_current_admin(request)

    if admin is None:
        return None, RedirectResponse(
            url="/login",
            status_code=303,
        )

    if str(admin.get("role", "")).upper() != role:
        return admin, RedirectResponse(
            url=get_dashboard_url(admin),
            status_code=303,
        )

    return admin, None


def get_system_admin(request: Request) -> dict:
    admin = get_current_admin(request)

    if (
        admin is None
        or str(admin.get("role", "")).upper() != "ADMIN"
    ):
        raise HTTPException(
            status_code=403,
            detail="Admin permission required",
        )

    return admin


def get_exchange_admin(request: Request) -> dict:
    admin = get_current_admin(request)

    if (
        admin is None
        or str(admin.get("role", "")).upper() != "EXCHANGE"
    ):
        raise HTTPException(
            status_code=403,
            detail="Exchange permission required",
        )

    return admin


def get_booth_admin(request: Request) -> dict:
    admin = get_current_admin(request)

    if (
        admin is None
        or str(admin.get("role", "")).upper() != "BOOTH"
        or not admin.get("booth_id")
    ):
        raise HTTPException(
            status_code=403,
            detail="Booth permission required",
        )

    return admin


def use_secure_cookie() -> bool:
    return os.getenv(
        "COOKIE_SECURE",
        "true",
    ).lower() not in {
        "0",
        "false",
        "no",
    }