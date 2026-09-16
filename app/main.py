from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


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


@app.get("/api/cards/{serial_number}")
async def get_card_balance(serial_number: str):
    """Return a card balance once the card database is connected."""
    # TODO: serial_number로 학생증/잔액 DB를 조회합니다.
    raise HTTPException(status_code=404, detail="Card information not found")
