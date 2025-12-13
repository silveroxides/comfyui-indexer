"""
Search API routes.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from ..models import (
    SearchMatch,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    UniqueValue,
)
from ...indexer import Indexer
from ...search import SearchEngine

router = APIRouter(prefix="/search", tags=["search"])


def get_indexer() -> Indexer:
    """Dependency to get the indexer instance."""
    from ..main import get_app_indexer
    return get_app_indexer()


def get_search_engine() -> SearchEngine:
    """Dependency to get the search engine instance."""
    from ..main import get_app_search
    return get_app_search()


@router.get("", response_model=SearchResponse)
async def search(
    q: Annotated[str, Query(min_length=1, description="Search query")],
    mode: Annotated[str, Query(description="Search mode: fts, regex, fuzzy, exact")] = "fts",
    field: Annotated[str | None, Query(description="Specific field to search")] = None,
    category: Annotated[str | None, Query(description="Category filter")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    threshold: Annotated[float, Query(ge=0, le=100)] = 60.0,
    search_engine: SearchEngine = Depends(get_search_engine),
) -> SearchResponse:
    """
    Search the metadata index.
    
    **Search Modes:**
    - **fts**: Full-text search using SQLite FTS5 (default)
    - **regex**: Regular expression search
    - **fuzzy**: Fuzzy string matching (Levenshtein distance)
    - **exact**: Exact match search
    
    **Examples:**
    - `?q=portrait&mode=fts` - Full-text search for "portrait"
    - `?q=model_name:.*sdxl.*&mode=regex` - Regex search for SDXL models
    - `?q=beautful landscape&mode=fuzzy` - Fuzzy search (handles typos)
    - `?q=.safetensors&mode=regex&category=model` - Find all safetensor models
    
    **Categories:**
    - `prompt`: Text prompts
    - `model`: Model file references
    - `value`: All string values
    - `parameter`: Generation parameters
    - `node_type`: ComfyUI node types
    """
    result = search_engine.search(
        query=q,
        mode=mode,
        field=field,
        category=category,
        limit=limit,
        offset=offset,
        threshold=threshold
    )
    
    return SearchResponse(
        query=result.query,
        mode=result.mode,
        total_results=result.total_results,
        search_time_ms=result.search_time_ms,
        results=[
            SearchResultItem(
                image_id=r.image_id,
                file_path=r.file_path,
                score=r.score,
                width=r.width,
                height=r.height,
                created_at=r.created_at,
                matches=[
                    SearchMatch(
                        category=m['category'],
                        key=m['key'],
                        value=m['value'],
                        node_type=m.get('node_type'),
                        score=m.get('score')
                    )
                    for m in r.matches
                ]
            )
            for r in result.results
        ]
    )


@router.post("", response_model=SearchResponse)
async def search_post(
    request: SearchRequest,
    search_engine: SearchEngine = Depends(get_search_engine),
) -> SearchResponse:
    """
    Search the metadata index (POST version for complex queries).
    
    Same functionality as GET /search but accepts a JSON body.
    """
    result = search_engine.search(
        query=request.query,
        mode=request.mode,
        field=request.field,
        category=request.category,
        limit=request.limit,
        offset=request.offset,
        threshold=request.threshold
    )
    
    return SearchResponse(
        query=result.query,
        mode=result.mode,
        total_results=result.total_results,
        search_time_ms=result.search_time_ms,
        results=[
            SearchResultItem(
                image_id=r.image_id,
                file_path=r.file_path,
                score=r.score,
                width=r.width,
                height=r.height,
                created_at=r.created_at,
                matches=[
                    SearchMatch(
                        category=m['category'],
                        key=m['key'],
                        value=m['value'],
                        node_type=m.get('node_type'),
                        score=m.get('score')
                    )
                    for m in r.matches
                ]
            )
            for r in result.results
        ]
    )


@router.get("/models", response_model=list[UniqueValue])
async def get_models(
    limit: Annotated[int, Query(ge=1, le=1000)] = 500,
    search_engine: SearchEngine = Depends(get_search_engine),
) -> list[UniqueValue]:
    """
    Get all unique model names with usage counts.
    
    Useful for building filter dropdowns.
    """
    values = search_engine.get_all_models(limit=limit)
    return [UniqueValue(value=v['value'], count=v['count']) for v in values]


@router.get("/node-types", response_model=list[UniqueValue])
async def get_node_types(
    limit: Annotated[int, Query(ge=1, le=1000)] = 500,
    search_engine: SearchEngine = Depends(get_search_engine),
) -> list[UniqueValue]:
    """
    Get all unique ComfyUI node types with usage counts.
    """
    values = search_engine.get_all_node_types(limit=limit)
    return [UniqueValue(value=v['value'], count=v['count']) for v in values]


@router.get("/values/{category}", response_model=list[UniqueValue])
async def get_unique_values(
    category: str,
    key: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 500,
    search_engine: SearchEngine = Depends(get_search_engine),
) -> list[UniqueValue]:
    """
    Get unique values for a specific category.
    
    **Categories:**
    - `prompt`: Text prompts  
    - `model`: Model file references
    - `value`: All string values
    - `parameter`: Generation parameters
    - `node_type`: ComfyUI node types
    """
    values = search_engine.get_unique_values(category=category, key=key, limit=limit)
    return [UniqueValue(value=v['value'], count=v['count']) for v in values]
