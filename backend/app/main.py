import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from .routers import auth, modules, sessions, reports, health


def create_app() -> FastAPI:
    api_app = FastAPI(title="Structured Clinical Interview and Assessment Interview API", version="0.1.0")

    frontend_origin = os.getenv("FRONTEND_ORIGIN", "*")
    api_app.add_middleware(
        CORSMiddleware,
        allow_origins=[frontend_origin] if frontend_origin != "*" else ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )

    api_app.include_router(health.router, prefix="")
    api_app.include_router(auth.router, prefix="/auth", tags=["auth"])
    api_app.include_router(modules.router, prefix="/modules", tags=["modules"])
    api_app.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
    api_app.include_router(reports.router, prefix="/sessions", tags=["reports"])
    # Serve built frontend (Vite) in production if available
    project_root = Path(__file__).resolve().parents[2]
    dist_dir = project_root / "frontend" / "dist"
    index_file = dist_dir / "index.html"

    if dist_dir.exists() and index_file.exists():
        # Serve static assets (e.g., /assets/*)
        assets_dir = dist_dir / "assets"
        if assets_dir.exists():
            api_app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        # Serve index.html at root
        @api_app.get("/", include_in_schema=False)
        def serve_index_root():
            return FileResponse(str(index_file))

        # SPA/static fallback: if a file exists under dist, serve it; otherwise serve index.html
        @api_app.get("/{full_path:path}", include_in_schema=False)
        def serve_index_spa(full_path: str):
            candidate = (dist_dir / full_path.lstrip("/")) if full_path else index_file
            candidate_resolved = candidate.resolve()
            if candidate_resolved.is_file() and str(candidate_resolved).startswith(str(dist_dir.resolve())):
                return FileResponse(str(candidate_resolved))
            return FileResponse(str(index_file))

    return api_app


app = create_app()



