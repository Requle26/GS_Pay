import logging

from fastapi import APIRouter, Form, HTTPException, Request

from app.auth import get_system_admin
from app.database import get_supabase
from app.security import server_error
from app.services.transaction_service import (
    load_admin_overview,
)


router = APIRouter(
    prefix="/api/admin",
)

logger = logging.getLogger(__name__)


@router.post("/booths")
def create_admin_booth(
    request: Request,
    name: str | None = Form(default=None),
):
    get_system_admin(request)

    name = (name or "").strip()

    if not name:
        raise HTTPException(
            status_code=400,
            detail="부스 이름은 필수입니다.",
        )

    try:
        response = (
            get_supabase()
            .table("booths")
            .insert(
                {
                    "name": name,
                    "status": "ACTIVE",
                }
            )
            .execute()
        )

    except Exception as error:
        logger.exception("Booth create failed")

        raise server_error(
            "부스를 추가하지 못했습니다. "
            "Supabase 권한을 확인해주세요."
        ) from error

    if not response.data:
        raise HTTPException(
            status_code=500,
            detail="부스를 추가하지 못했습니다.",
        )

    return {
        "booth": response.data[0],
    }


@router.post("/booths/{booth_id}")
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
        raise HTTPException(
            status_code=400,
            detail="부스 이름은 필수입니다.",
        )

    if status not in {
        "ACTIVE",
        "INACTIVE",
    }:
        raise HTTPException(
            status_code=400,
            detail="부스 상태가 올바르지 않습니다.",
        )

    try:
        response = (
            get_supabase()
            .table("booths")
            .update(
                {
                    "name": name,
                    "status": status,
                }
            )
            .eq("id", booth_id)
            .select("id, name, status")
            .execute()
        )

    except Exception as error:
        logger.exception("Booth update failed")

        raise server_error(
            "부스를 수정하지 못했습니다. "
            "Supabase 권한을 확인해주세요."
        ) from error

    if not response.data:
        raise HTTPException(
            status_code=404,
            detail="부스를 찾을 수 없습니다.",
        )

    return {
        "booth": response.data[0],
    }


@router.post("/accounts")
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
        raise HTTPException(
            status_code=400,
            detail="이메일, 비밀번호, 이름은 필수입니다.",
        )

    if len(password) < 6:
        raise HTTPException(
            status_code=400,
            detail="비밀번호는 6자 이상이어야 합니다.",
        )

    if role not in {
        "ADMIN",
        "EXCHANGE",
        "BOOTH",
    }:
        raise HTTPException(
            status_code=400,
            detail="역할이 올바르지 않습니다.",
        )

    if role == "BOOTH" and not booth_id:
        raise HTTPException(
            status_code=400,
            detail="부스 계정은 부스 연결이 필요합니다.",
        )

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
            raise HTTPException(
                status_code=404,
                detail="연결할 부스를 찾을 수 없습니다.",
            )

    try:
        auth_response = (
            get_supabase()
            .auth
            .admin
            .create_user(
                {
                    "email": email,
                    "password": password,
                    "email_confirm": True,
                }
            )
        )

        user = auth_response.user

        if user is None:
            raise RuntimeError(
                "Auth user was not created"
            )

        user_id = str(user.id)

    except Exception as error:
        logger.exception(
            "Admin account auth creation failed"
        )

        raise server_error(
            "인증 계정을 만들지 못했습니다. "
            "이메일 중복 여부를 확인해주세요."
        ) from error

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
        logger.exception(
            "Admin account profile insert failed"
        )

        try:
            get_supabase().auth.admin.delete_user(
                user_id
            )
        except Exception:
            logger.exception(
                "Auth user rollback failed"
            )

        raise server_error(
            "관리자 프로필을 저장하지 못했습니다."
        ) from error

    if not insert_response.data:
        try:
            get_supabase().auth.admin.delete_user(
                user_id
            )
        except Exception:
            logger.exception(
                "Auth user rollback failed"
            )

        raise HTTPException(
            status_code=500,
            detail="관리자 프로필을 저장하지 못했습니다.",
        )

    return {
        "admin": insert_response.data[0],
    }


@router.post("/accounts/{admin_id}")
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

    booth_id = (
        booth_id.strip()
        if booth_id is not None
        else ""
    ) or None

    if not username:
        raise HTTPException(
            status_code=400,
            detail="계정 이름은 필수입니다.",
        )

    if role not in {
        "ADMIN",
        "EXCHANGE",
        "BOOTH",
    }:
        raise HTTPException(
            status_code=400,
            detail="역할이 올바르지 않습니다.",
        )

    if status not in {
        "ACTIVE",
        "INACTIVE",
    }:
        raise HTTPException(
            status_code=400,
            detail="계정 상태가 올바르지 않습니다.",
        )

    if role == "BOOTH" and not booth_id:
        raise HTTPException(
            status_code=400,
            detail="부스 계정은 부스 연결이 필요합니다.",
        )

    if role != "BOOTH":
        booth_id = None

    if (
        admin_id == current_admin["id"]
        and status != "ACTIVE"
    ):
        raise HTTPException(
            status_code=400,
            detail="현재 로그인 계정은 비활성화할 수 없습니다.",
        )

    if (
        admin_id == current_admin["id"]
        and role != "ADMIN"
    ):
        raise HTTPException(
            status_code=400,
            detail="현재 로그인 계정의 역할은 변경할 수 없습니다.",
        )

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
            raise HTTPException(
                status_code=404,
                detail="연결할 부스를 찾을 수 없습니다.",
            )

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
            .select(
                "id, username, role, booth_id, status"
            )
            .execute()
        )

    except Exception as error:
        logger.exception(
            "Admin account update failed"
        )

        raise server_error(
            "계정을 수정하지 못했습니다. "
            "Supabase 권한을 확인해주세요."
        ) from error

    if not response.data:
        raise HTTPException(
            status_code=404,
            detail="계정을 찾을 수 없습니다.",
        )

    return {
        "admin": response.data[0],
    }


@router.get("/overview")
def get_admin_overview(request: Request):
    get_system_admin(request)

    try:
        return load_admin_overview()

    except Exception as error:
        logger.exception(
            "Admin overview refresh failed"
        )

        raise server_error(
            "관리 데이터를 불러오지 못했습니다."
        ) from error