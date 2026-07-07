"""
PrintFarm - Central 3D Printer Management Dashboard
Manages 10 printers across 5 Raspberry Pis running PrusaLink
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio

from core.config import settings
from core.database import init_db
from routers import auth, printers, jobs, admin, websocket
from services.queue_processor import QueueProcessor


queue_processor: QueueProcessor = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    global queue_processor
    queue_processor = QueueProcessor()
    asyncio.create_task(queue_processor.run())
    print("✅ PrintFarm started — managing 10 printers across 5 Pis")
    yield
    # Shutdown
    if queue_processor:
        queue_processor.stop()


app = FastAPI(
    title="PrintFarm",
    description="Central dashboard for managing 10 Prusa 3D printers via PrusaLink",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(printers.router, prefix="/api/printers", tags=["printers"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(websocket.router, prefix="/ws", tags=["websocket"])

# Serve frontend
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

templates = Jinja2Templates(directory="frontend/templates")


@app.get("/")
async def root():
    from fastapi.responses import HTMLResponse
    with open("frontend/templates/index.html") as f:
        return HTMLResponse(f.read())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)