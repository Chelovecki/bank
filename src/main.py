from fastapi import APIRouter, FastAPI

from src.api.orders.routers import orders_router
from src.api.payment.routers import payments_router

app = FastAPI()
api_router = APIRouter()
api_router.include_router(orders_router)
api_router.include_router(payments_router)

app.include_router(api_router, prefix="")
