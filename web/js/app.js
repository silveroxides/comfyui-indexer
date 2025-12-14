/**
 * ComfyUI Metadata Indexer - Main Application
 */

// ========================================
// API Client
// ========================================

const API_BASE = '/api';

const api = {
    async get(endpoint, params = {}) {
        const url = new URL(endpoint, window.location.origin);
        url.pathname = API_BASE + url.pathname;
        Object.entries(params).forEach(([key, value]) => {
            if (value !== null && value !== undefined && value !== '') {
                url.searchParams.set(key, value);
            }
        });

        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`API Error: ${response.status}`);
        }
        return response.json();
    },

    async post(endpoint, data = {}) {
        const response = await fetch(API_BASE + endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (!response.ok) {
            throw new Error(`API Error: ${response.status}`);
        }
        return response.json();
    },

    async delete(endpoint) {
        const response = await fetch(API_BASE + endpoint, {
            method: 'DELETE'
        });
        if (!response.ok) {
            throw new Error(`API Error: ${response.status}`);
        }
        return response.json();
    },

    // Convenience methods
    search(query, options = {}) {
        return this.get('/search', { q: query, ...options });
    },

    getImages(options = {}) {
        return this.get('/images', options);
    },

    getImage(id) {
        return this.get(`/images/${id}`);
    },

    getImageUrl(id) {
        return `${API_BASE}/images/${id}/file`;
    },

    getThumbnailUrl(id, size = 256) {
        return `${API_BASE}/images/${id}/thumbnail?size=${size}`;
    },

    getStats() {
        return this.get('/index/stats');
    },

    scanDirectory(directory, recursive = true, force = false) {
        return this.post('/index/scan', { directory, recursive, force });
    },

    getModels() {
        return this.get('/search/models');
    },

    getNodeTypes() {
        return this.get('/search/node-types');
    }
};

// ========================================
// State Management
// ========================================

const state = {
    currentTab: 'gallery',
    galleryImages: [],
    galleryOffset: 0,
    galleryHasMore: true,
    galleryTotal: 0,
    galleryLoaded: false,  // Track if gallery has been loaded
    sortBy: 'indexed_at',
    sortDesc: true,
    currentDirectory: '',  // Currently selected directory filter
    directories: [],       // List of available directories
    searchResults: [],
    currentImageIndex: -1,
    lightboxImages: [],
    isLoading: false,
    theme: 'dark'          // Current theme: 'dark' or 'light'
};

// ========================================
// DOM Elements
// ========================================

