import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.routers import analyze

app = FastAPI(title="Synthetic Media Fraud Detector — SEBI TechSprint")

# Only needed for local dev, where the Vite dev server (5173/5180) and the API
# (8000) are different origins. In production the built frontend is served
# from this same FastAPI process, so the browser never makes a cross-origin
# request and this middleware is inert there.
_DEV_ORIGINS = os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:5180,http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_DEV_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyze.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "static"
if _FRONTEND_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=_FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def spa(full_path: str):
        candidate = _FRONTEND_DIST / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_FRONTEND_DIST / "index.html")
