# Database Analysis Tool - Implementation Plan

**Date:** 2025-12-14  
**Status:** Approved - In Progress

## Overview

A utility for analyzing the ComfyUI Indexer database to identify bloat patterns, frequency distributions, and mark entries for exclusion from future indexing.

### User Decisions
- **Config location:** Project-local (`.comfyui-indexer.json`)
- **Interfaces:** CLI tool + Web UI tab (next to Search Results)
- **Export/Import:** JSON format for sharing exclusion rules

## Use Cases

1. **Analyze key/category frequency** - Find which keys appear most often
2. **Identify bloat patterns** - Spot keys like `widget_*` that add noise
3. **Mark entries as bloat** - Save exclusion rules for future indexing
4. **Export analysis** - Generate reports for human review

---

## Proposed CLI Commands

```bash
# Show database summary
comfy-idx db stats

# Analyze key frequency by category
comfy-idx db analyze --category prompt
comfy-idx db analyze --category model
comfy-idx db analyze --all

# Show top N bloated keys (by count)
comfy-idx db bloat --top 50

# Mark a key pattern as bloat (saved to config)
comfy-idx db exclude --key "widget_*"
comfy-idx db exclude --key "regex_pattern"

# List current exclusion rules
comfy-idx db exclusions

# Remove exclusion rule
comfy-idx db include --key "widget_*"

# Rebuild database using exclusion rules
comfy-idx db rebuild
```

---

## Configuration File

Exclusions stored in `~/.comfyui-indexer/config.json` or project-local `.comfyui-indexer.json`:

```json
{
  "exclude_keys": [
    "widget_*",
    "regex_pattern",
    "preview"
  ],
  "exclude_categories": [],
  "min_value_length": 4,
  "skip_node_types": true
}
```

---

## File Changes

### [NEW] `comfyui_indexer/db_utils.py`

Database analysis utilities:
- `get_key_frequency(category)` - Count occurrences per key
- `get_value_length_distribution()` - Histogram of value lengths
- `get_category_stats()` - Size per category
- `find_bloat_patterns()` - Auto-detect high-frequency low-value keys

### [MODIFY] `comfyui_indexer/cli.py`

Add `db` command group with subcommands:
- `stats` - Summary stats
- `analyze` - Frequency analysis
- `bloat` - Bloat detection
- `exclude` / `include` - Manage exclusions
- `exclusions` - List rules
- `rebuild` - Rebuild with rules applied

### [NEW] `comfyui_indexer/config.py`

Configuration management:
- Load/save config from JSON
- Merge project and user configs
- `get_exclusion_rules()`
- `add_exclusion(key_pattern)`
- `remove_exclusion(key_pattern)`

### [MODIFY] `comfyui_indexer/indexer.py`

- Load exclusion rules on init
- `_should_skip_key(key)` - Check against glob patterns
- Apply rules in `_insert_metadata()`

---

## Sample Output

```
$ comfy-idx db stats

Database Statistics
───────────────────────────────
Total images:        18,843
Total metadata rows: 695,676
Database size:       1.2 GB

By Category:
  prompt:     323,581 (46.5%)
  model:      240,659 (34.6%)
  parameter:  131,436 (18.9%)

$ comfy-idx db bloat --top 10

Top Bloated Keys (by frequency)
───────────────────────────────
1. sampler_name      69,912   (already in 'parameter')
2. scheduler         65,961   (already in 'parameter')
3. filename_prefix   58,157   ⚠️ Noise candidate
4. string_b          57,137   ⚠️ Noise candidate
5. channel           55,346   ⚠️ Noise candidate
...

$ comfy-idx db exclude --key "filename_prefix"
✓ Added 'filename_prefix' to exclusion list

$ comfy-idx db exclusions
Current Exclusions:
  - filename_prefix
  - string_*
```

---

## Implementation Order

1. Create `db_utils.py` with analysis functions
2. Create `config.py` for exclusion rule management
3. Add `db` command group to CLI
4. Modify `indexer.py` to apply exclusion rules
5. Test with current database

---

## Agent Integration

The exclusion config can be read by agents:
```python
from comfyui_indexer.config import get_exclusion_rules
rules = get_exclusion_rules()
# Returns: {'exclude_keys': ['widget_*', ...], ...}
```

This allows agents to respect user-defined bloat patterns without re-analyzing.