const elements = {
    // Search
    searchInput: document.getElementById('search-input'),
    searchClear: document.getElementById('search-clear'),
    searchMode: document.getElementById('search-mode'),
    searchCategory: document.getElementById('search-category'),
    searchBtn: document.getElementById('search-btn'),

    // Tabs
    tabs: document.querySelectorAll('.tabs__tab'),
    galleryView: document.getElementById('gallery-view'),
    resultsView: document.getElementById('results-view'),
    resultsCount: document.getElementById('results-count'),

    // Gallery
    gallery: document.getElementById('gallery'),
    galleryLoading: document.getElementById('gallery-loading'),
    galleryEmpty: document.getElementById('gallery-empty'),
    galleryWelcome: document.getElementById('gallery-welcome'),
    galleryControls: document.getElementById('gallery-controls'),
    gallerySort: document.getElementById('gallery-sort'),
    galleryDirectory: document.getElementById('gallery-directory'),
    galleryCount: document.getElementById('gallery-count'),
    loadMore: document.getElementById('load-more'),
    loadMoreBtn: document.getElementById('load-more-btn'),
    browseAllBtn: document.getElementById('browse-all-btn'),
    welcomeScanBtn: document.getElementById('welcome-scan-btn'),

    // Results
    searchInfo: document.getElementById('search-info'),
    searchQuery: document.getElementById('search-query'),
    searchTime: document.getElementById('search-time'),
    results: document.getElementById('results'),
    resultsLoading: document.getElementById('results-loading'),
    resultsEmpty: document.getElementById('results-empty'),

    // Lightbox
    lightbox: document.getElementById('lightbox'),
    lightboxImage: document.getElementById('lightbox-image'),
    lightboxTitle: document.getElementById('lightbox-title'),
    lightboxMetadata: document.getElementById('lightbox-metadata'),
    lightboxClose: document.getElementById('lightbox-close'),
    lightboxPrev: document.getElementById('lightbox-prev'),
    lightboxNext: document.getElementById('lightbox-next'),

    // Stats Modal
    statsModal: document.getElementById('stats-modal'),
    statsBtn: document.getElementById('stats-btn'),
    statsClose: document.getElementById('stats-close'),
    statsContent: document.getElementById('stats-content'),

    // Scan Modal
    scanModal: document.getElementById('scan-modal'),
    scanBtn: document.getElementById('scan-btn'),
    scanClose: document.getElementById('scan-close'),
    scanCancel: document.getElementById('scan-cancel'),
    scanStart: document.getElementById('scan-start'),
    scanDirectory: document.getElementById('scan-directory'),
    scanRecursive: document.getElementById('scan-recursive'),
    scanForce: document.getElementById('scan-force'),
    scanProgress: document.getElementById('scan-progress'),
    scanStatus: document.getElementById('scan-status'),
    scanResults: document.getElementById('scan-results'),

    // Empty state buttons
    emptyScanBtn: document.getElementById('empty-scan-btn'),

    // Theme toggle
    themeToggle: document.getElementById('theme-toggle'),

    // Database view
    databaseView: document.getElementById('database-view'),
    dbStats: document.getElementById('db-stats'),
    dbCategoryFilter: document.getElementById('db-category-filter'),
    dbAnalyzeBtn: document.getElementById('db-analyze-btn'),
    dbFindBloatBtn: document.getElementById('db-find-bloat-btn'),
    dbAnalysis: document.getElementById('db-analysis'),
    dbExcludeInput: document.getElementById('db-exclude-input'),
    dbAddExclusionBtn: document.getElementById('db-add-exclusion-btn'),
    dbExclusions: document.getElementById('db-exclusions'),
    dbExportBtn: document.getElementById('db-export-btn'),
    dbImportInput: document.getElementById('db-import-input')
};

// ========================================
// Gallery Functions
// ========================================

async function loadGallery(reset = false) {
    if (state.isLoading) return;

    if (reset) {
        state.galleryImages = [];
        state.galleryOffset = 0;
        state.galleryHasMore = true;
        state.galleryTotal = 0;
        elements.gallery.innerHTML = '';
    }

    if (!state.galleryHasMore) return;

    state.isLoading = true;
    state.galleryLoaded = true;
    elements.galleryLoading.style.display = 'flex';
    elements.galleryEmpty.style.display = 'none';
    elements.galleryWelcome.style.display = 'none';
    elements.loadMore.style.display = 'none';
    elements.galleryControls.style.display = 'flex';

    try {
        const params = {
            limit: 50,
            offset: state.galleryOffset,
            order_by: state.sortBy,
            descending: state.sortDesc
        };

        if (state.currentDirectory) {
            params.directory = state.currentDirectory;
        }

        const data = await api.getImages(params);

        if (data.images.length === 0 && state.galleryImages.length === 0) {
            elements.galleryEmpty.style.display = 'flex';
            elements.galleryControls.style.display = 'none';
        } else {
            state.galleryImages.push(...data.images);
            state.galleryOffset += data.images.length;
            state.galleryTotal = data.total;
            state.galleryHasMore = state.galleryOffset < data.total;

            renderGalleryItems(data.images);
            updateGalleryCount();

            if (state.galleryHasMore) {
                elements.loadMore.style.display = 'flex';
            }
        }
    } catch (error) {
        console.error('Failed to load gallery:', error);
        showError('Failed to load images. Is the server running?');
    } finally {
        state.isLoading = false;
        elements.galleryLoading.style.display = 'none';
    }
}

function renderGalleryItems(images) {
    const fragment = document.createDocumentFragment();

    images.forEach((image, index) => {
        const item = createGalleryItem(image, state.galleryImages.length - images.length + index);
        fragment.appendChild(item);
    });

    elements.gallery.appendChild(fragment);
}

