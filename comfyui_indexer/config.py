"""
Configuration management for ComfyUI Indexer.

Handles exclusion rules and other settings stored in project-local config.
"""

import json
import fnmatch
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class IndexerConfig:
    """Configuration for indexer behavior."""
    
    # Keys to exclude from indexing (supports glob patterns)
    exclude_keys: list[str] = field(default_factory=list)
    
    # Categories to skip entirely
    exclude_categories: list[str] = field(default_factory=list)
    
    # Minimum value length to index
    min_value_length: int = 4
    
    # Skip node_type indexing (recommended for size)
    skip_node_types: bool = True
    
    # Skip all_values indexing (recommended for size)
    skip_all_values: bool = True
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'IndexerConfig':
        """Create from dictionary."""
        return cls(
            exclude_keys=data.get('exclude_keys', []),
            exclude_categories=data.get('exclude_categories', []),
            min_value_length=data.get('min_value_length', 4),
            skip_node_types=data.get('skip_node_types', True),
            skip_all_values=data.get('skip_all_values', True),
        )


class ConfigManager:
    """Manages project-local configuration."""
    
    CONFIG_FILENAME = '.comfyui-indexer.json'
    
    def __init__(self, project_dir: Optional[Path] = None):
        """
        Initialize config manager.
        
        Args:
            project_dir: Project directory (defaults to current working directory)
        """
        self.project_dir = Path(project_dir) if project_dir else Path.cwd()
        self.config_path = self.project_dir / self.CONFIG_FILENAME
        self._config: Optional[IndexerConfig] = None
    
    @property
    def config(self) -> IndexerConfig:
        """Get current configuration, loading from file if needed."""
        if self._config is None:
            self._config = self.load()
        return self._config
    
    def load(self) -> IndexerConfig:
        """Load configuration from file."""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return IndexerConfig.from_dict(data)
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Warning: Failed to load config from {self.config_path}: {e}")
        
        return IndexerConfig()
    
    def save(self, config: Optional[IndexerConfig] = None) -> None:
        """Save configuration to file."""
        if config is not None:
            self._config = config
        
        if self._config is None:
            self._config = IndexerConfig()
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self._config.to_dict(), f, indent=2)
    
    def add_exclusion(self, key_pattern: str) -> bool:
        """
        Add a key pattern to exclusion list.
        
        Args:
            key_pattern: Glob pattern for keys to exclude
            
        Returns:
            True if added, False if already exists
        """
        if key_pattern not in self.config.exclude_keys:
            self.config.exclude_keys.append(key_pattern)
            self.save()
            return True
        return False
    
    def remove_exclusion(self, key_pattern: str) -> bool:
        """
        Remove a key pattern from exclusion list.
        
        Args:
            key_pattern: Pattern to remove
            
        Returns:
            True if removed, False if not found
        """
        if key_pattern in self.config.exclude_keys:
            self.config.exclude_keys.remove(key_pattern)
            self.save()
            return True
        return False
    
    def should_exclude_key(self, key: str) -> bool:
        """
        Check if a key should be excluded based on patterns.
        
        Args:
            key: The key name to check
            
        Returns:
            True if key matches any exclusion pattern
        """
        for pattern in self.config.exclude_keys:
            if fnmatch.fnmatch(key, pattern):
                return True
        return False
    
    def export_rules(self, filepath: Path) -> None:
        """Export exclusion rules to a shareable JSON file."""
        export_data = {
            'version': '1.0',
            'description': 'ComfyUI Indexer exclusion rules',
            'exclude_keys': self.config.exclude_keys,
            'exclude_categories': self.config.exclude_categories,
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2)
    
    def import_rules(self, filepath: Path, merge: bool = True) -> int:
        """
        Import exclusion rules from a JSON file.
        
        Args:
            filepath: Path to import file
            merge: If True, merge with existing rules. If False, replace.
            
        Returns:
            Number of new rules added
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        new_keys = data.get('exclude_keys', [])
        new_categories = data.get('exclude_categories', [])
        
        added = 0
        
        if merge:
            for key in new_keys:
                if key not in self.config.exclude_keys:
                    self.config.exclude_keys.append(key)
                    added += 1
            for cat in new_categories:
                if cat not in self.config.exclude_categories:
                    self.config.exclude_categories.append(cat)
                    added += 1
        else:
            added = len(new_keys) + len(new_categories)
            self.config.exclude_keys = new_keys
            self.config.exclude_categories = new_categories
        
        self.save()
        return added


# Default config manager instance
_default_manager: Optional[ConfigManager] = None


def get_config_manager(project_dir: Optional[Path] = None) -> ConfigManager:
    """Get default config manager instance."""
    global _default_manager
    if _default_manager is None or project_dir is not None:
        _default_manager = ConfigManager(project_dir)
    return _default_manager


def get_exclusion_rules() -> dict:
    """
    Get current exclusion rules for agent integration.
    
    Returns:
        Dictionary with exclusion rules
    """
    manager = get_config_manager()
    return {
        'exclude_keys': manager.config.exclude_keys,
        'exclude_categories': manager.config.exclude_categories,
        'min_value_length': manager.config.min_value_length,
        'skip_node_types': manager.config.skip_node_types,
        'skip_all_values': manager.config.skip_all_values,
    }
