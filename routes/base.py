from fastapi import FastAPI, APIRouter
import os

base_router = APIRouter(prefix="/api/v1", tags=["apiv1"])


@base_router.get("/")
async def welcome():
    app_name = os.getenv("APP_NAME")
    appv = os.getenv("APP_VERSION")
    return {"appName ": app_name, "appv": appv}
