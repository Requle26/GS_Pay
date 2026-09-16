"""Authentication helpers for administrator-only routes."""

import os
from typing import Any

from fastapi import Request
from supabase import create_client

from app.database import get_supabase


ADMIN_COOKIE_NAME = "gs_pay_admin_token"


def get_auth_client():
    """Create a short-lived client for Supabase Auth requests."""
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_PUBLISHABLE_KEY"],
    )


def get_current_admin(request: Request) -> dict[str, Any] | None:
    """Validate the cookie token and return an active admin profile, if any."""
    access_token = request.cookies.get(ADMIN_COOKIE_NAME)
    if not access_token:
        return None

    try:
        user_response = get_auth_client().auth.get_user(access_token)
        user = user_response.user
        if user is None:
            return None

        response = (
            get_supabase()
            .table("admins")
            .select("id, username, role, booth_id")
            .eq("id", str(user.id))
            .eq("status", "ACTIVE")
            .limit(1)
            .execute()
        )
    except Exception:
        return None

    return response.data[0] if response.data else None


def use_secure_cookie() -> bool:
    """Keep cookies HTTPS-only by default; disable only for localhost development."""
    return os.getenv("COOKIE_SECURE", "true").lower() not in {"0", "false", "no"}
