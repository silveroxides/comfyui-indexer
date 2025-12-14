"""
CLI tool for ComfyUI Metadata Indexer.

Provides commands for scanning, searching, and managing the index.
"""

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax

from .indexer import Indexer
from .search import SearchEngine

app = typer.Typer(
    name="comfy-idx",
    help="ComfyUI Metadata Indexer - Search and manage your AI-generated images",
    add_completion=False,
)

console = Console()

# Default database path
DEFAULT_DB = "comfyui_index.db"


def get_db_path(db: Optional[str] = None) -> str:
    """Get database path from argument or environment."""
    import os
    return db or os.environ.get("COMFY_IDX_DB", DEFAULT_DB)


@app.command()
def scan(
    directory: str = typer.Argument(..., help="Directory to scan for images"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", "-r/-R", help="Scan subdirectories"),
    force: bool = typer.Option(False, "--force", "-f", help="Force re-index unchanged files"),
    db: Optional[str] = typer.Option(None, "--db", "-d", help="Database path"),
):
    """
    Scan a directory and index all ComfyUI images.
    
    Supports PNG and WebP files with embedded ComfyUI metadata.
    """
    db_path = get_db_path(db)
    directory_path = Path(directory)
    
    if not directory_path.exists():
        console.print(f"[red]Error:[/red] Directory not found: {directory}")
        raise typer.Exit(1)
    
    console.print(f"[blue]📁 Database:[/blue] {db_path}")
    console.print(f"[blue]📂 Scanning:[/blue] {directory_path.absolute()}")
    
    indexer = Indexer(db_path)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Scanning...", total=None)
        
        def update_progress(current, total, file_path):
            progress.update(task, total=total, completed=current, description=f"Processing {Path(file_path).name[:40]}")
        
        stats = indexer.scan_directory(
            directory=directory_path,
            recursive=recursive,
            force=force,
            progress_callback=update_progress
        )
    
    # Print results
    table = Table(title="Scan Results", show_header=False)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Files scanned", str(stats['scanned']))
    table.add_row("New indexed", str(stats['indexed']))
    table.add_row("Updated", str(stats['updated']))
    table.add_row("Skipped (unchanged)", str(stats['skipped']))
    table.add_row("Errors", str(stats['errors']))
    
    console.print(table)


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    mode: str = typer.Option("fts", "--mode", "-m", help="Search mode: fts, regex, fuzzy, exact"),
    category: Optional[str] = typer.Option(None, "--category", "-c", help="Filter by category: prompt, model, value"),
    field: Optional[str] = typer.Option(None, "--field", "-f", help="Filter by field/key name"),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum results"),
    threshold: float = typer.Option(60.0, "--threshold", "-t", help="Fuzzy match threshold (0-100)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
    db: Optional[str] = typer.Option(None, "--db", "-d", help="Database path"),
):
    """
    Search the metadata index.
    
    Examples:
    
        comfy-idx search "portrait"
        
        comfy-idx search ".*sdxl.*" --mode regex --category model
        
        comfy-idx search "beautful landscape" --mode fuzzy
    """
    db_path = get_db_path(db)
    engine = SearchEngine(db_path)
    
    result = engine.search(
        query=query,
        mode=mode,
        field=field,
        category=category,
        limit=limit,
        threshold=threshold
    )
    
    if json_output:
        # JSON output
        output = {
            "query": result.query,
            "mode": result.mode,
            "total_results": result.total_results,
            "search_time_ms": result.search_time_ms,
            "results": [
                {
                    "image_id": r.image_id,
                    "file_path": r.file_path,
                    "score": r.score,
                    "matches": r.matches
                }
                for r in result.results
            ]
        }
        console.print(json.dumps(output, indent=2, default=str))
    else:
        # Pretty output
        console.print(f"\n[blue]Search:[/blue] {query} [dim]({mode} mode, {result.search_time_ms:.1f}ms)[/dim]")
        console.print(f"[blue]Results:[/blue] {result.total_results}\n")
        
        if not result.results:
            console.print("[yellow]No results found.[/yellow]")
            return
        
        for r in result.results:
            # Panel for each result
            path = Path(r.file_path)
            title = f"[bold]{path.name}[/bold] [dim](ID: {r.image_id}, Score: {r.score:.1f})[/dim]"
            
            content = f"[dim]{r.file_path}[/dim]\n"
            
            # Show top matches
            for match in r.matches[:5]:
                value = (match['value'] or '')[:100]
                if len(match.get('value', '') or '') > 100:
                    value += "..."
                content += f"\n[cyan]{match['category']}[/cyan].[green]{match['key']}[/green]: {value}"
            
            if len(r.matches) > 5:
                content += f"\n[dim]... and {len(r.matches) - 5} more matches[/dim]"
            
            console.print(Panel(content, title=title, border_style="blue"))


@app.command()
def stats(
    db: Optional[str] = typer.Option(None, "--db", "-d", help="Database path"),
):
    """
    Show index statistics.
    """
    db_path = get_db_path(db)
    indexer = Indexer(db_path)
    
    s = indexer.get_stats()
    
    # Format database size
    size = s.database_size_bytes
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            size_str = f"{size:.1f} {unit}"
            break
        size /= 1024
    else:
        size_str = f"{size:.1f} TB"
    
    table = Table(title="Index Statistics", show_header=False)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Total images", f"{s.total_images:,}")
    table.add_row("Metadata entries", f"{s.total_metadata_entries:,}")
    table.add_row("Unique models", f"{s.unique_models:,}")
    table.add_row("Unique node types", f"{s.unique_node_types:,}")
    table.add_row("Database size", size_str)
    table.add_row("Last scan", str(s.last_scan_at) if s.last_scan_at else "Never")
    
    console.print(table)


@app.command()
def models(
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum models to show"),
    db: Optional[str] = typer.Option(None, "--db", "-d", help="Database path"),
):
    """
    List all models used in indexed images.
    """
    db_path = get_db_path(db)
    engine = SearchEngine(db_path)
    
    values = engine.get_all_models(limit=limit)
    
    if not values:
        console.print("[yellow]No models found.[/yellow]")
        return
    
    table = Table(title="Models", show_header=True)
    table.add_column("Model", style="cyan", no_wrap=True)
    table.add_column("Count", style="green", justify="right")
    
    for v in values:
        if v['value']:
            table.add_row(v['value'], str(v['count']))
    
    console.print(table)


@app.command()
def nodes(
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum node types to show"),
    db: Optional[str] = typer.Option(None, "--db", "-d", help="Database path"),
):
    """
    List all ComfyUI node types used.
    """
    db_path = get_db_path(db)
    engine = SearchEngine(db_path)
    
    values = engine.get_all_node_types(limit=limit)
    
    if not values:
        console.print("[yellow]No node types found.[/yellow]")
        return
    
    table = Table(title="Node Types", show_header=True)
    table.add_column("Node Type", style="cyan")
    table.add_column("Count", style="green", justify="right")
    
    for v in values:
        if v['value']:
            table.add_row(v['value'], str(v['count']))
    
    console.print(table)


@app.command()
def show(
    image_id: int = typer.Argument(..., help="Image ID to show"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
    db: Optional[str] = typer.Option(None, "--db", "-d", help="Database path"),
):
    """
    Show details for a specific image.
    """
    db_path = get_db_path(db)
    indexer = Indexer(db_path)
    
    image = indexer.get_image(image_id)
    
    if not image:
        console.print(f"[red]Error:[/red] Image not found: {image_id}")
        raise typer.Exit(1)
    
    metadata = indexer.get_image_metadata(image_id)
    
    if json_output:
        output = {
            "id": image.id,
            "file_path": image.file_path,
            "file_hash": image.file_hash,
            "file_size": image.file_size,
            "width": image.width,
            "height": image.height,
            "created_at": str(image.created_at),
            "indexed_at": str(image.indexed_at),
            "metadata": metadata,
            "raw_prompt": image.raw_prompt,
            "raw_workflow": image.raw_workflow,
        }
        console.print(json.dumps(output, indent=2, default=str))
    else:
        # Pretty output
        console.print(f"\n[bold blue]Image {image_id}[/bold blue]")
        console.print(f"[dim]{image.file_path}[/dim]\n")
        
        info_table = Table(show_header=False, box=None)
        info_table.add_column("Key", style="cyan")
        info_table.add_column("Value")
        
        info_table.add_row("Size", f"{image.width}x{image.height}" if image.width else "Unknown")
        info_table.add_row("File size", f"{image.file_size:,} bytes" if image.file_size else "Unknown")
        info_table.add_row("Created", str(image.created_at) if image.created_at else "Unknown")
        info_table.add_row("Indexed", str(image.indexed_at) if image.indexed_at else "Unknown")
        
        console.print(info_table)
        
        if metadata:
            console.print("\n[bold]Metadata:[/bold]")
            
            # Group by category
            by_category: dict = {}
            for m in metadata:
                cat = m['category']
                if cat not in by_category:
                    by_category[cat] = []
                by_category[cat].append(m)
            
            for category, items in by_category.items():
                console.print(f"\n[cyan]{category}:[/cyan]")
                for item in items[:10]:
                    value = (item['value'] or '')[:80]
                    if len(item.get('value', '') or '') > 80:
                        value += "..."
                    console.print(f"  [green]{item['key']}[/green]: {value}")
                if len(items) > 10:
                    console.print(f"  [dim]... and {len(items) - 10} more[/dim]")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host to bind to"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind to"),
    db: Optional[str] = typer.Option(None, "--db", "-d", help="Database path"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload"),
):
    """
    Start the API server.
    """
    import os
    import uvicorn
    
    db_path = get_db_path(db)
    os.environ["COMFY_IDX_DB"] = db_path
    
    console.print(f"[blue]📁 Database:[/blue] {db_path}")
    console.print(f"[blue]🚀 Starting server:[/blue] http://{host}:{port}")
    console.print(f"[blue]📚 API Docs:[/blue] http://{host}:{port}/docs")
    console.print()
    
    uvicorn.run(
        "comfyui_indexer.api.main:app",
        host=host,
        port=port,
        reload=reload,
    )


@app.command()
def cleanup(
    db: Optional[str] = typer.Option(None, "--db", "-d", help="Database path"),
):
    """
    Remove entries for files that no longer exist.
    """
    db_path = get_db_path(db)
    indexer = Indexer(db_path)
    
    console.print("[blue]Checking for missing files...[/blue]")
    
    removed = indexer.remove_missing_files()
    
    if removed > 0:
        console.print(f"[green]Removed {removed} entries for missing files.[/green]")
    else:
        console.print("[dim]No missing files found.[/dim]")


# ========================================
# Database Analysis Commands
# ========================================

db_app = typer.Typer(
    name="db",
    help="Database analysis and optimization tools",
)
app.add_typer(db_app, name="db")


@db_app.command("stats")
def db_stats(
    db: Optional[str] = typer.Option(None, "--db", "-d", help="Database path"),
):
    """
    Show detailed database statistics.
    """
    from .db_utils import DatabaseAnalyzer, format_bytes
    
    db_path = get_db_path(db)
    analyzer = DatabaseAnalyzer(db_path)
    stats = analyzer.get_stats()
    
    console.print("\n[bold blue]Database Statistics[/bold blue]\n")
    
    table = Table(show_header=False, box=None)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Total images", f"{stats.total_images:,}")
    table.add_row("Total metadata rows", f"{stats.total_metadata:,}")
    table.add_row("Rows per image (avg)", f"{stats.rows_per_image:.1f}")
    table.add_row("Database size", format_bytes(stats.database_size_bytes))
    
    console.print(table)
    
    if stats.categories:
        console.print("\n[bold]By Category:[/bold]")
        cat_table = Table(show_header=True)
        cat_table.add_column("Category", style="cyan")
        cat_table.add_column("Count", justify="right")
        cat_table.add_column("%", justify="right")
        cat_table.add_column("Unique Keys", justify="right")
        cat_table.add_column("Unique Values", justify="right")
        
        for cat in stats.categories:
            cat_table.add_row(
                cat.category,
                f"{cat.count:,}",
                f"{cat.percentage:.1f}%",
                str(cat.unique_keys),
                f"{cat.unique_values:,}"
            )
        
        console.print(cat_table)


@db_app.command("analyze")
def db_analyze(
    category: Optional[str] = typer.Option(None, "--category", "-c", help="Category to analyze"),
    top: int = typer.Option(30, "--top", "-t", help="Number of top keys to show"),
    db: Optional[str] = typer.Option(None, "--db", "-d", help="Database path"),
):
    """
    Analyze key frequency in the database.
    """
    from .db_utils import DatabaseAnalyzer
    
    db_path = get_db_path(db)
    analyzer = DatabaseAnalyzer(db_path)
    keys = analyzer.get_key_frequency(category=category, limit=top)
    
    title = f"Top {top} Keys" + (f" in '{category}'" if category else " (all categories)")
    console.print(f"\n[bold blue]{title}[/bold blue]\n")
    
    table = Table(show_header=True)
    table.add_column("#", justify="right", style="dim")
    table.add_column("Key", style="cyan")
    table.add_column("Category", style="yellow")
    table.add_column("Count", justify="right", style="green")
    table.add_column("Unique Values", justify="right")
    table.add_column("Avg Length", justify="right", style="dim")
    
    for i, key in enumerate(keys, 1):
        table.add_row(
            str(i),
            key.key,
            key.category,
            f"{key.count:,}",
            str(key.unique_values),
            f"{key.avg_value_length:.0f}"
        )
    
    console.print(table)


@db_app.command("bloat")
def db_bloat(
    threshold: float = typer.Option(0.5, "--threshold", "-t", help="Min ratio of images (0.0-1.0)"),
    db: Optional[str] = typer.Option(None, "--db", "-d", help="Database path"),
):
    """
    Find bloat candidates - keys that appear in many images with low unique value ratio.
    """
    from .db_utils import DatabaseAnalyzer
    
    db_path = get_db_path(db)
    analyzer = DatabaseAnalyzer(db_path)
    bloat = analyzer.find_bloat_candidates(threshold_ratio=threshold)
    
    console.print(f"\n[bold blue]Bloat Candidates[/bold blue] (appearing in >{threshold*100:.0f}% of images)\n")
    
    if not bloat:
        console.print("[green]No obvious bloat patterns found.[/green]")
        return
    
    table = Table(show_header=True)
    table.add_column("Key", style="cyan")
    table.add_column("Category", style="yellow")
    table.add_column("Count", justify="right", style="red")
    table.add_column("Unique Values", justify="right")
    table.add_column("Status", style="dim")
    
    for key in bloat:
        table.add_row(
            key.key,
            key.category,
            f"{key.count:,}",
            str(key.unique_values),
            "⚠️ Candidate for exclusion"
        )
    
    console.print(table)
    console.print("\n[dim]Use 'comfy-idx db exclude --key <key>' to add to exclusion list.[/dim]")


@db_app.command("exclude")
def db_exclude(
    key: str = typer.Argument(..., help="Key pattern to exclude (supports glob: widget_*)"),
):
    """
    Add a key pattern to the exclusion list.
    """
    from .config import get_config_manager
    
    manager = get_config_manager()
    if manager.add_exclusion(key):
        console.print(f"[green]✓ Added '{key}' to exclusion list.[/green]")
    else:
        console.print(f"[yellow]'{key}' is already in exclusion list.[/yellow]")


@db_app.command("include")
def db_include(
    key: str = typer.Argument(..., help="Key pattern to remove from exclusion list"),
):
    """
    Remove a key pattern from the exclusion list.
    """
    from .config import get_config_manager
    
    manager = get_config_manager()
    if manager.remove_exclusion(key):
        console.print(f"[green]✓ Removed '{key}' from exclusion list.[/green]")
    else:
        console.print(f"[yellow]'{key}' was not in exclusion list.[/yellow]")


@db_app.command("exclusions")
def db_exclusions():
    """
    List current exclusion rules.
    """
    from .config import get_config_manager
    
    manager = get_config_manager()
    config = manager.config
    
    console.print("\n[bold blue]Current Exclusion Rules[/bold blue]\n")
    console.print(f"[dim]Config file: {manager.config_path}[/dim]\n")
    
    if config.exclude_keys:
        console.print("[cyan]Excluded Keys:[/cyan]")
        for key in config.exclude_keys:
            console.print(f"  - {key}")
    else:
        console.print("[dim]No key exclusions configured.[/dim]")
    
    console.print(f"\n[cyan]Settings:[/cyan]")
    console.print(f"  Min value length: {config.min_value_length}")
    console.print(f"  Skip node types: {config.skip_node_types}")
    console.print(f"  Skip all values: {config.skip_all_values}")


@db_app.command("export")
def db_export(
    output: str = typer.Argument(..., help="Output file path (JSON)"),
):
    """
    Export exclusion rules to a shareable JSON file.
    """
    from .config import get_config_manager
    
    manager = get_config_manager()
    output_path = Path(output)
    manager.export_rules(output_path)
    
    console.print(f"[green]✓ Exported rules to {output_path}[/green]")


@db_app.command("import")
def db_import(
    input_file: str = typer.Argument(..., help="Input file path (JSON)"),
    replace: bool = typer.Option(False, "--replace", "-r", help="Replace existing rules instead of merging"),
):
    """
    Import exclusion rules from a JSON file.
    """
    from .config import get_config_manager
    
    manager = get_config_manager()
    input_path = Path(input_file)
    
    if not input_path.exists():
        console.print(f"[red]Error: File not found: {input_path}[/red]")
        raise typer.Exit(1)
    
    added = manager.import_rules(input_path, merge=not replace)
    
    action = "Replaced with" if replace else "Added"
    console.print(f"[green]✓ {action} {added} rules from {input_path}[/green]")


if __name__ == "__main__":
    app()
