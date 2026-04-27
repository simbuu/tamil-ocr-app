"""
Tamil Handwritten OCR - Flower Transaction Management System (v2)
With analytics, feedback, and admin review.
"""

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

from app.database import init_db
from app.routes import transactions, market_rates, reports, ocr, admin, customers
from app.services.market_rate_service import seed_default_rates


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed_default_rates()
    print("✅ Database initialized")
    print("✅ Market rates seeded")
    yield


app = FastAPI(
    title="Tamil OCR Flower Transaction System",
    description="Digitize handwritten Tamil flower transaction records using EasyOCR",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# API routers
app.include_router(ocr.router, prefix="/api/ocr", tags=["OCR"])
app.include_router(transactions.router, prefix="/api/transactions", tags=["Transactions"])
app.include_router(market_rates.router, prefix="/api/rates", tags=["Market Rates"])
app.include_router(reports.router, prefix="/api/reports", tags=["Reports"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(customers.router, prefix="/api/customers", tags=["Customers"])


# ── Page routes ──────────────────────────────────────────────────────────────

@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/upload")
async def upload_page(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})


@app.get("/transactions")
async def transactions_page(request: Request):
    return templates.TemplateResponse("transactions.html", {"request": request})


@app.get("/rates")
async def rates_page(request: Request):
    return templates.TemplateResponse("rates.html", {"request": request})


@app.get("/reports")
async def reports_page(request: Request):
    return templates.TemplateResponse("reports.html", {"request": request})


@app.get("/admin")
async def admin_page(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})


@app.get("/customers")
async def customers_page(request: Request):
    return templates.TemplateResponse("customers.html", {"request": request})


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
