"""
Pydantic models for API request/response schemas.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# === Request Models ===

class ScanRequest(BaseModel):
    """Request to scan a directory for images."""
    
    directory: str = Field(..., description="Directory path to scan")
    recursive: bool = Field(True, description="Scan subdirectories")
    force: bool = Field(False, description="Force re-index unchanged files")


class SearchRequest(BaseModel):
    """Search request parameters."""
    
    query: str = Field(..., description="Search query string", min_length=1)
    mode: Literal['fts', 'regex', 'fuzzy', 'exact'] = Field(
        'fts', 
        description="Search mode"
    )
    field: str | None = Field(None, description="Specific field to search")
    category: str | None = Field(
        None, 
        description="Category filter (prompt, model, value, etc.)"
    )
    limit: int = Field(50, ge=1, le=500, description="Maximum results")
    offset: int = Field(0, ge=0, description="Pagination offset")
    threshold: float = Field(
        60.0, 
        ge=0, 
        le=100, 
        description="Fuzzy match threshold (0-100)"
    )


# === Response Models ===

class MetadataEntry(BaseModel):
    """A single metadata entry."""
    
    category: str
    key: str
    value: str | None
    node_type: str | None = None
    node_id: str | None = None


class ImageSummary(BaseModel):
    """Summary information about an indexed image."""
    
    id: int
    file_path: str
    file_size: int | None = None
    width: int | None = None
    height: int | None = None
    created_at: datetime | None = None
    indexed_at: datetime | None = None


class ImageDetail(ImageSummary):
    """Detailed information about an image including metadata."""
    
    file_hash: str
    modified_at: datetime | None = None
    raw_prompt: dict[str, Any] | None = None
    raw_workflow: dict[str, Any] | None = None
    metadata: list[MetadataEntry] = []


class SearchMatch(BaseModel):
    """A match within search results."""
    
    category: str
    key: str
    value: str | None
    node_type: str | None = None
    score: float | None = None


class SearchResultItem(BaseModel):
    """A single search result."""
    
    image_id: int
    file_path: str
    score: float
    matches: list[SearchMatch]
    width: int | None = None
    height: int | None = None
    created_at: datetime | None = None


class SearchResponse(BaseModel):
    """Search response with results and metadata."""
    
    query: str
    mode: str
    total_results: int
    results: list[SearchResultItem]
    search_time_ms: float


class ScanStats(BaseModel):
    """Statistics from a directory scan."""
    
    scanned: int
    indexed: int
    updated: int
    skipped: int
    errors: int


class ScanResponse(BaseModel):
    """Response from a scan operation."""
    
    status: str
    directory: str
    stats: ScanStats


class IndexStats(BaseModel):
    """Database index statistics."""
    
    total_images: int
    total_metadata_entries: int
    unique_models: int
    unique_node_types: int
    database_size_bytes: int
    database_size_human: str
    last_scan_at: datetime | None = None


class UniqueValue(BaseModel):
    """A unique value with count."""
    
    value: str | None
    count: int


class PaginatedImages(BaseModel):
    """Paginated list of images."""
    
    total: int
    limit: int
    offset: int
    images: list[ImageSummary]


class ErrorResponse(BaseModel):
    """Error response."""
    
    error: str
    detail: str | None = None


def format_bytes(size: int) -> str:
    """Format bytes to human-readable string."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"
