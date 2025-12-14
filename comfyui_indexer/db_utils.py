"""
Database analysis utilities for ComfyUI Indexer.

Provides functions to analyze database content, find bloat patterns,
and generate reports.
"""

import sqlite3
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from contextlib import closing


@dataclass
class CategoryStats:
    """Statistics for a metadata category."""
    category: str
    count: int
    percentage: float
    unique_keys: int
    unique_values: int


@dataclass 
class KeyStats:
    """Statistics for a metadata key."""
    key: str
    count: int
    category: str
    avg_value_length: float
    unique_values: int


@dataclass
class DatabaseStats:
    """Overall database statistics."""
    total_images: int
    total_metadata: int
    database_size_bytes: int
    categories: list[CategoryStats]
    rows_per_image: float


class DatabaseAnalyzer:
    """Analyzes ComfyUI Indexer database for optimization opportunities."""
    
    def __init__(self, db_path: str | Path):
        """
        Initialize analyzer.
        
        Args:
            db_path: Path to the SQLite database
        """
        self.db_path = Path(db_path)
    
    def get_stats(self) -> DatabaseStats:
        """Get overall database statistics."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            # Get counts
            total_images = conn.execute("SELECT COUNT(*) FROM images").fetchone()[0]
            total_metadata = conn.execute("SELECT COUNT(*) FROM metadata").fetchone()[0]
            
            # Get database file size
            db_size = self.db_path.stat().st_size if self.db_path.exists() else 0
            
            # Get category breakdown
            categories = []
            rows = conn.execute("""
                SELECT 
                    category,
                    COUNT(*) as cnt,
                    COUNT(DISTINCT key) as unique_keys,
                    COUNT(DISTINCT value) as unique_values
                FROM metadata 
                GROUP BY category 
                ORDER BY cnt DESC
            """).fetchall()
            
            for row in rows:
                categories.append(CategoryStats(
                    category=row[0],
                    count=row[1],
                    percentage=row[1] / total_metadata * 100 if total_metadata > 0 else 0,
                    unique_keys=row[2],
                    unique_values=row[3]
                ))
            
            return DatabaseStats(
                total_images=total_images,
                total_metadata=total_metadata,
                database_size_bytes=db_size,
                categories=categories,
                rows_per_image=total_metadata / total_images if total_images > 0 else 0
            )
    
    def get_key_frequency(
        self, 
        category: Optional[str] = None,
        limit: int = 50
    ) -> list[KeyStats]:
        """
        Get frequency of each key.
        
        Args:
            category: Filter to specific category (None for all)
            limit: Maximum number of results
            
        Returns:
            List of KeyStats sorted by count descending
        """
        with closing(sqlite3.connect(self.db_path)) as conn:
            if category:
                rows = conn.execute("""
                    SELECT 
                        key,
                        COUNT(*) as cnt,
                        category,
                        AVG(LENGTH(value)) as avg_len,
                        COUNT(DISTINCT value) as unique_vals
                    FROM metadata 
                    WHERE category = ?
                    GROUP BY key 
                    ORDER BY cnt DESC
                    LIMIT ?
                """, (category, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT 
                        key,
                        COUNT(*) as cnt,
                        category,
                        AVG(LENGTH(value)) as avg_len,
                        COUNT(DISTINCT value) as unique_vals
                    FROM metadata 
                    GROUP BY key, category
                    ORDER BY cnt DESC
                    LIMIT ?
                """, (limit,)).fetchall()
            
            return [
                KeyStats(
                    key=row[0],
                    count=row[1],
                    category=row[2],
                    avg_value_length=row[3] or 0,
                    unique_values=row[4]
                )
                for row in rows
            ]
    
    def find_bloat_candidates(self, threshold_ratio: float = 0.5) -> list[KeyStats]:
        """
        Find keys that appear in a high percentage of images.
        
        These are likely candidates for bloat - keys that appear in >50% of images
        but have low unique value counts (same value repeated).
        
        Args:
            threshold_ratio: Minimum ratio of images key appears in (0.0-1.0)
            
        Returns:
            List of KeyStats for bloat candidates
        """
        with closing(sqlite3.connect(self.db_path)) as conn:
            total_images = conn.execute("SELECT COUNT(*) FROM images").fetchone()[0]
            threshold = int(total_images * threshold_ratio)
            
            rows = conn.execute("""
                SELECT 
                    key,
                    COUNT(*) as cnt,
                    category,
                    AVG(LENGTH(value)) as avg_len,
                    COUNT(DISTINCT value) as unique_vals
                FROM metadata 
                GROUP BY key, category
                HAVING cnt > ?
                ORDER BY cnt DESC
            """, (threshold,)).fetchall()
            
            # Filter to keys with low unique value ratio (same values repeated)
            bloat = []
            for row in rows:
                key_stats = KeyStats(
                    key=row[0],
                    count=row[1],
                    category=row[2],
                    avg_value_length=row[3] or 0,
                    unique_values=row[4]
                )
                
                # Low unique ratio = same values repeated = bloat candidate
                unique_ratio = key_stats.unique_values / key_stats.count if key_stats.count > 0 else 1
                if unique_ratio < 0.1:  # Less than 10% unique values
                    bloat.append(key_stats)
            
            return bloat
    
    def get_value_samples(
        self, 
        key: str, 
        category: Optional[str] = None,
        limit: int = 10
    ) -> list[str]:
        """
        Get sample values for a specific key.
        
        Args:
            key: The key to get samples for
            category: Optional category filter
            limit: Maximum samples to return
            
        Returns:
            List of sample values
        """
        with closing(sqlite3.connect(self.db_path)) as conn:
            if category:
                rows = conn.execute("""
                    SELECT DISTINCT value 
                    FROM metadata 
                    WHERE key = ? AND category = ?
                    LIMIT ?
                """, (key, category, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT DISTINCT value 
                    FROM metadata 
                    WHERE key = ?
                    LIMIT ?
                """, (key, limit)).fetchall()
            
            return [row[0] for row in rows if row[0]]


def format_bytes(size: int) -> str:
    """Format bytes to human readable string."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"
