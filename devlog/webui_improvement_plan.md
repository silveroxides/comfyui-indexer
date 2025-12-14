# Web UI Improvements Plan

**Date:** 2025-12-13  
**Status:** Ready for Implementation

## Problem Analysis

Current issues:
1. **Auto-loads gallery on page load** (`loadGallery()` at line 683)
2. **No sorting options** - Only sorts by `indexed_at` descending
3. **No directory navigation** - Shows all images as flat list
4. **Performance risk** - With 30K+ images, even paginated loads strain the UI

---

## Proposed Changes

### 1. Lazy Gallery Loading

**Current:** Gallery loads immediately on page load  
**Change:** Show welcome/browse screen first, load gallery only on user action

```js
// Before (app.js line 683)
document.addEventListener('DOMContentLoaded', () => {
    initEventListeners();
    loadGallery();  // <-- Auto-loads
});

// After
document.addEventListener('DOMContentLoaded', () => {
    initEventListeners();
    showBrowsePrompt();  // Show directory selector first
});
```

### 2. Directory Browser

Add a sidebar or dropdown to browse by scanned directories:

**API Change (images.py):**
```python
@router.get("/directories")
def get_directories():
    """Get list of unique root directories from indexed images."""
    # Extract parent directories from file_path
```

**UI Change:**
- Add directory tree/list in sidebar
- Filter gallery by selected directory
- Add API param: `GET /api/images?directory=C:\path\to\folder`

### 3. Sorting Controls

Add dropdown to sort gallery:

| Sort Option | Order By |
|-------------|----------|
| Newest First | `indexed_at DESC` (current) |
| Oldest First | `indexed_at ASC` |
| Date Created | `created_at DESC` |
| Date Modified | `modified_at DESC` |
| File Name | `file_path ASC` |

**HTML Change:**
```html
<div class="gallery-controls">
    <select id="gallery-sort">
        <option value="indexed_at-desc">Newest Indexed</option>
        <option value="created_at-desc">Date Created</option>
        <option value="modified_at-desc">Date Modified</option>
        <option value="file_path-asc">File Name</option>
    </select>
    <select id="gallery-directory">
        <option value="">All Directories</option>
        <!-- Populated dynamically -->
    </select>
</div>
```

### 4. Pagination Improvements

- Show "Page X of Y" indicator
- Add page size selector (25, 50, 100)
- Virtual scrolling for large result sets (optional, advanced)

---

## File Changes

### [MODIFY] [app.js](file:///f:/ImageBrowsingParsing/web/js/app.js)

- Remove `loadGallery()` from `DOMContentLoaded`
- Add `showBrowsePrompt()` function
- Add sorting state and controls
- Add directory filter support
- Update `loadGallery()` to accept sort/filter params

### [MODIFY] [index.html](file:///f:/ImageBrowsingParsing/web/index.html)

- Add gallery controls section (sort dropdown, directory filter)
- Update empty state to show directory browser
- Add welcome/browse prompt for initial load

### [MODIFY] [styles.css](file:///f:/ImageBrowsingParsing/web/css/styles.css)

- Styles for gallery controls
- Styles for directory browser
- Styles for welcome prompt

### [MODIFY] [images.py](file:///f:/ImageBrowsingParsing/comfyui_indexer/api/routes/images.py)

- Add `/api/images/directories` endpoint
- Add `directory` filter param to `/api/images`

---

## Implementation Order

1. ~~Add API endpoint for directories~~ ✅
2. ~~Add sorting controls to UI~~ ✅
3. ~~Add directory filter dropdown~~ ✅
4. ~~Change initial load to show prompt instead of gallery~~ ✅
5. Test with real data

---

## Verification

To test the changes:
1. Delete the old database: `del comfyui_index.db`
2. Start the server: `comfy-idx serve`
3. Open http://localhost:8000
4. You should see "Browse Your Images" prompt instead of loading gallery
5. Click "Browse All Images" to load the gallery
6. Use dropdown to sort by date, filename, etc.
7. Use directory dropdown to filter by folder
