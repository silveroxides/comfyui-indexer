# Database Framework Research

**Date:** 2025-12-14  
**Purpose:** Evaluate alternatives to SQLite for reducing database bloat and improving search performance

---

## Current State

| Metric | Value |
|--------|-------|
| Images | ~18,800 |
| Metadata rows | ~696K (after optimization) |
| Rows/image | ~37 |
| Database size | ~1.5 GB |

Problem: Even after removing `value` and `node_type` indexing, the database grows significantly due to repetitive metadata entries.

---

## 🔍 FlexSearch (JavaScript)

**Verdict: ⭐ Strong candidate for client-side search**

| Feature | Details |
|---------|---------|
| Speed | Claims 1,000,000x faster than alternatives |
| Memory | Configurable "fast" vs "memory" modes |
| Dependencies | Zero dependencies |
| Platforms | Browser + Node.js |

### Key Features
- **Contextual Search** - Pre-scored in-memory dictionary for relevance
- **Typo tolerance, phonetic matching, partial matching**
- **Web Workers** - Parallel queries for large indexes
- **Supports: SQLite, IndexedDB, Redis, MongoDB backends**

### Use Case for ComfyUI Indexer
Could replace FTS5 for client-side search:
- Ship the index to browser as JSON
- Instant search without server round-trips
- Offload search processing to client

### Limitation
- Index must fit in memory (fine for ~20K images, ~700K metadata rows)

---

## 📊 Alternative Database Engines

### 1. **DuckDB** (Analytical/OLAP)

| Aspect | Rating |
|--------|--------|
| Fit for our use case | ⚠️ Moderate |
| Compression | ✅ Excellent (columnar) |
| Search | ❌ Not designed for FTS |

**Pros:**
- Columnar storage = excellent compression
- 100-1000x faster for aggregations/analytics
- In-process, like SQLite

**Cons:**
- Worse for point queries (single row lookups)
- No built-in FTS like SQLite's FTS5
- Designed for analytics, not OLTP

**Verdict:** Good for analytics dashboard on metadata. Not a direct SQLite replacement for our use case.

---

### 2. **RocksDB** (Key-Value Store)

| Aspect | Rating |
|--------|--------|
| Fit for our use case | ⭐ Good |
| Compression | ✅ Excellent (LZ4, Zstd, Snappy) |
| Search | ❌ Manual implementation needed |

**Pros:**
- Built by Facebook for massive scale
- Configurable compression per "column family"
- 10-50% smaller than SQLite for similar data
- LSM-tree architecture = fast writes

**Cons:**
- Key-value only (no SQL)
- Must implement search layer manually
- Python bindings: `python-rocksdb`

**Verdict:** Best if we're willing to rebuild the storage layer for maximum compression.

---

### 3. **LevelDB** (Key-Value Store)

| Aspect | Rating |
|--------|--------|
| Fit for our use case | ⚠️ Moderate |
| Compression | ✅ Good (Snappy by default) |
| Search | ❌ Manual implementation |

**Pros:**
- Simpler than RocksDB
- Automatic Snappy compression
- Good for sequential reads/writes

**Cons:**
- Single-process only
- Limited maintenance
- Python: `plyvel` library

**Verdict:** Simpler but less powerful than RocksDB. Consider only for smaller scale.

---

### 4. **LMDB** (Memory-Mapped)

| Aspect | Rating |
|--------|--------|
| Fit for our use case | ⚠️ Moderate |
| Compression | ❌ None built-in |
| Search | ❌ Manual implementation |

**Pros:**
- Ultra-fast reads (memory-mapped)
- ACID compliant
- Multi-threaded readers

**Cons:**
- No built-in compression
- Less suitable for large databases

**Verdict:** Not recommended - lacks compression which is our main need.

---

### 5. **Meilisearch** (Full-Text Search Engine)

| Aspect | Rating |
|--------|--------|
| Fit for our use case | ⭐⭐ Excellent |
| Compression | ✅ Good |
| Search | ⭐ Purpose-built |

**Pros:**
- Sub-50ms search responses
- Typo tolerance, synonym support, ranking built-in
- Python SDK available
- Designed for instant search UX
- Easy setup, minimal configuration

**Cons:**
- Separate service (not embedded like SQLite)
- Adds operational complexity
- "Small to medium" scale focus

**Verdict:** Excellent if willing to run a separate search service. Best-in-class for user-facing search.

---

## Recommendations

### Option A: Hybrid Approach (Recommended)

```
SQLite (storage)  →  FlexSearch (client-side search)
     ↓
  Export index JSON on startup
```

- Keep SQLite for metadata storage
- Generate FlexSearch index for browser-side search
- Benefits: No server queries for search, instant results

### Option B: Replace FTS with Meilisearch

```
SQLite (storage)  +  Meilisearch (search)
```

- SQLite stores raw data
- Meilisearch handles all search queries
- Better relevance, typo tolerance, faster

### Option C: Full Rewrite with RocksDB

```
RocksDB (storage)  +  Custom search layer
```

- Maximum compression (~50% smaller)
- Most complex to implement
- Only if storage is critical constraint

---

## Action Items

1. [ ] Prototype FlexSearch integration for client-side search
2. [ ] Benchmark SQLite FTS5 vs FlexSearch on ~20K images
3. [ ] Evaluate Meilisearch as drop-in replacement if client-side approach insufficient
4. [ ] Consider SQLite with Zstd compression pages (requires custom compile)
