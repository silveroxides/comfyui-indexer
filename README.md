# ComfyUI Metadata Indexer

A powerful metadata indexing system for ComfyUI-generated images. Search, browse, and explore your AI-generated images through their embedded workflow and prompt data.

![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)

## Features

- 📸 **Automatic Metadata Extraction** - Parse PNG/WebP images with embedded ComfyUI workflow data
- 🔍 **Powerful Search** - Full-text, regex, and fuzzy search across all metadata
- 🎨 **Modern Web UI** - Gallery view with lightbox and metadata inspection
- ⚡ **Fast & Incremental** - Only re-indexes changed files
- 🖥️ **CLI Tool** - Command-line interface for automation
- 🔌 **REST API** - Full API for integration with other tools

## Quick Start

### Installation

```bash
# Clone or download the project
cd ImageBrowsingParsing

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install as editable package
pip install -e .
```

### Basic Usage

```bash
# Scan a directory of images
comfy-idx scan "C:\path\to\your\images" --recursive

# Search for images
comfy-idx search "portrait"
comfy-idx search ".*sdxl.*" --mode regex --category model

# Start the web server
comfy-idx serve --port 8000

# Open http://localhost:8000 in your browser
```

## CLI Commands

```bash
# Index Management
comfy-idx scan <directory>     # Scan and index images
comfy-idx stats                # Show index statistics
comfy-idx cleanup              # Remove entries for deleted files

# Search
comfy-idx search <query>       # Full-text search
comfy-idx search <pattern> --mode regex    # Regex search
comfy-idx search <text> --mode fuzzy       # Fuzzy/typo-tolerant search
comfy-idx models               # List all models used
comfy-idx nodes                # List all node types

# Server
comfy-idx serve                # Start API server (port 8000)
comfy-idx serve --port 3000    # Custom port

# Image Details
comfy-idx show <image_id>      # Show image metadata
comfy-idx show <image_id> --json  # JSON output
```

## Search Modes

| Mode | Description | Example |
|------|-------------|---------|
| `fts` | Full-text search (default) | `comfy-idx search "beautiful landscape"` |
| `regex` | Regular expression | `comfy-idx search ".*xl.*" --mode regex` |
| `fuzzy` | Typo-tolerant fuzzy matching | `comfy-idx search "protrait" --mode fuzzy` |
| `exact` | Exact match | `comfy-idx search "model.safetensors" --mode exact` |

## API Endpoints

Start the server with `comfy-idx serve` and access API docs at `http://localhost:8000/docs`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/search` | Search metadata |
| GET | `/api/images` | List images (paginated) |
| GET | `/api/images/{id}` | Get image details |
| GET | `/api/images/{id}/file` | Serve image file |
| GET | `/api/images/{id}/thumbnail` | Get thumbnail |
| POST | `/api/index/scan` | Scan a directory |
| GET | `/api/index/stats` | Get index statistics |
| GET | `/api/search/models` | List all models |
| GET | `/api/search/node-types` | List all node types |

## Project Structure

```
ImageBrowsingParsing/
├── comfyui_indexer/
│   ├── __init__.py
│   ├── parser.py          # PNG metadata extraction
│   ├── indexer.py         # SQLite database operations
│   ├── search.py          # Search engine (FTS5, regex, fuzzy)
│   ├── cli.py             # CLI commands
│   └── api/
│       ├── main.py        # FastAPI application
│       ├── models.py      # Pydantic schemas
│       └── routes/        # API endpoints
├── web/                   # Static WebUI files
│   ├── index.html
│   ├── css/styles.css
│   └── js/app.js
├── pyproject.toml
└── README.md
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `COMFY_IDX_DB` | `comfyui_index.db` | Database file path |

### Database Location

By default, the database is created in the current directory. Use the `--db` flag or `COMFY_IDX_DB` environment variable to specify a custom path:

```bash
# Using flag
comfy-idx scan "C:\images" --db "D:\data\comfy.db"

# Using environment variable
set COMFY_IDX_DB=D:\data\comfy.db
comfy-idx serve
```

## Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with auto-reload
comfy-idx serve --reload
```

## How It Works

1. **Parsing**: ComfyUI embeds workflow data in PNG `tEXt` chunks as JSON. The parser extracts this data along with the full workflow graph.

2. **Indexing**: Extracted metadata is normalized into an SQLite database with FTS5 full-text search. File hashes enable incremental updates.

3. **Searching**: Multiple search modes leverage SQLite FTS5 for full-text, Python `re` for regex, and `rapidfuzz` for fuzzy matching.

4. **Serving**: FastAPI provides a REST API, and the WebUI is served as static files with on-demand thumbnail generation.

## License

MIT License - see LICENSE file for details.

## Acknowledgments

- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) - The amazing modular diffusion GUI
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [rapidfuzz](https://github.com/maxbachmann/RapidFuzz) - Fast fuzzy string matching
