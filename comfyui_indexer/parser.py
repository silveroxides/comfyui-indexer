"""
PNG/WebP metadata parser for ComfyUI-generated images.

Extracts workflow and prompt data embedded in image metadata.
ComfyUI stores JSON data in PNG tEXt chunks with keys 'prompt' and 'workflow'.
"""

import json
import re
import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ExtractedMetadata:
    """Parsed metadata from a ComfyUI image."""
    
    file_path: str
    prompt: dict[str, Any] | None = None
    workflow: dict[str, Any] | None = None
    
    # Extracted fields for indexing
    prompts: list[dict[str, str]] = field(default_factory=list)  # text prompts found
    models: list[dict[str, str]] = field(default_factory=list)   # model references
    parameters: dict[str, Any] = field(default_factory=dict)      # generation params
    node_types: list[str] = field(default_factory=list)           # node class types used
    all_values: list[dict[str, Any]] = field(default_factory=list)  # all key-value pairs
    
    # Image info
    width: int | None = None
    height: int | None = None
    
    @property
    def has_metadata(self) -> bool:
        """Check if any ComfyUI metadata was found."""
        return self.prompt is not None or self.workflow is not None


class MetadataParser:
    """Parser for extracting ComfyUI metadata from images."""
    
    # Keys that typically contain prompt text
    PROMPT_KEYS = {
        'text', 'string', 'prompt', 'positive', 'negative',
        'positive_prompt', 'negative_prompt', 'text_positive', 'text_negative',
        'conditioning', 'caption', 'description'
    }
    
    # Keys that contain model references
    MODEL_KEYS = {
        'model_name', 'ckpt_name', 'clip_name', 'vae_name',
        'lora_name', 'control_net_name', 'unet_name',
        'model', 'checkpoint', 'lora', 'controlnet'
    }
    
    # Keys for generation parameters
    PARAM_KEYS = {
        'steps', 'cfg', 'cfg_scale', 'sampler', 'sampler_name',
        'scheduler', 'seed', 'denoise', 'width', 'height',
        'batch_size', 'noise_seed'
    }
    
    def __init__(self):
        self._safetensors_pattern = re.compile(r'.*\.safetensors$', re.IGNORECASE)
        self._ckpt_pattern = re.compile(r'.*\.(ckpt|pt|pth|bin)$', re.IGNORECASE)
    
    def parse_file(self, file_path: str | Path) -> ExtractedMetadata:
        """
        Parse a single image file and extract metadata.
        
        Args:
            file_path: Path to the image file
            
        Returns:
            ExtractedMetadata with parsed content
        """
        file_path = Path(file_path)
        result = ExtractedMetadata(file_path=str(file_path))
        
        if not file_path.exists():
            return result
        
        suffix = file_path.suffix.lower()
        
        try:
            if suffix == '.png':
                raw_metadata = self._read_png_metadata(file_path)
            elif suffix == '.webp':
                raw_metadata = self._read_webp_metadata(file_path)
            else:
                return result
            
            # Parse the raw metadata
            if 'prompt' in raw_metadata:
                try:
                    result.prompt = json.loads(raw_metadata['prompt'])
                except json.JSONDecodeError:
                    pass
            
            if 'workflow' in raw_metadata:
                try:
                    result.workflow = json.loads(raw_metadata['workflow'])
                except json.JSONDecodeError:
                    pass
            
            # Extract structured data from the parsed JSON
            self._extract_fields(result)
            
            # Try to get image dimensions
            self._extract_dimensions(file_path, result)
            
        except Exception:
            # If parsing fails, return empty metadata
            pass
        
        return result
    
    def _read_png_metadata(self, file_path: Path) -> dict[str, str]:
        """Read metadata from PNG tEXt and iTXt chunks."""
        metadata = {}
        
        with open(file_path, 'rb') as f:
            # Verify PNG signature
            signature = f.read(8)
            if signature != b'\x89PNG\r\n\x1a\n':
                return metadata
            
            # Read chunks
            while True:
                try:
                    # Read chunk header
                    length_bytes = f.read(4)
                    if len(length_bytes) < 4:
                        break
                    
                    length = struct.unpack('>I', length_bytes)[0]
                    chunk_type = f.read(4)
                    
                    if len(chunk_type) < 4:
                        break
                    
                    # Read chunk data
                    data = f.read(length)
                    crc = f.read(4)  # CRC (not validated)
                    
                    if chunk_type == b'IEND':
                        break
                    
                    # Parse tEXt chunk (uncompressed)
                    if chunk_type == b'tEXt':
                        try:
                            null_idx = data.index(b'\x00')
                            key = data[:null_idx].decode('latin-1')
                            value = data[null_idx + 1:].decode('latin-1')
                            metadata[key] = value
                        except (ValueError, UnicodeDecodeError):
                            pass
                    
                    # Parse iTXt chunk (international text, possibly compressed)
                    elif chunk_type == b'iTXt':
                        try:
                            null_idx = data.index(b'\x00')
                            key = data[:null_idx].decode('utf-8')
                            
                            # Skip compression flag, method, language tag, translated keyword
                            rest = data[null_idx + 1:]
                            compression_flag = rest[0]
                            compression_method = rest[1]
                            rest = rest[2:]
                            
                            # Skip language tag
                            null_idx = rest.index(b'\x00')
                            rest = rest[null_idx + 1:]
                            
                            # Skip translated keyword
                            null_idx = rest.index(b'\x00')
                            text_data = rest[null_idx + 1:]
                            
                            if compression_flag == 1:
                                text_data = zlib.decompress(text_data)
                            
                            value = text_data.decode('utf-8')
                            metadata[key] = value
                        except (ValueError, UnicodeDecodeError, zlib.error):
                            pass
                    
                    # Parse zTXt chunk (compressed text)
                    elif chunk_type == b'zTXt':
                        try:
                            null_idx = data.index(b'\x00')
                            key = data[:null_idx].decode('latin-1')
                            compression_method = data[null_idx + 1]
                            compressed_data = data[null_idx + 2:]
                            
                            if compression_method == 0:  # zlib
                                value = zlib.decompress(compressed_data).decode('latin-1')
                                metadata[key] = value
                        except (ValueError, UnicodeDecodeError, zlib.error):
                            pass
                
                except Exception:
                    break
        
        return metadata
    
    def _read_webp_metadata(self, file_path: Path) -> dict[str, str]:
        """Read metadata from WebP EXIF data."""
        metadata = {}
        
        # WebP metadata extraction is more complex
        # For now, try using PIL if available
        try:
            from PIL import Image
            with Image.open(file_path) as img:
                exif = img.getexif()
                if exif:
                    # Check for UserComment or ImageDescription
                    for tag_id in [0x9286, 0x010E]:  # UserComment, ImageDescription
                        if tag_id in exif:
                            data = exif[tag_id]
                            if isinstance(data, bytes):
                                data = data.decode('utf-8', errors='ignore')
                            
                            # Try to parse as JSON
                            try:
                                parsed = json.loads(data)
                                if isinstance(parsed, dict):
                                    if 'prompt' in parsed:
                                        metadata['prompt'] = json.dumps(parsed['prompt'])
                                    if 'workflow' in parsed:
                                        metadata['workflow'] = json.dumps(parsed['workflow'])
                            except json.JSONDecodeError:
                                pass
        except ImportError:
            pass
        except Exception:
            pass
        
        return metadata
    
    def _extract_fields(self, result: ExtractedMetadata) -> None:
        """Extract searchable fields from parsed metadata."""
        
        # Process prompt data (node outputs/inputs)
        if result.prompt:
            self._process_prompt_data(result.prompt, result)
        
        # Process workflow data (full node graph)
        if result.workflow:
            self._process_workflow_data(result.workflow, result)
    
    def _process_prompt_data(self, prompt: dict, result: ExtractedMetadata) -> None:
        """Process the prompt JSON structure."""
        
        for node_id, node_data in prompt.items():
            if not isinstance(node_data, dict):
                continue
            
            class_type = node_data.get('class_type', '')
            if class_type:
                if class_type not in result.node_types:
                    result.node_types.append(class_type)
            
            inputs = node_data.get('inputs', {})
            if isinstance(inputs, dict):
                self._extract_from_inputs(inputs, class_type, node_id, result)
    
    def _process_workflow_data(self, workflow: dict, result: ExtractedMetadata) -> None:
        """Process the workflow JSON structure."""
        
        nodes = workflow.get('nodes', [])
        if not isinstance(nodes, list):
            return
        
        for node in nodes:
            if not isinstance(node, dict):
                continue
            
            node_type = node.get('type', '')
            node_id = str(node.get('id', ''))
            
            if node_type and node_type not in result.node_types:
                result.node_types.append(node_type)
            
            # Check widgets_values for additional data
            widgets = node.get('widgets_values', [])
            if isinstance(widgets, list):
                for i, value in enumerate(widgets):
                    if value is not None:
                        self._categorize_value(
                            key=f"widget_{i}",
                            value=value,
                            node_type=node_type,
                            node_id=node_id,
                            result=result
                        )
    
    def _extract_from_inputs(
        self, 
        inputs: dict, 
        class_type: str, 
        node_id: str, 
        result: ExtractedMetadata
    ) -> None:
        """Extract relevant data from node inputs."""
        
        for key, value in inputs.items():
            # Skip connection references (lists like [node_id, output_idx])
            if isinstance(value, list):
                continue
            
            self._categorize_value(key, value, class_type, node_id, result)
    
    def _categorize_value(
        self,
        key: str,
        value: Any,
        node_type: str,
        node_id: str,
        result: ExtractedMetadata
    ) -> None:
        """Categorize a value into prompts, models, or parameters."""
        
        key_lower = key.lower()
        
        # Store all string values for full-text search
        if isinstance(value, str) and value.strip():
            result.all_values.append({
                'key': key,
                'value': value,
                'node_type': node_type,
                'node_id': node_id
            })
            
            # Check if it's a model file reference
            if self._safetensors_pattern.match(value) or self._ckpt_pattern.match(value):
                result.models.append({
                    'key': key,
                    'value': value,
                    'node_type': node_type,
                    'node_id': node_id
                })
            # Check if it's a prompt-like field
            elif key_lower in self.PROMPT_KEYS or any(pk in key_lower for pk in ['prompt', 'text']):
                result.prompts.append({
                    'key': key,
                    'value': value,
                    'node_type': node_type,
                    'node_id': node_id
                })
        
        # Check for model keys explicitly
        if key_lower in self.MODEL_KEYS:
            if isinstance(value, str) and value.strip():
                if not any(m['value'] == value for m in result.models):
                    result.models.append({
                        'key': key,
                        'value': value,
                        'node_type': node_type,
                        'node_id': node_id
                    })
        
        # Extract generation parameters
        if key_lower in self.PARAM_KEYS:
            result.parameters[key] = value
    
    def _extract_dimensions(self, file_path: Path, result: ExtractedMetadata) -> None:
        """Try to extract image dimensions."""
        try:
            from PIL import Image
            with Image.open(file_path) as img:
                result.width, result.height = img.size
        except Exception:
            pass


def parse_image(file_path: str | Path) -> ExtractedMetadata:
    """
    Convenience function to parse a single image.
    
    Args:
        file_path: Path to the image file
        
    Returns:
        ExtractedMetadata with parsed content
    """
    parser = MetadataParser()
    return parser.parse_file(file_path)
