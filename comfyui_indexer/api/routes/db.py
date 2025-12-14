"""
Database analysis API routes.

Provides endpoints for analyzing the database and managing exclusion rules.
"""

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...db_utils import DatabaseAnalyzer, format_bytes
from ...config import get_config_manager

router = APIRouter(prefix="/db", tags=["database"])


class CategoryStatsResponse(BaseModel):
    category: str
    count: int
    percentage: float
    unique_keys: int
    unique_values: int


class DatabaseStatsResponse(BaseModel):
    total_images: int
    total_metadata: int
    database_size: str
    rows_per_image: float
    categories: list[CategoryStatsResponse]


class KeyStatsResponse(BaseModel):
    key: str
    count: int
    category: str
    avg_value_length: float
    unique_values: int


class ExclusionRule(BaseModel):
    pattern: str


class ConfigResponse(BaseModel):
    exclude_keys: list[str]
    exclude_categories: list[str]
    min_value_length: int
    skip_node_types: bool
    skip_all_values: bool


class ImportExportData(BaseModel):
    version: str = "1.0"
    description: str = "ComfyUI Indexer exclusion rules"
    exclude_keys: list[str]
    exclude_categories: list[str] = []


def get_db_path() -> str:
    """Get database path from environment."""
    import os
    return os.environ.get("COMFY_IDX_DB", "comfyui_index.db")


@router.get("/stats", response_model=DatabaseStatsResponse)
async def get_stats():
    """Get database statistics."""
    db_path = get_db_path()
    
    if not Path(db_path).exists():
        raise HTTPException(status_code=404, detail="Database not found")
    
    analyzer = DatabaseAnalyzer(db_path)
    stats = analyzer.get_stats()
    
    return DatabaseStatsResponse(
        total_images=stats.total_images,
        total_metadata=stats.total_metadata,
        database_size=format_bytes(stats.database_size_bytes),
        rows_per_image=stats.rows_per_image,
        categories=[
            CategoryStatsResponse(
                category=cat.category,
                count=cat.count,
                percentage=cat.percentage,
                unique_keys=cat.unique_keys,
                unique_values=cat.unique_values
            )
            for cat in stats.categories
        ]
    )


@router.get("/analyze", response_model=list[KeyStatsResponse])
async def analyze_keys(
    category: Optional[str] = None,
    limit: int = 50
):
    """Get key frequency analysis."""
    db_path = get_db_path()
    
    if not Path(db_path).exists():
        raise HTTPException(status_code=404, detail="Database not found")
    
    analyzer = DatabaseAnalyzer(db_path)
    keys = analyzer.get_key_frequency(category=category, limit=limit)
    
    return [
        KeyStatsResponse(
            key=k.key,
            count=k.count,
            category=k.category,
            avg_value_length=k.avg_value_length,
            unique_values=k.unique_values
        )
        for k in keys
    ]


@router.get("/bloat", response_model=list[KeyStatsResponse])
async def find_bloat(threshold: float = 0.5):
    """Find bloat candidates."""
    db_path = get_db_path()
    
    if not Path(db_path).exists():
        raise HTTPException(status_code=404, detail="Database not found")
    
    analyzer = DatabaseAnalyzer(db_path)
    bloat = analyzer.find_bloat_candidates(threshold_ratio=threshold)
    
    return [
        KeyStatsResponse(
            key=k.key,
            count=k.count,
            category=k.category,
            avg_value_length=k.avg_value_length,
            unique_values=k.unique_values
        )
        for k in bloat
    ]


@router.get("/config", response_model=ConfigResponse)
async def get_config():
    """Get current configuration."""
    manager = get_config_manager()
    config = manager.config
    
    return ConfigResponse(
        exclude_keys=config.exclude_keys,
        exclude_categories=config.exclude_categories,
        min_value_length=config.min_value_length,
        skip_node_types=config.skip_node_types,
        skip_all_values=config.skip_all_values
    )


@router.post("/exclude")
async def add_exclusion(rule: ExclusionRule):
    """Add a key pattern to exclusion list."""
    manager = get_config_manager()
    
    if manager.add_exclusion(rule.pattern):
        return {"status": "added", "pattern": rule.pattern}
    return {"status": "exists", "pattern": rule.pattern}


@router.delete("/exclude/{pattern:path}")
async def remove_exclusion(pattern: str):
    """Remove a key pattern from exclusion list."""
    manager = get_config_manager()
    
    if manager.remove_exclusion(pattern):
        return {"status": "removed", "pattern": pattern}
    return {"status": "not_found", "pattern": pattern}


@router.get("/export", response_model=ImportExportData)
async def export_rules():
    """Export exclusion rules."""
    manager = get_config_manager()
    config = manager.config
    
    return ImportExportData(
        exclude_keys=config.exclude_keys,
        exclude_categories=config.exclude_categories
    )


@router.post("/import")
async def import_rules(data: ImportExportData, merge: bool = True):
    """Import exclusion rules."""
    manager = get_config_manager()
    
    added = 0
    
    if merge:
        for key in data.exclude_keys:
            if key not in manager.config.exclude_keys:
                manager.config.exclude_keys.append(key)
                added += 1
        for cat in data.exclude_categories:
            if cat not in manager.config.exclude_categories:
                manager.config.exclude_categories.append(cat)
                added += 1
    else:
        manager.config.exclude_keys = data.exclude_keys
        manager.config.exclude_categories = data.exclude_categories
        added = len(data.exclude_keys) + len(data.exclude_categories)
    
    manager.save()
    
    return {"status": "imported", "rules_added": added}
