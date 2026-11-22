from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.config import settings
from app.database import Base, engine
from app.api import router

scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    if settings.sync_interval_hours > 0:
        from app.services.collector import sync_all
        scheduler.add_job(sync_all, "interval", hours=settings.sync_interval_hours, id="football_sync", replace_existing=True, max_instances=1)
        scheduler.start()
    yield
    if scheduler.running:
        scheduler.shutdown(wait=False)

app = FastAPI(title=settings.app_name, version="1.1.1", description="Football data ingestion and API for MatchEdge Arena", lifespan=lifespan)
app.include_router(router)
web_dir = Path(__file__).resolve().parent.parent / "web"
app.mount("/static", StaticFiles(directory=web_dir), name="static")

@app.get("/")
def dashboard():
    return FileResponse(web_dir / "index.html")
