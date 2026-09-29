from pathlib import Path
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.security import enforce_same_origin
from app.routers import (
    pages,
    auth,
    admin,
    booth,
    exchange,
    card,
)


BASE_DIR = Path(__file__).resolve().parent

_enable_docs = os.getenv("ENABLE_DOCS", "false").lower() in {
    "1",
    "true",
    "yes",
}

app = FastAPI(
    title="GS Pay",
    docs_url="/docs" if _enable_docs else None,
    redoc_url="/redoc" if _enable_docs else None,
    openapi_url="/openapi.json" if _enable_docs else None,
)

app.mount(
    "/static",
    StaticFiles(directory=BASE_DIR / "static"),
    name="static",
)


@app.middleware("http")
async def csrf_origin_middleware(request: Request, call_next):
    try:
        enforce_same_origin(request)
    except HTTPException as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    return await call_next(request)


app.include_router(pages.router)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(booth.router)
app.include_router(exchange.router)
app.include_router(card.router)