function createGalleryItem(image, index) {
    const item = document.createElement('div');
    item.className = 'gallery-item';
    item.dataset.index = index;
    item.dataset.id = image.id;

    const fileName = image.file_path.split(/[/\\]/).pop();
    const dimensions = image.width && image.height
        ? `${image.width}×${image.height}`
        : '';

    item.innerHTML = `
        <img 
            class="gallery-item__image" 
            src="${api.getThumbnailUrl(image.id, 300)}" 
            alt="${fileName}"
            loading="lazy"
        >
        <div class="gallery-item__overlay">
            <div class="gallery-item__title">${fileName}</div>
            ${dimensions ? `<div class="gallery-item__meta">${dimensions}</div>` : ''}
        </div>
    `;

    item.addEventListener('click', () => {
        state.lightboxImages = state.galleryImages;
        openLightbox(index);
    });

    return item;
}

// ========================================
// Search Functions
// ========================================

async function performSearch() {
    const query = elements.searchInput.value.trim();
    if (!query) return;

    state.isLoading = true;
    switchTab('results');

    elements.resultsLoading.style.display = 'flex';
    elements.resultsEmpty.style.display = 'none';
    elements.searchInfo.style.display = 'none';
    elements.results.innerHTML = '';

    try {
        const data = await api.search(query, {
            mode: elements.searchMode.value,
            category: elements.searchCategory.value || null,
            limit: 100
        });

        state.searchResults = data.results;

        elements.searchQuery.textContent = `"${data.query}" (${data.mode})`;
        elements.searchTime.textContent = `${data.total_results} results in ${data.search_time_ms.toFixed(1)}ms`;
        elements.searchInfo.style.display = 'flex';

        elements.resultsCount.textContent = data.total_results;
        elements.resultsCount.style.display = 'inline-flex';

        if (data.results.length === 0) {
            elements.resultsEmpty.querySelector('h3').textContent = 'No Results Found';
            elements.resultsEmpty.querySelector('p').textContent = 'Try a different search query or mode.';
            elements.resultsEmpty.style.display = 'flex';
        } else {
            renderSearchResults(data.results);
        }
    } catch (error) {
        console.error('Search failed:', error);
        showError('Search failed. Please try again.');
    } finally {
        state.isLoading = false;
        elements.resultsLoading.style.display = 'none';
    }
}

function renderSearchResults(results) {
    const fragment = document.createDocumentFragment();

    results.forEach((result, index) => {
        const card = createResultCard(result, index);
        fragment.appendChild(card);
    });

    elements.results.appendChild(fragment);
}

function createResultCard(result, index) {
    const card = document.createElement('div');
    card.className = 'result-card';
    card.dataset.index = index;
    card.dataset.id = result.image_id;

    const fileName = result.file_path.split(/[/\\]/).pop();

    // Get top 3 matches to display
    const topMatches = result.matches.slice(0, 3);
    const matchesHtml = topMatches.map(m => {
        const value = (m.value || '').substring(0, 50);
        return `<span class="result-card__match"><strong>${m.key}:</strong> ${value}${(m.value || '').length > 50 ? '...' : ''}</span>`;
    }).join('');

    card.innerHTML = `
        <div class="result-card__image">
            <img src="${api.getThumbnailUrl(result.image_id, 400)}" alt="${fileName}" loading="lazy">
        </div>
        <div class="result-card__content">
            <div class="result-card__header">
                <div class="result-card__title">${fileName}</div>
                <div class="result-card__score">${result.score.toFixed(0)}%</div>
            </div>
            <div class="result-card__matches">
                ${matchesHtml}
            </div>
        </div>
    `;

    card.addEventListener('click', () => {
        state.lightboxImages = state.searchResults.map(r => ({
            id: r.image_id,
            file_path: r.file_path,
            width: r.width,
            height: r.height
        }));
        openLightbox(index);
    });

    return card;
}

// ========================================
// Lightbox Functions
// ========================================

