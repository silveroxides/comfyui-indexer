"""
Search index API routes for FlexSearch client-side search.

Provides endpoints to export a compact search index for browser-side searching.
"""

import gzip
import hashlib
from datetime import datetime
from io import BytesIO

from fastapi import APIRouter, Response, Depends
from fastapi.responses import StreamingResponse

from ...indexer import Indexer

router = APIRouter(prefix="/search", tags=["search-index"])


def get_indexer() -> Indexer:
    """Dependency to get the indexer instance."""
    from ..main import get_app_indexer
    return get_app_indexer()

# Cache for the generated index
_index_cache: dict = {
    'hash': None,
    'data': None,
    'compressed': None,
    'generated': None
}


def _get_db_hash(indexer: Indexer) -> str:
    """Generate a hash based on image count and last indexed time."""
    stats = indexer.get_stats()
    hash_input = f"{stats.total_images}:{stats.last_scan_at}"
    return hashlib.md5(hash_input.encode()).hexdigest()[:12]


@router.get("/index")
async def get_search_index(
    indexer: Indexer = Depends(get_indexer),
    compressed: bool = True
):
    """
    Export a compact search index for client-side FlexSearch.
    
    The index contains all images with their aggregated metadata,
    optimized for fast client-side full-text search.
    
    Parameters:
        compressed: If True, return gzipped JSON (default)
    
    Returns:
        JSON with: version, generated, total, documents[]
    """
    global _index_cache
    
    current_hash = _get_db_hash(indexer)
    
    # Check if we need to regenerate
    if _index_cache['hash'] != current_hash:
        # Generate new index
        index_data = indexer.export_search_index()
        
        # Compress
        json_bytes = __import__('json').dumps(index_data).encode('utf-8')
        compressed_buffer = BytesIO()
        with gzip.GzipFile(fileobj=compressed_buffer, mode='wb') as gz:
            gz.write(json_bytes)
        compressed_data = compressed_buffer.getvalue()
        
        # Update cache
        _index_cache = {
            'hash': current_hash,
            'data': index_data,
            'compressed': compressed_data,
            'generated': datetime.now().isoformat()
        }
    
    if compressed:
        return Response(
            content=_index_cache['compressed'],
            media_type='application/gzip',
            headers={
                'Content-Encoding': 'gzip',
                'Content-Disposition': 'inline; filename="search-index.json.gz"',
                'X-Index-Hash': current_hash,
                'X-Index-Total': str(_index_cache['data']['total'])
            }
        )
    else:
        return _index_cache['data']


@router.get("/index/metadata")
async def get_search_index_metadata(
    indexer: Indexer = Depends(get_indexer)
):
    """
    Get metadata about the search index without the full data.
    
    Useful for checking if the client's cached index is still valid.
    """
    current_hash = _get_db_hash(indexer)
    stats = indexer.get_stats()
    
    return {
        'hash': current_hash,
        'total_images': stats.total_images,
        'total_metadata': stats.total_metadata_entries,
        'last_scan': str(stats.last_scan_at) if stats.last_scan_at else None,
        'cached': _index_cache['hash'] == current_hash,
        'cache_generated': _index_cache.get('generated')
    }


@router.post("/index/invalidate")
async def invalidate_search_index():
    """
    Invalidate the cached search index.
    
    Call this after a scan to force regeneration on next request.
    """
    global _index_cache
    _index_cache = {
        'hash': None,
        'data': None,
        'compressed': None,
        'generated': None
    }
    return {'status': 'invalidated'}
