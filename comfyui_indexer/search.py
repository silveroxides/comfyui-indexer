"""
Search engine for ComfyUI indexed metadata.

Provides both regex and fuzzy search capabilities across the metadata index.
"""

import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from rapidfuzz import fuzz, process


@dataclass
class SearchResult:
    """A single search result."""
    
    image_id: int
    file_path: str
    score: float  # Relevance score (0-100)
    matches: list[dict[str, Any]]  # Matched metadata entries
    width: int | None = None
    height: int | None = None
    created_at: datetime | None = None


@dataclass
class SearchResponse:
    """Response containing search results and metadata."""
    
    query: str
    mode: str
    total_results: int
    results: list[SearchResult]
    search_time_ms: float


class SearchEngine:
    """
    Search engine supporting multiple search modes.
    
    Modes:
    - 'fts': Full-text search using SQLite FTS5
    - 'regex': Regular expression search
    - 'fuzzy': Fuzzy string matching using rapidfuzz
    - 'exact': Exact match search
    """
    
    def __init__(self, db_path: str | Path):
        """
        Initialize the search engine.
        
        Args:
            db_path: Path to the SQLite database
        """
        self.db_path = Path(db_path)
        
        # Register custom regex function
        self._setup_regex_function()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection with custom functions."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        
        # Register REGEXP function
        def regexp(pattern, value):
            if value is None:
                return False
            try:
                return bool(re.search(pattern, str(value), re.IGNORECASE))
            except re.error:
                return False
        
        conn.create_function("REGEXP", 2, regexp)
        
        return conn
    
    def _setup_regex_function(self) -> None:
        """Ensure regex function is available."""
        pass  # Done in _get_connection
    
    def search(
        self,
        query: str,
        mode: Literal['fts', 'regex', 'fuzzy', 'exact'] = 'fts',
        field: str | None = None,
        category: str | None = None,
        limit: int = 100,
        offset: int = 0,
        threshold: float = 60.0,  # For fuzzy search (0-100)
    ) -> SearchResponse:
        """
        Search the index with the specified mode.
        
        Args:
            query: Search query string
            mode: Search mode ('fts', 'regex', 'fuzzy', 'exact')
            field: Optional field/key to search in
            category: Optional category filter ('prompt', 'model', 'value', etc.)
            limit: Maximum results to return
            offset: Offset for pagination
            threshold: Minimum score for fuzzy matches (0-100)
            
        Returns:
            SearchResponse with results
        """
        import time
        start = time.perf_counter()
        
        if mode == 'fts':
            results = self._search_fts(query, field, category, limit, offset)
        elif mode == 'regex':
            results = self._search_regex(query, field, category, limit, offset)
        elif mode == 'fuzzy':
            results = self._search_fuzzy(query, field, category, limit, offset, threshold)
        elif mode == 'exact':
            results = self._search_exact(query, field, category, limit, offset)
        else:
            raise ValueError(f"Unknown search mode: {mode}")
        
        elapsed = (time.perf_counter() - start) * 1000
        
        return SearchResponse(
            query=query,
            mode=mode,
            total_results=len(results),
            results=results,
            search_time_ms=elapsed
        )
    
    def _search_fts(
        self,
        query: str,
        field: str | None,
        category: str | None,
        limit: int,
        offset: int
    ) -> list[SearchResult]:
        """Full-text search using FTS5."""
        conn = self._get_connection()
        
        try:
            # Build FTS query
            fts_query = self._build_fts_query(query)
            
            # Build SQL
            sql = """
                SELECT 
                    m.image_id,
                    i.file_path,
                    i.width,
                    i.height,
                    i.created_at,
                    m.id as meta_id,
                    m.category,
                    m.key,
                    m.value,
                    m.node_type,
                    bm25(metadata_fts) as rank
                FROM metadata_fts
                JOIN metadata m ON metadata_fts.rowid = m.id
                JOIN images i ON m.image_id = i.id
                WHERE metadata_fts MATCH ?
            """
            params = [fts_query]
            
            if field:
                sql += " AND m.key = ?"
                params.append(field)
            
            if category:
                sql += " AND m.category = ?"
                params.append(category)
            
            sql += " ORDER BY rank LIMIT ? OFFSET ?"
            params.extend([limit * 10, offset])  # Get more to group
            
            rows = conn.execute(sql, params).fetchall()
            
            return self._group_results(rows, limit)
            
        finally:
            conn.close()
    
    def _build_fts_query(self, query: str) -> str:
        """Build an FTS5 match query from user input."""
        # Escape special FTS characters
        special = ['"', "'", '(', ')', '*', '-', '+', ':', '^']
        escaped = query
        for char in special:
            escaped = escaped.replace(char, f' ')
        
        # Split into terms and wrap in quotes for phrase matching
        terms = escaped.split()
        if len(terms) == 1:
            # Single term: prefix match
            return f'"{terms[0]}"*'
        else:
            # Multiple terms: match all
            return ' '.join(f'"{t}"*' for t in terms if t)
    
    def _search_regex(
        self,
        pattern: str,
        field: str | None,
        category: str | None,
        limit: int,
        offset: int
    ) -> list[SearchResult]:
        """Regular expression search."""
        conn = self._get_connection()
        
        try:
            # Parse field:pattern syntax
            if ':' in pattern and not field:
                parts = pattern.split(':', 1)
                if len(parts) == 2:
                    field = parts[0]
                    pattern = parts[1]
            
            sql = """
                SELECT 
                    m.image_id,
                    i.file_path,
                    i.width,
                    i.height,
                    i.created_at,
                    m.id as meta_id,
                    m.category,
                    m.key,
                    m.value,
                    m.node_type
                FROM metadata m
                JOIN images i ON m.image_id = i.id
                WHERE m.value REGEXP ?
            """
            params = [pattern]
            
            if field:
                sql += " AND m.key REGEXP ?"
                params.append(field)
            
            if category:
                sql += " AND m.category = ?"
                params.append(category)
            
            sql += " LIMIT ? OFFSET ?"
            params.extend([limit * 10, offset])
            
            rows = conn.execute(sql, params).fetchall()
            
            # Score based on match quality
            results = []
            for row in rows:
                match = re.search(pattern, row['value'] or '', re.IGNORECASE)
                score = 100.0 if match else 0.0
                results.append((row, score))
            
            return self._group_results_with_scores(results, limit)
            
        finally:
            conn.close()
    
    def _search_fuzzy(
        self,
        query: str,
        field: str | None,
        category: str | None,
        limit: int,
        offset: int,
        threshold: float
    ) -> list[SearchResult]:
        """Fuzzy string matching search."""
        conn = self._get_connection()
        
        try:
            # Get candidate values
            sql = """
                SELECT 
                    m.image_id,
                    i.file_path,
                    i.width,
                    i.height,
                    i.created_at,
                    m.id as meta_id,
                    m.category,
                    m.key,
                    m.value,
                    m.node_type
                FROM metadata m
                JOIN images i ON m.image_id = i.id
                WHERE m.value IS NOT NULL AND m.value != ''
            """
            params = []
            
            if field:
                sql += " AND m.key = ?"
                params.append(field)
            
            if category:
                sql += " AND m.category = ?"
                params.append(category)
            
            rows = conn.execute(sql, params).fetchall()
            
            # Score each row with fuzzy matching
            scored = []
            for row in rows:
                value = row['value'] or ''
                
                # Use partial ratio for substring matches
                score = fuzz.partial_ratio(query.lower(), value.lower())
                
                if score >= threshold:
                    scored.append((row, score))
            
            # Sort by score
            scored.sort(key=lambda x: x[1], reverse=True)
            
            return self._group_results_with_scores(scored[:limit * 10], limit)
            
        finally:
            conn.close()
    
    def _search_exact(
        self,
        query: str,
        field: str | None,
        category: str | None,
        limit: int,
        offset: int
    ) -> list[SearchResult]:
        """Exact match search."""
        conn = self._get_connection()
        
        try:
            sql = """
                SELECT 
                    m.image_id,
                    i.file_path,
                    i.width,
                    i.height,
                    i.created_at,
                    m.id as meta_id,
                    m.category,
                    m.key,
                    m.value,
                    m.node_type
                FROM metadata m
                JOIN images i ON m.image_id = i.id
                WHERE m.value = ?
            """
            params = [query]
            
            if field:
                sql += " AND m.key = ?"
                params.append(field)
            
            if category:
                sql += " AND m.category = ?"
                params.append(category)
            
            sql += " LIMIT ? OFFSET ?"
            params.extend([limit * 10, offset])
            
            rows = conn.execute(sql, params).fetchall()
            
            return self._group_results(rows, limit, default_score=100.0)
            
        finally:
            conn.close()
    
    def _group_results(
        self,
        rows: list,
        limit: int,
        default_score: float = 80.0
    ) -> list[SearchResult]:
        """Group metadata rows by image."""
        images: dict[int, SearchResult] = {}
        
        for row in rows:
            image_id = row['image_id']
            
            if image_id not in images:
                images[image_id] = SearchResult(
                    image_id=image_id,
                    file_path=row['file_path'],
                    score=default_score,
                    matches=[],
                    width=row['width'],
                    height=row['height'],
                    created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None
                )
            
            images[image_id].matches.append({
                'category': row['category'],
                'key': row['key'],
                'value': row['value'],
                'node_type': row['node_type']
            })
        
        results = list(images.values())[:limit]
        return results
    
    def _group_results_with_scores(
        self,
        scored_rows: list[tuple],
        limit: int
    ) -> list[SearchResult]:
        """Group scored metadata rows by image."""
        images: dict[int, SearchResult] = {}
        
        for row, score in scored_rows:
            image_id = row['image_id']
            
            if image_id not in images:
                images[image_id] = SearchResult(
                    image_id=image_id,
                    file_path=row['file_path'],
                    score=score,
                    matches=[],
                    width=row['width'],
                    height=row['height'],
                    created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None
                )
            else:
                # Keep highest score for image
                images[image_id].score = max(images[image_id].score, score)
            
            images[image_id].matches.append({
                'category': row['category'],
                'key': row['key'],
                'value': row['value'],
                'node_type': row['node_type'],
                'score': score
            })
        
        # Sort by score
        results = sorted(images.values(), key=lambda x: x.score, reverse=True)
        return results[:limit]
    
    def search_models(
        self,
        pattern: str = ".*\\.safetensors$",
        limit: int = 100
    ) -> SearchResponse:
        """
        Search for model files (convenience method).
        
        Args:
            pattern: Regex pattern for model names
            limit: Maximum results
            
        Returns:
            SearchResponse with matching images
        """
        return self.search(
            query=pattern,
            mode='regex',
            category='model',
            limit=limit
        )
    
    def search_prompts(
        self,
        query: str,
        fuzzy: bool = True,
        limit: int = 100
    ) -> SearchResponse:
        """
        Search for prompt text (convenience method).
        
        Args:
            query: Text to search for
            fuzzy: Use fuzzy matching
            limit: Maximum results
            
        Returns:
            SearchResponse with matching images
        """
        return self.search(
            query=query,
            mode='fuzzy' if fuzzy else 'fts',
            category='prompt',
            limit=limit
        )
    
    def get_unique_values(
        self,
        category: str,
        key: str | None = None,
        limit: int = 1000
    ) -> list[dict[str, Any]]:
        """
        Get unique values for a category/key combination.
        
        Useful for building filter dropdowns.
        
        Args:
            category: Metadata category
            key: Optional specific key
            limit: Maximum values to return
            
        Returns:
            List of unique values with counts
        """
        conn = self._get_connection()
        
        try:
            sql = """
                SELECT value, COUNT(*) as count
                FROM metadata
                WHERE category = ?
            """
            params = [category]
            
            if key:
                sql += " AND key = ?"
                params.append(key)
            
            sql += """
                GROUP BY value
                ORDER BY count DESC
                LIMIT ?
            """
            params.append(limit)
            
            rows = conn.execute(sql, params).fetchall()
            
            return [{'value': row['value'], 'count': row['count']} for row in rows]
            
        finally:
            conn.close()
    
    def get_all_models(self, limit: int = 500) -> list[dict[str, Any]]:
        """Get all unique model names with usage counts."""
        return self.get_unique_values('model', limit=limit)
    
    def get_all_node_types(self, limit: int = 500) -> list[dict[str, Any]]:
        """Get all unique node types with usage counts."""
        return self.get_unique_values('node_type', limit=limit)