async function openLightbox(index) {
    if (index < 0 || index >= state.lightboxImages.length) return;

    state.currentImageIndex = index;
    const image = state.lightboxImages[index];
    const imageId = image.id || image.image_id;

    elements.lightbox.classList.add('lightbox--open');
    document.body.style.overflow = 'hidden';

    // Load image
    elements.lightboxImage.src = api.getImageUrl(imageId);

    const fileName = image.file_path.split(/[/\\]/).pop();
    elements.lightboxTitle.textContent = fileName;

    // Load metadata
    elements.lightboxMetadata.innerHTML = '<div class="loading"><div class="loading__spinner"></div></div>';

    try {
        const data = await api.getImage(imageId);
        renderLightboxMetadata(data);
    } catch (error) {
        console.error('Failed to load image details:', error);
        elements.lightboxMetadata.innerHTML = '<p style="color: var(--color-text-tertiary);">Failed to load metadata.</p>';
    }

    // Update nav button visibility
    elements.lightboxPrev.style.visibility = index > 0 ? 'visible' : 'hidden';
    elements.lightboxNext.style.visibility = index < state.lightboxImages.length - 1 ? 'visible' : 'hidden';
}

function closeLightbox() {
    elements.lightbox.classList.remove('lightbox--open');
    document.body.style.overflow = '';
    state.currentImageIndex = -1;
}

function navigateLightbox(direction) {
    const newIndex = state.currentImageIndex + direction;
    if (newIndex >= 0 && newIndex < state.lightboxImages.length) {
        openLightbox(newIndex);
    }
}

function renderLightboxMetadata(imageData) {
    const sections = {};

    // Group metadata by category
    if (imageData.metadata) {
        imageData.metadata.forEach(m => {
            if (!sections[m.category]) {
                sections[m.category] = [];
            }
            sections[m.category].push(m);
        });
    }

    // Add basic info section
    const basicInfo = [
        { key: 'Dimensions', value: imageData.width && imageData.height ? `${imageData.width}×${imageData.height}` : 'Unknown' },
        { key: 'File Size', value: imageData.file_size ? formatBytes(imageData.file_size) : 'Unknown' },
        { key: 'Created', value: imageData.created_at ? new Date(imageData.created_at).toLocaleString() : 'Unknown' }
    ];

    let html = `
        <div class="meta-section">
            <div class="meta-section__title">Image Info</div>
            ${basicInfo.map(item => `
                <div class="meta-item">
                    <div class="meta-item__key">${item.key}</div>
                    <div class="meta-item__value">${item.value}</div>
                </div>
            `).join('')}
        </div>
    `;

    // Render each category
    const categoryOrder = ['prompt', 'model', 'parameter', 'node_type', 'value'];
    const categoryLabels = {
        prompt: 'Prompts',
        model: 'Models',
        parameter: 'Parameters',
        node_type: 'Node Types',
        value: 'Other Values'
    };

    categoryOrder.forEach(category => {
        if (sections[category] && sections[category].length > 0) {
            const items = sections[category].slice(0, 10); // Limit to 10 items
            html += `
                <div class="meta-section">
                    <div class="meta-section__title">${categoryLabels[category] || category}</div>
                    ${items.map(m => `
                        <div class="meta-item">
                            <div class="meta-item__key">${m.key}</div>
                            <div class="meta-item__value">${m.value || ''}</div>
                        </div>
                    `).join('')}
                    ${sections[category].length > 10 ? `<div class="meta-item__value" style="color: var(--color-text-muted);">... and ${sections[category].length - 10} more</div>` : ''}
                </div>
            `;
        }
    });

    elements.lightboxMetadata.innerHTML = html;
}

// ========================================
// Tab Functions
// ========================================

function switchTab(tabName) {
    state.currentTab = tabName;

    elements.tabs.forEach(tab => {
        tab.classList.toggle('tabs__tab--active', tab.dataset.tab === tabName);
    });

    elements.galleryView.classList.toggle('view--active', tabName === 'gallery');
    elements.resultsView.classList.toggle('view--active', tabName === 'results');
    elements.databaseView?.classList.toggle('view--active', tabName === 'database');

    // Load database data when switching to that tab
    if (tabName === 'database') {
        loadDbStats();
        loadExclusions();
    }
}

