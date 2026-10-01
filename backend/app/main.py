from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.config import settings
from backend.app.database import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Safe deterministic database initialization on startup
    init_db()
    yield

app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None,
)

# Configure CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "phase": "phase-1"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=True)
