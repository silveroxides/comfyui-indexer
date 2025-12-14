"""
Image-related API routes.
"""

import io
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import FileResponse

from ..models import (
    ImageDetail,
    ImageSummary,
    MetadataEntry,
    PaginatedImages,
    format_bytes,
)
from ...indexer import Indexer

router = APIRouter(prefix="/images", tags=["images"])


def get_indexer() -> Indexer:
    """Dependency to get the indexer instance."""
    from ..main import get_app_indexer
    return get_app_indexer()


@router.get("/directories")
async def get_directories(
    indexer: Indexer = Depends(get_indexer),
) -> dict:
    """
    Get list of unique directories containing indexed images.
    
    Returns directories grouped by root path with image counts.
    """
    from contextlib import closing
    import sqlite3
    
    directories = {}
    
    try:
        with closing(sqlite3.connect(indexer.db_path)) as conn:
            # Get all file paths
            rows = conn.execute("SELECT file_path FROM images").fetchall()
            
            for (file_path,) in rows:
                # Extract parent directory
                path = Path(file_path)
                parent = str(path.parent)
                
                if parent in directories:
                    directories[parent] += 1
                else:
                    directories[parent] = 1
        
        # Sort by count descending
        sorted_dirs = sorted(directories.items(), key=lambda x: (-x[1], x[0]))
        
        return {
            "directories": [
                {"path": path, "count": count}
                for path, count in sorted_dirs
            ],
            "total": len(sorted_dirs)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=PaginatedImages)
async def list_images(
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    order_by: str = "indexed_at",
    descending: bool = True,
    directory: str = None,
    indexer: Indexer = Depends(get_indexer),
) -> PaginatedImages:
    """
    List indexed images with pagination.
    
    - **limit**: Maximum number of images to return (1-200)
    - **offset**: Offset for pagination
    - **order_by**: Field to order by (id, file_path, created_at, modified_at, indexed_at, file_size)
    - **descending**: Sort in descending order
    - **directory**: Filter to images in this directory (exact match on parent path)
    """
    images = indexer.list_images(
        limit=limit,
        offset=offset,
        order_by=order_by,
        descending=descending,
        directory=directory
    )
    
    # Get total count (with directory filter if specified)
    if directory:
        from contextlib import closing
        import sqlite3
        with closing(sqlite3.connect(indexer.db_path)) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM images WHERE file_path LIKE ?",
                (directory.replace('\\', '/') + '/%',)
            ).fetchone()[0]
            # Also try backslash version for Windows paths
            count2 = conn.execute(
                "SELECT COUNT(*) FROM images WHERE file_path LIKE ?",
                (directory.replace('/', '\\') + '\\%',)
            ).fetchone()[0]
            total = max(count, count2) if count != count2 else count
    else:
        stats = indexer.get_stats()
        total = stats.total_images
    
    return PaginatedImages(
        total=total,
        limit=limit,
        offset=offset,
        images=[
            ImageSummary(
                id=img.id,
                file_path=img.file_path,
                file_size=img.file_size,
                width=img.width,
                height=img.height,
                created_at=img.created_at,
                indexed_at=img.indexed_at
            )
            for img in images
        ]
    )


@router.get("/{image_id}", response_model=ImageDetail)
async def get_image(
    image_id: int,
    indexer: Indexer = Depends(get_indexer),
) -> ImageDetail:
    """
    Get detailed information about a specific image.
    
    Includes all extracted metadata.
    """
    image = indexer.get_image(image_id)
    
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    metadata = indexer.get_image_metadata(image_id)
    
    return ImageDetail(
        id=image.id,
        file_path=image.file_path,
        file_hash=image.file_hash,
        file_size=image.file_size,
        width=image.width,
        height=image.height,
        created_at=image.created_at,
        modified_at=image.modified_at,
        indexed_at=image.indexed_at,
        raw_prompt=image.raw_prompt,
        raw_workflow=image.raw_workflow,
        metadata=[
            MetadataEntry(
                category=m['category'],
                key=m['key'],
                value=m['value'],
                node_type=m.get('node_type'),
                node_id=m.get('node_id')
            )
            for m in metadata
        ]
    )


@router.get("/{image_id}/file")
async def get_image_file(
    image_id: int,
    indexer: Indexer = Depends(get_indexer),
) -> FileResponse:
    """
    Serve the original image file.
    """
    image = indexer.get_image(image_id)
    
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    file_path = Path(image.file_path)
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Image file not found on disk")
    
    # Determine media type
    suffix = file_path.suffix.lower()
    media_types = {
        '.png': 'image/png',
        '.webp': 'image/webp',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
    }
    media_type = media_types.get(suffix, 'application/octet-stream')
    
    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=file_path.name
    )


@router.get("/{image_id}/thumbnail")
async def get_image_thumbnail(
    image_id: int,
    size: Annotated[int, Query(ge=32, le=512)] = 256,
    indexer: Indexer = Depends(get_indexer),
) -> Response:
    """
    Get a thumbnail of the image.
    
    Thumbnails are generated on-demand and cached in memory.
    
    - **size**: Maximum dimension (width or height) of thumbnail
    """
    image = indexer.get_image(image_id)
    
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    file_path = Path(image.file_path)
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Image file not found on disk")
    
    try:
        from PIL import Image
        
        with Image.open(file_path) as img:
            # Convert to RGB if necessary (for PNG with transparency)
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Create thumbnail
            img.thumbnail((size, size), Image.Resampling.LANCZOS)
            
            # Save to bytes
            buffer = io.BytesIO()
            img.save(buffer, format='WEBP', quality=85)
            buffer.seek(0)
            
            return Response(
                content=buffer.getvalue(),
                media_type='image/webp',
                headers={
                    'Cache-Control': 'public, max-age=3600',
                }
            )
            
    except ImportError:
        raise HTTPException(
            status_code=500, 
            detail="PIL not available for thumbnail generation"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate thumbnail: {str(e)}"
        )