// ========================================
// Stats Modal
// ========================================

async function showStats() {
    elements.statsModal.classList.add('modal--open');
    elements.statsContent.innerHTML = '<div class="loading"><div class="loading__spinner"></div></div>';

    try {
        const stats = await api.getStats();

        elements.statsContent.innerHTML = `
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-card__value">${stats.total_images.toLocaleString()}</div>
                    <div class="stat-card__label">Total Images</div>
                </div>
                <div class="stat-card">
                    <div class="stat-card__value">${stats.total_metadata_entries.toLocaleString()}</div>
                    <div class="stat-card__label">Metadata Entries</div>
                </div>
                <div class="stat-card">
                    <div class="stat-card__value">${stats.unique_models}</div>
                    <div class="stat-card__label">Unique Models</div>
                </div>
                <div class="stat-card">
                    <div class="stat-card__value">${stats.unique_node_types}</div>
                    <div class="stat-card__label">Node Types</div>
                </div>
            </div>
            <div style="margin-top: var(--space-4); color: var(--color-text-tertiary); font-size: var(--font-size-sm);">
                <p>Database Size: ${stats.database_size_human}</p>
                ${stats.last_scan_at ? `<p>Last Scan: ${new Date(stats.last_scan_at).toLocaleString()}</p>` : ''}
            </div>
        `;
    } catch (error) {
        console.error('Failed to load stats:', error);
        elements.statsContent.innerHTML = '<p style="color: var(--color-error);">Failed to load statistics.</p>';
    }
}

function closeStats() {
    elements.statsModal.classList.remove('modal--open');
}

// ========================================
// Scan Modal
// ========================================

function showScan() {
    elements.scanModal.classList.add('modal--open');
    elements.scanProgress.style.display = 'none';
    elements.scanResults.style.display = 'none';
    elements.scanStart.disabled = false;
}

function closeScan() {
    elements.scanModal.classList.remove('modal--open');
}

async function startScan() {
    const directory = elements.scanDirectory.value.trim();
    if (!directory) {
        alert('Please enter a directory path.');
        return;
    }

    elements.scanStart.disabled = true;
    elements.scanProgress.style.display = 'flex';
    elements.scanResults.style.display = 'none';
    elements.scanStatus.textContent = 'Scanning...';

    try {
        const result = await api.scanDirectory(
            directory,
            elements.scanRecursive.checked,
            elements.scanForce.checked
        );

        elements.scanProgress.style.display = 'none';
        elements.scanResults.style.display = 'block';
        elements.scanResults.innerHTML = `
            <div style="padding: var(--space-4); background: var(--color-success-bg); border-radius: var(--radius-md); color: var(--color-success);">
                <strong>Scan Complete!</strong>
                <ul style="margin-top: var(--space-2); margin-left: var(--space-4);">
                    <li>Scanned: ${result.stats.scanned}</li>
                    <li>New: ${result.stats.indexed}</li>
                    <li>Updated: ${result.stats.updated}</li>
                    <li>Skipped: ${result.stats.skipped}</li>
                    ${result.stats.errors > 0 ? `<li style="color: var(--color-error);">Errors: ${result.stats.errors}</li>` : ''}
                </ul>
            </div>
        `;

        // Reload gallery
        loadGallery(true);

    } catch (error) {
        console.error('Scan failed:', error);
        elements.scanProgress.style.display = 'none';
        elements.scanResults.style.display = 'block';
        elements.scanResults.innerHTML = `
            <div style="padding: var(--space-4); background: var(--color-error-bg); border-radius: var(--radius-md); color: var(--color-error);">
                <strong>Scan Failed</strong>
                <p style="margin-top: var(--space-2);">${error.message}</p>
            </div>
        `;
    } finally {
        elements.scanStart.disabled = false;
    }
}

// ========================================
// Utility Functions
// ========================================

function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function showError(message) {
    // Simple error display - could be enhanced with toast notifications
    console.error(message);
}

