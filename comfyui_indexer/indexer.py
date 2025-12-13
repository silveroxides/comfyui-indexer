"""
Database indexer for ComfyUI image metadata.

Provides SQLite-based storage with FTS5 full-text search capabilities.
Supports incremental updates based on file hash change detection.
"""

import hashlib
import json
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Generator, Iterator

from .parser import ExtractedMetadata, MetadataParser


@dataclass
class IndexedImage:
    """Represents an indexed image record."""
    
    id: int
    file_path: str
    file_hash: str
    file_size: int
    created_at: datetime
    modified_at: datetime
    indexed_at: datetime
    width: int | None
    height: int | None
    raw_prompt: dict | None
    raw_workflow: dict | None


@dataclass
class IndexStats:
    """Statistics about the index."""
    
    total_images: int
    total_metadata_entries: int
    unique_models: int
    unique_node_types: int
    database_size_bytes: int
    last_scan_at: datetime | None


class Indexer:
    """
    SQLite-based indexer for ComfyUI image metadata.
    
    Uses FTS5 for efficient full-text search capabilities.
    """
    
    SCHEMA_VERSION = 1
    
    def __init__(self, db_path: str | Path = "comfyui_index.db"):
        """
        Initialize the indexer.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = Path(db_path)
        self.parser = MetadataParser()
        self._init_database()
    
    def _init_database(self) -> None:
        """Initialize the database schema."""
        with self._get_connection() as conn:
            # Create main images table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT UNIQUE NOT NULL,
                    file_hash TEXT NOT NULL,
                    file_size INTEGER,
                    created_at TIMESTAMP,
                    modified_at TIMESTAMP,
                    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    width INTEGER,
                    height INTEGER,
                    raw_prompt TEXT,
                    raw_workflow TEXT
                )
            """)
            
            # Create metadata table for extracted key-value pairs
            conn.execute("""
                CREATE TABLE IF NOT EXISTS metadata (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    image_id INTEGER NOT NULL,
                    category TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT,
                    node_type TEXT,
                    node_id TEXT,
                    FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE
                )
            """)
            
            # Create FTS5 virtual table for full-text search
            # Using detail='none' to reduce index size (no position data needed)
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS metadata_fts USING fts5(
                    key,
                    value,
                    category,
                    node_type,
                    content='metadata',
                    content_rowid='id',
                    tokenize='unicode61',
                    detail='none'
                )
            """)
            
            # Create triggers to keep FTS in sync
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS metadata_ai AFTER INSERT ON metadata BEGIN
                    INSERT INTO metadata_fts(rowid, key, value, category, node_type)
                    VALUES (new.id, new.key, new.value, new.category, new.node_type);
                END
            """)
            
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS metadata_ad AFTER DELETE ON metadata BEGIN
                    INSERT INTO metadata_fts(metadata_fts, rowid, key, value, category, node_type)
                    VALUES ('delete', old.id, old.key, old.value, old.category, old.node_type);
                END
            """)
            
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS metadata_au AFTER UPDATE ON metadata BEGIN
                    INSERT INTO metadata_fts(metadata_fts, rowid, key, value, category, node_type)
                    VALUES ('delete', old.id, old.key, old.value, old.category, old.node_type);
                    INSERT INTO metadata_fts(rowid, key, value, category, node_type)
                    VALUES (new.id, new.key, new.value, new.category, new.node_type);
                END
            """)
            
            # Create indexes for common queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_metadata_image_id 
                ON metadata(image_id)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_metadata_category 
                ON metadata(category)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_images_file_hash 
                ON images(file_hash)
            """)
            
            # Create scan history table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scan_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    directory TEXT NOT NULL,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    files_scanned INTEGER DEFAULT 0,
                    files_indexed INTEGER DEFAULT 0,
                    files_updated INTEGER DEFAULT 0,
                    files_skipped INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'running'
                )
            """)
            
            # Create schema version table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_info (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            
            conn.execute("""
                INSERT OR REPLACE INTO schema_info (key, value)
                VALUES ('version', ?)
            """, (str(self.SCHEMA_VERSION),))
            
            conn.commit()
    
    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a database connection with proper settings."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        try:
            yield conn
        finally:
            conn.close()
    
    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute a hash of the file for change detection."""
        # Use a combination of size and first/last bytes for speed
        stat = file_path.stat()
        hasher = hashlib.md5()
        hasher.update(str(stat.st_size).encode())
        hasher.update(str(stat.st_mtime).encode())
        
        # Read first and last 4KB for content-based hashing
        with open(file_path, 'rb') as f:
            hasher.update(f.read(4096))
            if stat.st_size > 8192:
                f.seek(-4096, 2)
                hasher.update(f.read(4096))
        
        return hasher.hexdigest()
    
    def index_file(self, file_path: str | Path, force: bool = False) -> bool:
        """
        Index a single image file.
        
        Args:
            file_path: Path to the image file
            force: If True, re-index even if file hasn't changed
            
        Returns:
            True if the file was indexed/updated, False if skipped
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            return False
        
        file_hash = self._compute_file_hash(file_path)
        stat = file_path.stat()
        
        with self._get_connection() as conn:
            # Check if file already exists and is unchanged
            existing = conn.execute(
                "SELECT id, file_hash FROM images WHERE file_path = ?",
                (str(file_path),)
            ).fetchone()
            
            if existing and not force:
                if existing['file_hash'] == file_hash:
                    return False  # File unchanged, skip
            
            # Parse the image metadata
            metadata = self.parser.parse_file(file_path)
            
            if existing:
                # Update existing record
                image_id = existing['id']
                conn.execute("""
                    UPDATE images SET
                        file_hash = ?,
                        file_size = ?,
                        modified_at = ?,
                        indexed_at = CURRENT_TIMESTAMP,
                        width = ?,
                        height = ?,
                        raw_prompt = ?,
                        raw_workflow = ?
                    WHERE id = ?
                """, (
                    file_hash,
                    stat.st_size,
                    datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    metadata.width,
                    metadata.height,
                    json.dumps(metadata.prompt) if metadata.prompt else None,
                    json.dumps(metadata.workflow) if metadata.workflow else None,
                    image_id
                ))
                
                # Delete old metadata entries
                conn.execute("DELETE FROM metadata WHERE image_id = ?", (image_id,))
            else:
                # Insert new record
                cursor = conn.execute("""
                    INSERT INTO images (
                        file_path, file_hash, file_size, created_at, modified_at,
                        width, height, raw_prompt, raw_workflow
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(file_path),
                    file_hash,
                    stat.st_size,
                    datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    metadata.width,
                    metadata.height,
                    json.dumps(metadata.prompt) if metadata.prompt else None,
                    json.dumps(metadata.workflow) if metadata.workflow else None
                ))
                image_id = cursor.lastrowid
            
            # Insert metadata entries
            self._insert_metadata(conn, image_id, metadata)
            
            conn.commit()
            return True
    
    def _insert_metadata(
        self, 
        conn: sqlite3.Connection, 
        image_id: int, 
        metadata: ExtractedMetadata
    ) -> None:
        """Insert metadata entries for an image.
        
        Only indexes high-value categories: prompts, models, parameters, node_types.
        Skips 'all_values' to avoid database bloat from widget data.
        """
        entries = []
        seen_values = set()  # Deduplicate entries
        
        # Add prompts (only if text is meaningful - min 10 chars)
        for item in metadata.prompts:
            value = item.get('value', '')
            if len(value) >= 10:
                key = (item['key'], value)
                if key not in seen_values:
                    seen_values.add(key)
                    entries.append((
                        image_id, 'prompt', item['key'], value,
                        item.get('node_type'), item.get('node_id')
                    ))
        
        # Add models (deduplicated by value)
        seen_models = set()
        for item in metadata.models:
            value = item.get('value', '')
            if value and value not in seen_models:
                seen_models.add(value)
                entries.append((
                    image_id, 'model', item['key'], value,
                    item.get('node_type'), item.get('node_id')
                ))
        
        # NOTE: Skipping all_values category - this was the main source of bloat
        # (67% of all metadata rows were widget_* values nobody searches for)
        
        # Add parameters (only meaningful ones)
        for key, value in metadata.parameters.items():
            str_value = str(value)
            if len(str_value) >= 1:  # Keep all parameters, they're already filtered
                entries.append((
                    image_id, 'parameter', key, str_value, None, None
                ))
        
        # Add node types (deduplicated - one entry per unique type)
        seen_nodes = set()
        for node_type in metadata.node_types:
            if node_type and node_type not in seen_nodes:
                seen_nodes.add(node_type)
                entries.append((
                    image_id, 'node_type', 'class_type', node_type, node_type, None
                ))
        
        if entries:
            conn.executemany("""
                INSERT INTO metadata (image_id, category, key, value, node_type, node_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, entries)
    
    def scan_directory(
        self,
        directory: str | Path,
        recursive: bool = True,
        force: bool = False,
        extensions: tuple[str, ...] = ('.png', '.webp'),
        progress_callback: callable = None
    ) -> dict[str, int]:
        """
        Scan a directory and index all image files.
        
        Args:
            directory: Directory path to scan
            recursive: Whether to scan subdirectories
            force: Force re-indexing of all files
            extensions: File extensions to process
            progress_callback: Optional callback(current, total, file_path)
            
        Returns:
            Statistics dict with counts
        """
        directory = Path(directory)
        
        if not directory.exists():
            raise ValueError(f"Directory does not exist: {directory}")
        
        # Collect files
        if recursive:
            files = []
            for ext in extensions:
                files.extend(directory.rglob(f"*{ext}"))
        else:
            files = []
            for ext in extensions:
                files.extend(directory.glob(f"*{ext}"))
        
        files = list(files)
        total = len(files)
        
        stats = {
            'scanned': 0,
            'indexed': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0
        }
        
        # Record scan start
        with self._get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO scan_history (directory, files_scanned)
                VALUES (?, ?)
            """, (str(directory), total))
            scan_id = cursor.lastrowid
            conn.commit()
        
        # Process files
        for i, file_path in enumerate(files):
            stats['scanned'] += 1
            
            try:
                # Check if update or new
                with self._get_connection() as conn:
                    existing = conn.execute(
                        "SELECT id FROM images WHERE file_path = ?",
                        (str(file_path),)
                    ).fetchone()
                
                indexed = self.index_file(file_path, force=force)
                
                if indexed:
                    if existing:
                        stats['updated'] += 1
                    else:
                        stats['indexed'] += 1
                else:
                    stats['skipped'] += 1
                    
            except Exception as e:
                stats['errors'] += 1
            
            if progress_callback:
                progress_callback(i + 1, total, str(file_path))
        
        # Record scan completion
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE scan_history SET
                    completed_at = CURRENT_TIMESTAMP,
                    files_indexed = ?,
                    files_updated = ?,
                    files_skipped = ?,
                    status = 'completed'
                WHERE id = ?
            """, (stats['indexed'], stats['updated'], stats['skipped'], scan_id))
            conn.commit()
        
        return stats
    
    def get_image(self, image_id: int) -> IndexedImage | None:
        """Get an image by ID."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM images WHERE id = ?", (image_id,)
            ).fetchone()
            
            if not row:
                return None
            
            return IndexedImage(
                id=row['id'],
                file_path=row['file_path'],
                file_hash=row['file_hash'],
                file_size=row['file_size'],
                created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
                modified_at=datetime.fromisoformat(row['modified_at']) if row['modified_at'] else None,
                indexed_at=datetime.fromisoformat(row['indexed_at']) if row['indexed_at'] else None,
                width=row['width'],
                height=row['height'],
                raw_prompt=json.loads(row['raw_prompt']) if row['raw_prompt'] else None,
                raw_workflow=json.loads(row['raw_workflow']) if row['raw_workflow'] else None
            )
    
    def get_image_by_path(self, file_path: str | Path) -> IndexedImage | None:
        """Get an image by file path."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT id FROM images WHERE file_path = ?", (str(file_path),)
            ).fetchone()
            
            if not row:
                return None
            
            return self.get_image(row['id'])
    
    def get_image_metadata(self, image_id: int) -> list[dict[str, Any]]:
        """Get all metadata entries for an image."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT category, key, value, node_type, node_id
                FROM metadata
                WHERE image_id = ?
                ORDER BY category, key
            """, (image_id,)).fetchall()
            
            return [dict(row) for row in rows]
    
    def get_stats(self) -> IndexStats:
        """Get index statistics."""
        with self._get_connection() as conn:
            total_images = conn.execute(
                "SELECT COUNT(*) FROM images"
            ).fetchone()[0]
            
            total_metadata = conn.execute(
                "SELECT COUNT(*) FROM metadata"
            ).fetchone()[0]
            
            unique_models = conn.execute(
                "SELECT COUNT(DISTINCT value) FROM metadata WHERE category = 'model'"
            ).fetchone()[0]
            
            unique_nodes = conn.execute(
                "SELECT COUNT(DISTINCT value) FROM metadata WHERE category = 'node_type'"
            ).fetchone()[0]
            
            last_scan = conn.execute("""
                SELECT completed_at FROM scan_history 
                WHERE status = 'completed' 
                ORDER BY completed_at DESC LIMIT 1
            """).fetchone()
            
            db_size = self.db_path.stat().st_size if self.db_path.exists() else 0
            
            return IndexStats(
                total_images=total_images,
                total_metadata_entries=total_metadata,
                unique_models=unique_models,
                unique_node_types=unique_nodes,
                database_size_bytes=db_size,
                last_scan_at=datetime.fromisoformat(last_scan[0]) if last_scan and last_scan[0] else None
            )
    
    def remove_missing_files(self) -> int:
        """Remove entries for files that no longer exist."""
        removed = 0
        
        with self._get_connection() as conn:
            rows = conn.execute("SELECT id, file_path FROM images").fetchall()
            
            for row in rows:
                if not Path(row['file_path']).exists():
                    conn.execute("DELETE FROM images WHERE id = ?", (row['id'],))
                    removed += 1
            
            conn.commit()
        
        return removed
    
    def list_images(
        self,
        limit: int = 100,
        offset: int = 0,
        order_by: str = 'indexed_at',
        descending: bool = True
    ) -> list[IndexedImage]:
        """List indexed images with pagination."""
        
        valid_columns = {'id', 'file_path', 'created_at', 'modified_at', 'indexed_at', 'file_size'}
        if order_by not in valid_columns:
            order_by = 'indexed_at'
        
        direction = 'DESC' if descending else 'ASC'
        
        with self._get_connection() as conn:
            rows = conn.execute(f"""
                SELECT * FROM images
                ORDER BY {order_by} {direction}
                LIMIT ? OFFSET ?
            """, (limit, offset)).fetchall()
            
            return [
                IndexedImage(
                    id=row['id'],
                    file_path=row['file_path'],
                    file_hash=row['file_hash'],
                    file_size=row['file_size'],
                    created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
                    modified_at=datetime.fromisoformat(row['modified_at']) if row['modified_at'] else None,
                    indexed_at=datetime.fromisoformat(row['indexed_at']) if row['indexed_at'] else None,
                    width=row['width'],
                    height=row['height'],
                    raw_prompt=json.loads(row['raw_prompt']) if row['raw_prompt'] else None,
                    raw_workflow=json.loads(row['raw_workflow']) if row['raw_workflow'] else None
                )
                for row in rows
            ]
