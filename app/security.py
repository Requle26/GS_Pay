from __future__ import annotations

import os
from urllib.parse import urlparse

from fastapi import HTTPException, Request


MAX_CHARGE_AMOUNT = int(
    os.getenv("MAX_CHARGE_AMOUNT", "100000")
)

MAX_BALANCE = int(
    os.getenv("MAX_BALANCE", "500000")
)

MAX_MENU_PRICE = int(
    os.getenv("MAX_MENU_PRICE", "100000")
)


def validate_charge_amount(amount: int) -> None:
    if amount < 0:
        raise HTTPException(
            status_code=400,
            detail="충전 금액은 0원 이상이어야 합니다.",
        )

    if amount > MAX_CHARGE_AMOUNT:
        raise HTTPException(
            status_code=400,
            detail=(
                f"1회 충전 한도는 "
                f"{MAX_CHARGE_AMOUNT:,}원입니다."
            ),
        )


def validate_balance_value(balance: int) -> None:
    if balance < 0:
        raise HTTPException(
            status_code=400,
            detail="잔액은 0원 이상이어야 합니다.",
        )

    if balance > MAX_BALANCE:
        raise HTTPException(
            status_code=400,
            detail=(
                f"잔액 상한은 "
                f"{MAX_BALANCE:,}원입니다."
            ),
        )


def validate_menu_price(price: int) -> None:
    if price <= 0:
        raise HTTPException(
            status_code=400,
            detail="메뉴 가격은 1원 이상이어야 합니다.",
        )

    if price > MAX_MENU_PRICE:
        raise HTTPException(
            status_code=400,
            detail=(
                f"메뉴 가격 상한은 "
                f"{MAX_MENU_PRICE:,}원입니다."
            ),
        )


def allowed_origins() -> set[str]:
    raw = os.getenv(
        "ALLOWED_ORIGINS",
        "",
    ).strip()

    if not raw:
        return set()

    return {
        item.strip().rstrip("/")
        for item in raw.split(",")
        if item.strip()
    }


def _origin_from_url(
    url: str | None,
) -> str | None:

    if not url:
        return None

    parsed = urlparse(url)

    if not parsed.scheme or not parsed.netloc:
        return None

    return f"{parsed.scheme}://{parsed.netloc}"


def enforce_same_origin(request: Request) -> None:
    if request.method not in {
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
    }:
        return

    from app.auth import ADMIN_COOKIE_NAME

    if not request.cookies.get(ADMIN_COOKIE_NAME):
        return

    configured_origins = allowed_origins()

    request_origin = _origin_from_url(
        str(request.base_url)
    )

    if request_origin:
        configured_origins.add(
            request_origin.rstrip("/")
        )

    origin = request.headers.get("origin")

    referer_origin = _origin_from_url(
        request.headers.get("referer")
    )

    candidate = origin or referer_origin

    if candidate is None:
        if request.url.path.startswith("/api/"):
            raise HTTPException(
                status_code=403,
                detail="잘못된 요청 출처입니다.",
            )

        return

    if candidate.rstrip("/") not in {
        item.rstrip("/")
        for item in configured_origins
    }:
        raise HTTPException(
            status_code=403,
            detail="잘못된 요청 출처입니다.",
        )


def server_error(message: str) -> HTTPException:
    return HTTPException(
        status_code=500,
        detail=message,
    )