function updateGalleryCount() {
    if (elements.galleryCount) {
        elements.galleryCount.textContent = `${state.galleryImages.length} of ${state.galleryTotal.toLocaleString()}`;
    }
}

async function loadDirectories() {
    try {
        const data = await api.get('/images/directories');
        state.directories = data.directories || [];

        // Update directory dropdown
        if (elements.galleryDirectory) {
            elements.galleryDirectory.innerHTML = '<option value="">All Directories</option>';
            state.directories.forEach(dir => {
                const option = document.createElement('option');
                option.value = dir.path;
                // Show shortened path + count
                const shortPath = dir.path.length > 50 ? '...' + dir.path.slice(-47) : dir.path;
                option.textContent = `${shortPath} (${dir.count})`;
                elements.galleryDirectory.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Failed to load directories:', error);
    }
}

function handleSortChange() {
    const value = elements.gallerySort.value;
    const [field, direction] = value.split('-');
    state.sortBy = field;
    state.sortDesc = direction === 'desc';
    loadGallery(true);
}

function handleDirectoryChange() {
    state.currentDirectory = elements.galleryDirectory.value;
    loadGallery(true);
}

// ========================================
// Database Analysis Functions
// ========================================

async function loadDbStats() {
    try {
        const data = await api.get('/db/stats');

        elements.dbStats.innerHTML = `
            <div class="db-stat-card">
                <div class="db-stat-card__value">${data.total_images.toLocaleString()}</div>
                <div class="db-stat-card__label">Images</div>
            </div>
            <div class="db-stat-card">
                <div class="db-stat-card__value">${data.total_metadata.toLocaleString()}</div>
                <div class="db-stat-card__label">Metadata Rows</div>
            </div>
            <div class="db-stat-card">
                <div class="db-stat-card__value">${data.rows_per_image.toFixed(1)}</div>
                <div class="db-stat-card__label">Rows/Image</div>
            </div>
            <div class="db-stat-card">
                <div class="db-stat-card__value">${data.database_size}</div>
                <div class="db-stat-card__label">DB Size</div>
            </div>
        `;

        if (data.categories.length > 0) {
            const catTable = `
                <table class="db-table db-category-table">
                    <thead>
                        <tr><th>Category</th><th>Count</th><th>%</th><th>Unique Keys</th><th>Unique Values</th></tr>
                    </thead>
                    <tbody>
                        ${data.categories.map(c => `
                            <tr>
                                <td>${c.category}</td>
                                <td class="count">${c.count.toLocaleString()}</td>
                                <td>${c.percentage.toFixed(1)}%</td>
                                <td>${c.unique_keys}</td>
                                <td>${c.unique_values.toLocaleString()}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
            elements.dbStats.innerHTML += catTable;
        }
    } catch (error) {
        elements.dbStats.innerHTML = `<p class="db-hint">Failed to load stats: ${error.message}</p>`;
    }
}

async function analyzeKeys() {
    const category = elements.dbCategoryFilter.value || null;

    try {
        const keys = await api.get(`/db/analyze?limit=50${category ? `&category=${category}` : ''}`);

        if (keys.length === 0) {
            elements.dbAnalysis.innerHTML = '<p class="db-hint">No data found.</p>';
            return;
        }

        elements.dbAnalysis.innerHTML = `
            <table class="db-table">
                <thead>
                    <tr><th>#</th><th>Key</th><th>Category</th><th>Count</th><th>Unique</th><th>Avg Len</th><th>Action</th></tr>
                </thead>
                <tbody>
                    ${keys.map((k, i) => `
                        <tr>
                            <td>${i + 1}</td>
                            <td>${k.key}</td>
                            <td>${k.category}</td>
                            <td class="count">${k.count.toLocaleString()}</td>
                            <td>${k.unique_values}</td>
                            <td>${k.avg_value_length.toFixed(0)}</td>
                            <td><button class="btn-exclude" data-key="${k.key}">Exclude</button></td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;

        // Add click handlers for exclude buttons
        elements.dbAnalysis.querySelectorAll('.btn-exclude').forEach(btn => {
            btn.addEventListener('click', () => addExclusion(btn.dataset.key));
        });
    } catch (error) {
        elements.dbAnalysis.innerHTML = `<p class="db-hint">Error: ${error.message}</p>`;
    }
}

async function findBloat() {
    try {
        const bloat = await api.get('/db/bloat?threshold=0.3');

        if (bloat.length === 0) {
            elements.dbAnalysis.innerHTML = '<p class="db-hint">No obvious bloat patterns found. Great!</p>';
            return;
        }

        elements.dbAnalysis.innerHTML = `
            <p class="db-hint">⚠️ Found ${bloat.length} potential bloat candidates:</p>
            <table class="db-table">
                <thead>
                    <tr><th>Key</th><th>Category</th><th>Count</th><th>Unique</th><th>Action</th></tr>
                </thead>
                <tbody>
                    ${bloat.map(k => `
                        <tr>
                            <td>${k.key}</td>
                            <td>${k.category}</td>
                            <td class="count">${k.count.toLocaleString()}</td>
                            <td>${k.unique_values}</td>
                            <td><button class="btn-exclude" data-key="${k.key}">Exclude</button></td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;

        elements.dbAnalysis.querySelectorAll('.btn-exclude').forEach(btn => {
            btn.addEventListener('click', () => addExclusion(btn.dataset.key));
        });
    } catch (error) {
        elements.dbAnalysis.innerHTML = `<p class="db-hint">Error: ${error.message}</p>`;
    }
}

async function loadExclusions() {
    try {
        const config = await api.get('/db/config');

        if (config.exclude_keys.length === 0) {
            elements.dbExclusions.innerHTML = '<p class="db-hint">No exclusions configured.</p>';
            return;
        }

        elements.dbExclusions.innerHTML = config.exclude_keys.map(key => `
            <span class="db-exclusion-tag">
                ${key}
                <button class="remove" data-key="${key}">&times;</button>
            </span>
        `).join('');

        // Add remove handlers
        elements.dbExclusions.querySelectorAll('.remove').forEach(btn => {
            btn.addEventListener('click', () => removeExclusion(btn.dataset.key));
        });
    } catch (error) {
        elements.dbExclusions.innerHTML = '<p class="db-hint">Failed to load exclusions.</p>';
    }
}

async function addExclusion(pattern) {
    try {
        await api.post('/db/exclude', { pattern });
        loadExclusions();
    } catch (error) {
        console.error('Failed to add exclusion:', error);
    }
}

async function removeExclusion(pattern) {
    try {
        await api.delete(`/db/exclude/${encodeURIComponent(pattern)}`);
        loadExclusions();
    } catch (error) {
        console.error('Failed to remove exclusion:', error);
    }
}

async function exportRules() {
    try {
        const data = await api.get('/db/export');
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'comfyui-indexer-rules.json';
        a.click();
        URL.revokeObjectURL(url);
    } catch (error) {
        console.error('Failed to export rules:', error);
    }
}

async function importRules(file) {
    try {
        const text = await file.text();
        const data = JSON.parse(text);
        await api.post('/db/import?merge=true', data);
        loadExclusions();
    } catch (error) {
        console.error('Failed to import rules:', error);
    }
}

// ========================================
// Event Listeners
// ========================================

function initEventListeners() {
    // Search
    elements.searchBtn.addEventListener('click', performSearch);
    elements.searchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') performSearch();
    });
    elements.searchInput.addEventListener('input', () => {
        elements.searchClear.style.display = elements.searchInput.value ? 'flex' : 'none';
    });
    elements.searchClear.addEventListener('click', () => {
        elements.searchInput.value = '';
        elements.searchClear.style.display = 'none';
        elements.searchInput.focus();
    });

    // Tabs
    elements.tabs.forEach(tab => {
        tab.addEventListener('click', () => switchTab(tab.dataset.tab));
    });

    // Gallery
    elements.loadMoreBtn.addEventListener('click', () => loadGallery());
    elements.emptyScanBtn?.addEventListener('click', showScan);
    elements.browseAllBtn?.addEventListener('click', () => {
        loadDirectories();
        loadGallery(true);
    });
    elements.welcomeScanBtn?.addEventListener('click', showScan);

    // Gallery controls
    if (elements.gallerySort) {
        elements.gallerySort.addEventListener('change', handleSortChange);
    }
    if (elements.galleryDirectory) {
        elements.galleryDirectory.addEventListener('change', handleDirectoryChange);
    }

    // Database view
    elements.dbAnalyzeBtn?.addEventListener('click', analyzeKeys);
    elements.dbFindBloatBtn?.addEventListener('click', findBloat);
    elements.dbAddExclusionBtn?.addEventListener('click', () => {
        const pattern = elements.dbExcludeInput.value.trim();
        if (pattern) {
            addExclusion(pattern);
            elements.dbExcludeInput.value = '';
        }
    });
    elements.dbExcludeInput?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            const pattern = elements.dbExcludeInput.value.trim();
            if (pattern) {
                addExclusion(pattern);
                elements.dbExcludeInput.value = '';
            }
        }
    });
    elements.dbExportBtn?.addEventListener('click', exportRules);
    elements.dbImportInput?.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            importRules(e.target.files[0]);
            e.target.value = ''; // Reset for future imports
        }
    });

    // Lightbox
    elements.lightboxClose.addEventListener('click', closeLightbox);
    elements.lightboxPrev.addEventListener('click', () => navigateLightbox(-1));
    elements.lightboxNext.addEventListener('click', () => navigateLightbox(1));
    elements.lightbox.addEventListener('click', (e) => {
        if (e.target === elements.lightbox) closeLightbox();
    });

    // Stats
    elements.statsBtn.addEventListener('click', showStats);
    elements.statsClose.addEventListener('click', closeStats);
    elements.statsModal.addEventListener('click', (e) => {
        if (e.target === elements.statsModal) closeStats();
    });

    // Scan
    elements.scanBtn.addEventListener('click', showScan);
    elements.scanClose.addEventListener('click', closeScan);
    elements.scanCancel.addEventListener('click', closeScan);
    elements.scanStart.addEventListener('click', startScan);
    elements.scanModal.addEventListener('click', (e) => {
        if (e.target === elements.scanModal) closeScan();
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        if (elements.lightbox.classList.contains('lightbox--open')) {
            if (e.key === 'Escape') closeLightbox();
            if (e.key === 'ArrowLeft') navigateLightbox(-1);
            if (e.key === 'ArrowRight') navigateLightbox(1);
        } else {
            if (e.key === 'Escape') {
                closeStats();
                closeScan();
            }
        }
    });
}

