"""
FastAPI application for ComfyUI Metadata Indexer.

Provides REST API for searching and browsing indexed images.
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from ..indexer import Indexer
from ..search import SearchEngine
from .routes import images, index, search

# Global instances (initialized on startup)
_indexer: Indexer | None = None
_search_engine: SearchEngine | None = None


def get_app_indexer() -> Indexer:
    """Get the global indexer instance."""
    if _indexer is None:
        raise RuntimeError("Indexer not initialized")
    return _indexer


def get_app_search() -> SearchEngine:
    """Get the global search engine instance."""
    if _search_engine is None:
        raise RuntimeError("Search engine not initialized")
    return _search_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    global _indexer, _search_engine
    
    # Initialize on startup
    db_path = os.environ.get("COMFY_IDX_DB", "comfyui_index.db")
    _indexer = Indexer(db_path)
    _search_engine = SearchEngine(db_path)
    
    print(f"📁 Database: {db_path}")
    stats = _indexer.get_stats()
    print(f"📊 Indexed images: {stats.total_images}")
    
    yield
    
    # Cleanup on shutdown
    _indexer = None
    _search_engine = None


def create_app(
    db_path: str | Path = "comfyui_index.db",
    static_dir: str | Path | None = None,
) -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Args:
        db_path: Path to the SQLite database
        static_dir: Optional directory for static files (WebUI)
        
    Returns:
        Configured FastAPI application
    """
    global _indexer, _search_engine
    
    app = FastAPI(
        title="ComfyUI Metadata Indexer",
        description="Search and browse ComfyUI-generated images by their metadata",
        version="0.1.0",
        lifespan=lifespan,
    )
    
    # CORS middleware for frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure as needed
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include API routers
    app.include_router(search.router, prefix="/api")
    app.include_router(images.router, prefix="/api")
    app.include_router(index.router, prefix="/api")
    
    # Health check endpoint
    @app.get("/api/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy"}
    
    # Auto-detect web directory if not specified
    if static_dir is None:
        # Try to find web directory relative to this file
        package_dir = Path(__file__).parent.parent.parent
        potential_web_dir = package_dir / "web"
        if potential_web_dir.exists():
            static_dir = potential_web_dir
    
    # Serve static files for WebUI if directory exists
    if static_dir:
        static_path = Path(static_dir)
        if static_path.exists():
            app.mount("/", StaticFiles(directory=static_path, html=True), name="static")
    
    return app


# Default app instance for `uvicorn comfyui_indexer.api.main:app`
app = create_app()
