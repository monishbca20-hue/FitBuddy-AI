from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import Base, engine
from app.models import User, WorkoutPlan  # noqa: F401 - register ORM models before create_all
from app.routes import router


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


settings = get_settings()
APP_DIR = Path(__file__).resolve().parent
app = FastAPI(
    title=settings.app_name,
    description="Personalized seven-day workout plans with Gemini or local demo mode.",
    version="1.0.0",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
app.include_router(router)