// ========================================
// Theme Toggle
// ========================================

function toggleTheme() {
    state.theme = state.theme === 'dark' ? 'light' : 'dark';
    applyTheme(state.theme);
    localStorage.setItem('comfyui-indexer-theme', state.theme);
}

function applyTheme(theme) {
    state.theme = theme;

    if (theme === 'light') {
        document.body.classList.add('light-mode');
    } else {
        document.body.classList.remove('light-mode');
    }

    // Update toggle button icons
    const darkIcon = document.querySelector('.theme-icon-dark');
    const lightIcon = document.querySelector('.theme-icon-light');

    if (darkIcon && lightIcon) {
        if (theme === 'light') {
            darkIcon.style.display = 'none';
            lightIcon.style.display = 'block';
        } else {
            darkIcon.style.display = 'block';
            lightIcon.style.display = 'none';
        }
    }
}

function initTheme() {
    // Check localStorage for saved preference
    const savedTheme = localStorage.getItem('comfyui-indexer-theme');

    if (savedTheme) {
        applyTheme(savedTheme);
    } else {
        // Check system preference
        if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
            applyTheme('light');
        }
    }

    // Add event listener for theme toggle
    if (elements.themeToggle) {
        elements.themeToggle.addEventListener('click', toggleTheme);
    }
}

// ========================================
// Initialize
// ========================================

document.addEventListener('DOMContentLoaded', () => {
    initEventListeners();
    initTheme();
    // Don't auto-load gallery - show welcome prompt instead
    // loadGallery(); 
    // Pre-load directories for the welcome screen
    loadDirectories();
});


