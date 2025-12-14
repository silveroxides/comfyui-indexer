# FlexSearch Integration - Implementation Plan

**Date:** 2025-12-14  
**Status:** Draft

## Overview

Integrate FlexSearch for client-side search while keeping SQLite for data storage. This enables instant search without server round-trips.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                     Browser                          │
│  ┌─────────────┐    ┌─────────────────────────────┐ │
│  │ FlexSearch  │◄───│ Search Index (JSON)         │ │
│  │ (in-memory) │    │ Loaded on page load         │ │
│  └─────────────┘    └─────────────────────────────┘ │
│        │                                             │
│        ▼ Instant results                             │
│  ┌─────────────────────────────────────────────────┐ │
│  │              Search UI                           │ │
│  └─────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
        │ 
        │ Gallery/Details still use API
        ▼
┌─────────────────────────────────────────────────────┐
│                    Server                            │
│  ┌─────────────┐    ┌─────────────────────────────┐ │
│  │ SQLite DB   │───►│ /api/search/index (export)  │ │
│  │ (storage)   │    │ Returns compact JSON index  │ │
│  └─────────────┘    └─────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

## Index Format

Compact JSON optimized for FlexSearch:

```json
{
  "version": 1,
  "generated": "2024-12-14T09:00:00Z",
  "total": 18843,
  "documents": [
    {
      "id": 1,
      "path": "C:/images/portrait.png",
      "prompts": "beautiful portrait woman...",
      "models": "sd_xl_base_1.0.safetensors",
      "params": "steps:30 cfg:7.5 sampler:euler"
    }
  ]
}
```

## File Changes

### Backend

#### [NEW] `comfyui_indexer/api/routes/search_index.py`
- `GET /api/search/index` - Export compact search index
- `GET /api/search/index/metadata` - Index stats without full data
- Caching: Generate on first request, invalidate on DB changes

#### [MODIFY] `comfyui_indexer/indexer.py`
- Add `export_search_index()` method
- Concatenate prompts/models per image for compact export

### Frontend

#### [NEW] `web/js/flexsearch.bundle.min.js`
- FlexSearch library (CDN or bundled)

#### [MODIFY] `web/js/app.js`
- Add FlexSearch index initialization
- Replace `api.search()` with local FlexSearch query
- Add index loading progress indicator
- Keep server API for gallery, image details, thumbnails

#### [MODIFY] `web/index.html`
- Add FlexSearch script tag

---

## Implementation Steps

### Phase 1: Backend Index Export
1. [ ] Create `export_search_index()` in indexer.py
2. [ ] Add `/api/search/index` endpoint
3. [ ] Implement caching (regenerate only when DB changes)
4. [ ] Test export with large database

### Phase 2: Frontend Integration
5. [ ] Add FlexSearch library to web/
6. [ ] Create index loader with progress
7. [ ] Initialize FlexSearch Document index
8. [ ] Replace search function with client-side search
9. [ ] Update UI to show "local search" indicator

### Phase 3: Optimization
10. [ ] Compress index with gzip on server
11. [ ] Add incremental index updates (optional)
12. [ ] Store index in IndexedDB for faster reload

---

## FlexSearch Configuration

```javascript
const index = new FlexSearch.Document({
    document: {
        id: "id",
        index: ["prompts", "models", "params"],
        store: ["id", "path"]
    },
    tokenize: "forward",
    resolution: 9,
    cache: true
});
```

---

## Expected Benefits

| Metric | Before (FTS5) | After (FlexSearch) |
|--------|---------------|-------------------|
| Search latency | ~50-200ms | <10ms |
| Server load | Per-query | Index export only |
| Offline capable | No | Yes |
| Typo tolerance | Limited | Built-in |

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Large index size | Compress, lazy load, chunk |
| Memory usage | FlexSearch memory-optimized mode |
| Stale index | Auto-refresh on scan completion |
