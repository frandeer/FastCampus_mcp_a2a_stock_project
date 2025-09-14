"""
Data Transformer Plugin Example

Demonstrates a transformer-type plugin that processes and transforms data
between different formats with validation, caching, and performance monitoring.
"""

import asyncio
import json
import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
import re

from ..interfaces import TransformerPlugin, PluginConfig, PluginHealth
from ..decorators import (
    plugin_metadata, config_schema, lifecycle_hook, requires_permission,
    monitor_performance, retry_on_failure, timeout, validate_input,
    cache_result, log_calls,
    HookType, PermissionType
)


@plugin_metadata(
    name="data_transformer",
    version="2.1.0",
    description="Universal data transformer supporting JSON, XML, CSV, and custom formats",
    author="Universal Platform Team",
    plugin_type="transformer",
    provides=["data_transformation", "format_conversion", "data_validation"],
    requires=["cpu"],
    tags=["transformer", "data", "json", "xml", "csv", "conversion"],
    max_memory_mb=150,
    max_cpu_percent=25.0,
    network_access=False,
    file_system_access=True
)
@config_schema({
    'supported_formats': {
        'type': list,
        'required': False,
        'default': ['json', 'xml', 'csv', 'yaml']
    },
    'max_input_size_mb': {'type': int, 'required': False, 'default': 10},
    'enable_validation': {'type': bool, 'required': False, 'default': True},
    'enable_caching': {'type': bool, 'required': False, 'default': True},
    'cache_ttl_seconds': {'type': int, 'required': False, 'default': 300},
    'transformation_timeout': {'type': int, 'required': False, 'default': 30},
    'custom_transformers': {'type': dict, 'required': False, 'default': {}},
    'validation_rules': {'type': dict, 'required': False, 'default': {}}
})
class DataTransformerPlugin(TransformerPlugin):
    """
    Data transformer plugin supporting multiple data formats and transformations.
    """
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self._supported_formats = set()
        self._custom_transformers = {}
        self._validation_rules = {}
        self._stats = {
            'transformations_total': 0,
            'transformations_failed': 0,
            'bytes_processed': 0,
            'last_transformation_time': None,
            'format_usage': {}
        }
    
    @lifecycle_hook(HookType.BEFORE_INIT)
    async def _prepare_transformers(self):
        """Prepare transformation modules before initialization."""
        self.logger.info("Preparing data transformation modules...")
    
    async def initialize(self, config: PluginConfig) -> None:
        """Initialize the data transformer plugin."""
        self.logger.info("Initializing data transformer plugin...")
        
        # Validate configuration
        if hasattr(self, 'validate_config'):
            self.validate_config(config)
        
        self._plugin_config = config
        
        # Initialize supported formats
        self._supported_formats = set(config.get('supported_formats', 
                                                ['json', 'xml', 'csv', 'yaml']))
        
        # Load custom transformers
        self._custom_transformers = config.get('custom_transformers', {})
        
        # Load validation rules
        self._validation_rules = config.get('validation_rules', {})
        
        # Initialize format usage statistics
        for fmt in self._supported_formats:
            self._stats['format_usage'][fmt] = 0
        
        self._is_initialized = True
        self.logger.info(f"Data transformer initialized with formats: {self._supported_formats}")
    
    @lifecycle_hook(HookType.AFTER_START)
    async def _post_start_checks(self):
        """Perform post-start validation checks."""
        self.logger.info("Running post-start validation checks...")
        
        # Test each supported format with sample data
        for fmt in self._supported_formats:
            try:
                await self._test_format_support(fmt)
            except Exception as e:
                self.logger.warning(f"Format {fmt} may have issues: {e}")
    
    async def start(self) -> None:
        """Start the data transformer."""
        self.logger.info("Starting data transformer...")
        
        self._is_started = True
        self.logger.info("Data transformer started successfully")
    
    async def stop(self) -> None:
        """Stop the data transformer."""
        self.logger.info("Stopping data transformer...")
        
        self._is_started = False
        self.logger.info("Data transformer stopped successfully")
    
    async def destroy(self) -> None:
        """Destroy the data transformer plugin."""
        self.logger.info("Destroying data transformer plugin...")
        
        # Clear transformers and rules
        self._custom_transformers.clear()
        self._validation_rules.clear()
        self._stats.clear()
        
        self._is_initialized = False
        self.logger.info("Data transformer plugin destroyed")
    
    @monitor_performance(include_args=False)
    @validate_input(
        input_data=lambda x: x is not None,
        transform_params=lambda x: x is None or isinstance(x, dict)
    )
    @timeout(30.0)
    @retry_on_failure(max_attempts=2, delay=1.0)
    async def transform(
        self,
        input_data: Any,
        transform_params: Dict[str, Any] = None
    ) -> Any:
        """
        Transform input data according to specified parameters.
        
        Args:
            input_data: Data to transform
            transform_params: Transformation parameters including 'from_format',
                            'to_format', 'options', etc.
            
        Returns:
            Transformed data
        """
        if not transform_params:
            raise ValueError("Transform parameters are required")
        
        from_format = transform_params.get('from_format', 'auto')
        to_format = transform_params.get('to_format')
        options = transform_params.get('options', {})
        
        if not to_format:
            raise ValueError("Target format ('to_format') is required")
        
        try:
            # Auto-detect input format if needed
            if from_format == 'auto':
                from_format = await self._detect_format(input_data)
            
            # Validate formats
            if from_format not in self._supported_formats:
                raise ValueError(f"Unsupported input format: {from_format}")
            
            if to_format not in self._supported_formats:
                raise ValueError(f"Unsupported output format: {to_format}")
            
            # Check input size
            input_size = len(str(input_data).encode('utf-8'))
            max_size = self._plugin_config.get('max_input_size_mb', 10) * 1024 * 1024
            
            if input_size > max_size:
                raise ValueError(f"Input data too large: {input_size} bytes > {max_size} bytes")
            
            # Validate input data if enabled
            if self._plugin_config.get('enable_validation', True):
                await self._validate_input_data(input_data, from_format)
            
            # Perform transformation
            transformed_data = await self._perform_transformation(
                input_data, from_format, to_format, options
            )
            
            # Update statistics
            self._stats['transformations_total'] += 1
            self._stats['bytes_processed'] += input_size
            self._stats['last_transformation_time'] = datetime.now().isoformat()
            self._stats['format_usage'][from_format] += 1
            
            self.logger.debug(f"Transformed data from {from_format} to {to_format}")
            
            return transformed_data
            
        except Exception as e:
            self._stats['transformations_failed'] += 1
            self.logger.error(f"Transformation failed: {e}")
            raise
    
    @validate_input(input_data=lambda x: x is not None)
    async def validate_input(self, input_data: Any) -> bool:
        """
        Validate input data before transformation.
        
        Args:
            input_data: Data to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            # Basic validation
            if input_data is None:
                return False
            
            # Size check
            input_size = len(str(input_data).encode('utf-8'))
            max_size = self._plugin_config.get('max_input_size_mb', 10) * 1024 * 1024
            
            if input_size > max_size:
                return False
            
            # Format detection
            detected_format = await self._detect_format(input_data)
            
            if detected_format not in self._supported_formats:
                return False
            
            # Format-specific validation
            return await self._validate_input_data(input_data, detected_format)
            
        except Exception as e:
            self.logger.error(f"Input validation failed: {e}")
            return False
    
    async def get_supported_formats(self) -> List[str]:
        """
        Get list of supported data formats.
        
        Returns:
            List of supported format names
        """
        return list(self._supported_formats)
    
    @cache_result(ttl=60.0)  # Cache for 1 minute
    async def get_transformation_options(self, from_format: str, to_format: str) -> Dict[str, Any]:
        """
        Get available transformation options for format pair.
        
        Args:
            from_format: Source format
            to_format: Target format
            
        Returns:
            Dictionary of available options
        """
        options = {
            'basic_options': {
                'preserve_types': True,
                'strict_mode': False,
                'encoding': 'utf-8'
            }
        }
        
        # Format-specific options
        if to_format == 'json':
            options['json_options'] = {
                'indent': 2,
                'sort_keys': False,
                'ensure_ascii': False
            }
        elif to_format == 'xml':
            options['xml_options'] = {
                'pretty_print': True,
                'root_element': 'data',
                'encoding': 'utf-8'
            }
        elif to_format == 'csv':
            options['csv_options'] = {
                'delimiter': ',',
                'quote_char': '"',
                'include_headers': True
            }
        
        return options
    
    async def health_check(self) -> PluginHealth:
        """Perform health check on the data transformer."""
        try:
            # Test basic transformation functionality
            test_data = {'test': 'data', 'timestamp': datetime.now().isoformat()}
            
            # Test JSON to XML transformation
            await self.transform(
                test_data,
                {'from_format': 'json', 'to_format': 'xml'}
            )
            
            # Calculate health score based on success rate
            total_transformations = (self._stats['transformations_total'] + 
                                   self._stats['transformations_failed'])
            
            if total_transformations == 0:
                success_rate = 1.0
            else:
                success_rate = self._stats['transformations_total'] / total_transformations
            
            health_score = min(1.0, success_rate)
            
            return PluginHealth(
                is_healthy=True,
                score=health_score,
                message="Data transformer is healthy",
                details={
                    'supported_formats': list(self._supported_formats),
                    'success_rate': success_rate,
                    'total_transformations': total_transformations,
                    'bytes_processed': self._stats['bytes_processed']
                }
            )
            
        except Exception as e:
            return PluginHealth(
                is_healthy=False,
                score=0.0,
                message=f"Health check failed: {e}",
                details={'error': str(e)}
            )
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get data transformer metrics."""
        total_transformations = (self._stats['transformations_total'] + 
                               self._stats['transformations_failed'])
        
        return {
            'transformations_total': self._stats['transformations_total'],
            'transformations_failed': self._stats['transformations_failed'],
            'success_rate': (self._stats['transformations_total'] / total_transformations 
                           if total_transformations > 0 else 1.0),
            'bytes_processed_total': self._stats['bytes_processed'],
            'average_bytes_per_transformation': (self._stats['bytes_processed'] / 
                                               self._stats['transformations_total']
                                               if self._stats['transformations_total'] > 0 else 0),
            'last_transformation_timestamp': self._stats['last_transformation_time'],
            'format_usage': self._stats['format_usage'].copy(),
            'supported_formats_count': len(self._supported_formats)
        }
    
    # Private helper methods
    
    async def _detect_format(self, data: Any) -> str:
        """Auto-detect data format."""
        if isinstance(data, dict) or isinstance(data, list):
            return 'json'
        
        if isinstance(data, str):
            data_stripped = data.strip()
            
            # Check for JSON
            if (data_stripped.startswith('{') and data_stripped.endswith('}')) or \
               (data_stripped.startswith('[') and data_stripped.endswith(']')):
                try:
                    json.loads(data)
                    return 'json'
                except:
                    pass
            
            # Check for XML
            if data_stripped.startswith('<') and data_stripped.endswith('>'):
                try:
                    ET.fromstring(data)
                    return 'xml'
                except:
                    pass
            
            # Check for CSV (simple heuristic)
            if ',' in data and '\n' in data:
                lines = data.split('\n')
                if len(lines) > 1 and len(lines[0].split(',')) > 1:
                    return 'csv'
            
            # Check for YAML (simple heuristic)
            if ':' in data and ('\n' in data or data.count(':') > 1):
                return 'yaml'
        
        return 'unknown'
    
    async def _validate_input_data(self, data: Any, format_name: str) -> bool:
        """Validate input data for specific format."""
        try:
            if format_name == 'json':
                if isinstance(data, (dict, list)):
                    return True
                elif isinstance(data, str):
                    json.loads(data)
                    return True
                else:
                    return False
            
            elif format_name == 'xml':
                if isinstance(data, str):
                    ET.fromstring(data)
                    return True
                else:
                    return False
            
            elif format_name == 'csv':
                if isinstance(data, str):
                    # Basic CSV validation
                    lines = data.strip().split('\n')
                    if len(lines) > 0:
                        header_cols = len(lines[0].split(','))
                        return all(len(line.split(',')) == header_cols for line in lines[:5])
                    return False
                else:
                    return False
            
            elif format_name == 'yaml':
                # Simplified YAML validation
                return isinstance(data, str) and ':' in data
            
            return True
            
        except Exception:
            return False
    
    async def _perform_transformation(
        self,
        data: Any,
        from_format: str,
        to_format: str,
        options: Dict[str, Any]
    ) -> Any:
        """Perform the actual data transformation."""
        
        # First, parse the input data into a common format (dict/list)
        parsed_data = await self._parse_data(data, from_format)
        
        # Then, serialize to the target format
        transformed_data = await self._serialize_data(parsed_data, to_format, options)
        
        return transformed_data
    
    async def _parse_data(self, data: Any, format_name: str) -> Any:
        """Parse data from specific format to common format."""
        if format_name == 'json':
            if isinstance(data, (dict, list)):
                return data
            else:
                return json.loads(data)
        
        elif format_name == 'xml':
            # Simple XML to dict conversion
            if isinstance(data, str):
                root = ET.fromstring(data)
                return self._xml_to_dict(root)
            else:
                raise ValueError("XML data must be string")
        
        elif format_name == 'csv':
            # Simple CSV to list of dicts conversion
            if isinstance(data, str):
                lines = data.strip().split('\n')
                if len(lines) < 2:
                    return []
                
                headers = [h.strip().strip('"') for h in lines[0].split(',')]
                result = []
                
                for line in lines[1:]:
                    values = [v.strip().strip('"') for v in line.split(',')]
                    if len(values) == len(headers):
                        result.append(dict(zip(headers, values)))
                
                return result
            else:
                raise ValueError("CSV data must be string")
        
        elif format_name == 'yaml':
            # Simplified YAML parsing
            if isinstance(data, str):
                # Very basic YAML-like parsing
                result = {}
                for line in data.strip().split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        result[key.strip()] = value.strip()
                return result
            else:
                raise ValueError("YAML data must be string")
        
        else:
            raise ValueError(f"Unsupported format: {format_name}")
    
    async def _serialize_data(self, data: Any, format_name: str, options: Dict[str, Any]) -> Any:
        """Serialize data to specific format."""
        if format_name == 'json':
            json_options = options.get('json_options', {})
            return json.dumps(data, 
                            indent=json_options.get('indent', 2),
                            sort_keys=json_options.get('sort_keys', False),
                            ensure_ascii=json_options.get('ensure_ascii', False))
        
        elif format_name == 'xml':
            xml_options = options.get('xml_options', {})
            root_name = xml_options.get('root_element', 'data')
            return self._dict_to_xml(data, root_name)
        
        elif format_name == 'csv':
            csv_options = options.get('csv_options', {})
            delimiter = csv_options.get('delimiter', ',')
            include_headers = csv_options.get('include_headers', True)
            
            if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
                headers = list(data[0].keys())
                result = []
                
                if include_headers:
                    result.append(delimiter.join(headers))
                
                for row in data:
                    values = [str(row.get(h, '')) for h in headers]
                    result.append(delimiter.join(values))
                
                return '\n'.join(result)
            else:
                raise ValueError("CSV format requires list of dictionaries")
        
        elif format_name == 'yaml':
            # Simple YAML-like serialization
            if isinstance(data, dict):
                result = []
                for key, value in data.items():
                    result.append(f"{key}: {value}")
                return '\n'.join(result)
            else:
                raise ValueError("YAML format requires dictionary")
        
        else:
            raise ValueError(f"Unsupported format: {format_name}")
    
    def _xml_to_dict(self, element) -> Dict[str, Any]:
        """Convert XML element to dictionary."""
        result = {}
        
        # Add attributes
        if element.attrib:
            result['@attributes'] = element.attrib
        
        # Add text content
        if element.text and element.text.strip():
            if len(element) == 0:
                return element.text.strip()
            else:
                result['#text'] = element.text.strip()
        
        # Add child elements
        for child in element:
            child_data = self._xml_to_dict(child)
            
            if child.tag in result:
                # Multiple children with same tag - convert to list
                if not isinstance(result[child.tag], list):
                    result[child.tag] = [result[child.tag]]
                result[child.tag].append(child_data)
            else:
                result[child.tag] = child_data
        
        return result
    
    def _dict_to_xml(self, data: Any, root_name: str = 'root') -> str:
        """Convert dictionary to XML string."""
        def build_element(name: str, value: Any) -> str:
            if isinstance(value, dict):
                content = ''
                for k, v in value.items():
                    if k.startswith('@'):
                        continue  # Skip attributes for now
                    content += build_element(k, v)
                return f"<{name}>{content}</{name}>"
            
            elif isinstance(value, list):
                content = ''
                for item in value:
                    content += build_element('item', item)
                return f"<{name}>{content}</{name}>"
            
            else:
                return f"<{name}>{str(value)}</{name}>"
        
        return f'<?xml version="1.0" encoding="utf-8"?>\n{build_element(root_name, data)}'
    
    async def _test_format_support(self, format_name: str) -> None:
        """Test format support with sample data."""
        test_data = {'test': True, 'format': format_name}
        
        # Test transformation to and from the format
        if format_name != 'json':
            # Transform JSON to target format
            transformed = await self.transform(
                test_data,
                {'from_format': 'json', 'to_format': format_name}
            )
            
            # Transform back to JSON
            await self.transform(
                transformed,
                {'from_format': format_name, 'to_format': 'json'}
            )