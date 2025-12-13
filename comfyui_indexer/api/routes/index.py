"""
Index management API routes.
"""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from ..models import (
    IndexStats,
    ScanRequest,
    ScanResponse,
    ScanStats,
    format_bytes,
)
from ...indexer import Indexer

router = APIRouter(prefix="/index", tags=["index"])

# Track active scans
_active_scans: dict[str, dict] = {}


def get_indexer() -> Indexer:
    """Dependency to get the indexer instance."""
    from ..main import get_app_indexer
    return get_app_indexer()


@router.post("/scan", response_model=ScanResponse)
async def scan_directory(
    request: ScanRequest,
    background_tasks: BackgroundTasks,
    indexer: Indexer = Depends(get_indexer),
) -> ScanResponse:
    """
    Scan a directory and index all image files.
    
    The scan runs synchronously for small directories.
    For larger directories, consider implementing background task support.
    
    - **directory**: Path to scan
    - **recursive**: Scan subdirectories (default: true)
    - **force**: Re-index even unchanged files (default: false)
    """
    from pathlib import Path
    
    directory = Path(request.directory)
    
    if not directory.exists():
        raise HTTPException(status_code=400, detail=f"Directory not found: {request.directory}")
    
    if not directory.is_dir():
        raise HTTPException(status_code=400, detail=f"Not a directory: {request.directory}")
    
    try:
        stats = indexer.scan_directory(
            directory=directory,
            recursive=request.recursive,
            force=request.force
        )
        
        return ScanResponse(
            status="completed",
            directory=str(directory),
            stats=ScanStats(
                scanned=stats['scanned'],
                indexed=stats['indexed'],
                updated=stats['updated'],
                skipped=stats['skipped'],
                errors=stats['errors']
            )
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=IndexStats)
async def get_stats(
    indexer: Indexer = Depends(get_indexer),
) -> IndexStats:
    """
    Get database index statistics.
    """
    stats = indexer.get_stats()
    
    return IndexStats(
        total_images=stats.total_images,
        total_metadata_entries=stats.total_metadata_entries,
        unique_models=stats.unique_models,
        unique_node_types=stats.unique_node_types,
        database_size_bytes=stats.database_size_bytes,
        database_size_human=format_bytes(stats.database_size_bytes),
        last_scan_at=stats.last_scan_at
    )


@router.post("/cleanup")
async def cleanup_missing_files(
    indexer: Indexer = Depends(get_indexer),
) -> dict:
    """
    Remove entries for files that no longer exist on disk.
    
    Returns the number of entries removed.
    """
    removed = indexer.remove_missing_files()
    
    return {
        "status": "completed",
        "removed": removed
    }


@router.post("/optimize")
async def optimize_database(
    indexer: Indexer = Depends(get_indexer),
) -> dict:
    """
    Optimize the database (VACUUM and rebuild FTS index).
    
    This can take a while for large databases.
    """
    from contextlib import closing
    import sqlite3
    
    try:
        with closing(sqlite3.connect(indexer.db_path)) as conn:
            # Rebuild FTS index
            conn.execute("INSERT INTO metadata_fts(metadata_fts) VALUES('rebuild')")
            # Vacuum database
            conn.execute("VACUUM")
            conn.commit()
        
        return {"status": "completed"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
