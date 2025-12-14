# Indexing Optimization Plan

**Date:** 2025-12-13  
**Status:** Ready for Implementation

## Problem Analysis

The current database is **21.5 GB** for **30,663 images** - averaging **321 metadata rows per image**.

### Database Breakdown

| Category | Count | % | Notes |
|----------|-------|---|-------|
| **value** | 6,614,572 | 67% | **Main bloat source** |
| node_type | 1,983,779 | 20% | Duplicate node types |
| model | 609,887 | 6% | ✅ Keep |
| prompt | 412,865 | 4% | ✅ Keep |
| parameter | 216,159 | 2% | ✅ Keep |

### What's in the `value` Category (The Bloat)

```
widget_0: 1,489,882    <- Random workflow widget values
widget_1: 803,388
widget_2: 418,116
string: 336,561        <- Node connection references  
widget_3: 321,899
regex_pattern: 151,119 <- Noise from regex nodes
preview: 84,173        <- UI state, useless for search
...
```

Most `widget_*` values are numbers, booleans, or short strings that users would never search for.

---

## Solution

### 1. Remove `value` Category from Indexing

The `value` category stores **every string** from the workflow JSON. This is redundant because:
- Prompts are already in `prompt` category
- Models are already in `model` category  
- Parameters are already in `parameter` category

**Action:** In `indexer.py._insert_metadata()`, skip the loop that adds `all_values`.

### 2. Deduplicate Node Types

Currently storing one `node_type` row per node instance. Should store unique node types only.

**Action:** Use `set()` in parser, insert unique types only.

### 3. Use FTS5 `detail='none'`

Reduces FTS index size by ~50% by skipping position data (not needed for boolean/ranking queries).

```sql
CREATE VIRTUAL TABLE metadata_fts USING fts5(
    key, value, category,
    content='metadata', content_rowid='id',
    tokenize='unicode61',
    detail='none'  -- <-- Add this
);
```

### 4. Minimum Value Length Filter

Skip indexing values shorter than 4 characters (catches "true", "1", "0", etc.)

---

## Expected Results

| Metric | Original | After v1 | After v2 (Current) |
|--------|----------|----------|---------------------|
| Categories indexed | 5 | 4 | 3 (prompt, model, parameter) |
| Rows per image | 321 | ~114 | **~37** |
| Database size | 21.5 GB | ~7 GB | **~2-3 GB** |

### What's No Longer Indexed

1. **value** (67% of original) - widget values nobody searches for
2. **node_type** (68% of remaining) - same 741 types repeated per-image

Node types are still stored in `raw_workflow` JSON column if needed.

---

## Migration

Existing databases will need to be rebuilt:
```bash
# Delete old database and re-scan
rm comfyui_index.db
comfy-idx scan "C:\path\to\images" --recursive
```
