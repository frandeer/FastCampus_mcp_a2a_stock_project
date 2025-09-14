"""
Configuration schema definition and validation with JSON Schema support.
"""

import json
import jsonschema
from jsonschema import validate, ValidationError, Draft7Validator
from typing import Dict, Any, Optional, List, Union, Type, get_type_hints
from dataclasses import dataclass, field, fields
from enum import Enum
import re
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""
    
    def __init__(self, message: str, errors: List[str] = None):
        super().__init__(message)
        self.errors = errors or []


class SchemaType(Enum):
    """Supported schema types."""
    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"
    NULL = "null"


@dataclass
class ValidationRule:
    """Configuration validation rule."""
    name: str
    description: str
    validator: callable
    error_message: str
    severity: str = "error"  # error, warning, info


@dataclass
class SchemaField:
    """Configuration schema field definition."""
    name: str
    type: SchemaType
    description: str = ""
    required: bool = False
    default: Any = None
    enum: Optional[List[Any]] = None
    pattern: Optional[str] = None
    minimum: Optional[Union[int, float]] = None
    maximum: Optional[Union[int, float]] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    items: Optional['SchemaField'] = None
    properties: Optional[Dict[str, 'SchemaField']] = None
    additional_properties: bool = True
    format: Optional[str] = None
    custom_rules: List[ValidationRule] = field(default_factory=list)
    
    def to_json_schema(self) -> Dict[str, Any]:
        """Convert to JSON Schema format."""
        schema = {"type": self.type.value}
        
        if self.description:
            schema["description"] = self.description
            
        if self.default is not None:
            schema["default"] = self.default
            
        if self.enum:
            schema["enum"] = self.enum
            
        if self.pattern:
            schema["pattern"] = self.pattern
            
        if self.format:
            schema["format"] = self.format
            
        if self.minimum is not None:
            schema["minimum"] = self.minimum
            
        if self.maximum is not None:
            schema["maximum"] = self.maximum
            
        if self.min_length is not None:
            schema["minLength"] = self.min_length
            
        if self.max_length is not None:
            schema["maxLength"] = self.max_length
            
        if self.type == SchemaType.ARRAY and self.items:
            schema["items"] = self.items.to_json_schema()
            
        if self.type == SchemaType.OBJECT and self.properties:
            schema["properties"] = {
                name: field.to_json_schema() 
                for name, field in self.properties.items()
            }
            schema["additionalProperties"] = self.additional_properties
            
        return schema


class ConfigSchema:
    """Configuration schema definition and validation."""
    
    def __init__(self, name: str, version: str = "1.0.0"):
        self.name = name
        self.version = version
        self.fields: Dict[str, SchemaField] = {}
        self.global_rules: List[ValidationRule] = []
        self._json_schema: Optional[Dict[str, Any]] = None
        self._validator: Optional[Draft7Validator] = None
        
    def add_field(self, field: SchemaField) -> 'ConfigSchema':
        """Add a field to the schema."""
        self.fields[field.name] = field
        self._invalidate_cache()
        return self
        
    def add_global_rule(self, rule: ValidationRule) -> 'ConfigSchema':
        """Add a global validation rule."""
        self.global_rules.append(rule)
        return self
        
    def _invalidate_cache(self):
        """Invalidate cached schema and validator."""
        self._json_schema = None
        self._validator = None
        
    def to_json_schema(self) -> Dict[str, Any]:
        """Convert to JSON Schema format."""
        if self._json_schema is None:
            self._json_schema = {
                "$schema": "http://json-schema.org/draft-07/schema#",
                "title": self.name,
                "version": self.version,
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": True
            }
            
            for name, field in self.fields.items():
                self._json_schema["properties"][name] = field.to_json_schema()
                if field.required:
                    self._json_schema["required"].append(name)
                    
        return self._json_schema
        
    def get_validator(self) -> Draft7Validator:
        """Get JSON Schema validator."""
        if self._validator is None:
            schema = self.to_json_schema()
            self._validator = Draft7Validator(schema)
        return self._validator
        
    def validate(self, config: Dict[str, Any], strict: bool = True) -> ValidationResult:
        """Validate configuration against schema."""
        result = ValidationResult()
        
        # JSON Schema validation
        validator = self.get_validator()
        errors = list(validator.iter_errors(config))
        
        for error in errors:
            result.add_error(
                path=".".join(str(p) for p in error.absolute_path),
                message=error.message,
                value=error.instance if hasattr(error, 'instance') else None
            )
            
        # Custom field validation
        for field_name, field in self.fields.items():
            if field_name in config:
                field_result = self._validate_field(field, config[field_name], field_name)
                result.merge(field_result)
                
        # Global validation rules
        for rule in self.global_rules:
            try:
                if not rule.validator(config):
                    result.add_error(
                        path="",
                        message=rule.error_message,
                        rule=rule.name
                    )
            except Exception as e:
                result.add_error(
                    path="",
                    message=f"Validation rule '{rule.name}' failed: {e}",
                    rule=rule.name
                )
                
        # Strict mode: fail on unknown fields
        if strict:
            known_fields = set(self.fields.keys())
            config_fields = set(config.keys())
            unknown_fields = config_fields - known_fields
            
            for unknown_field in unknown_fields:
                result.add_warning(
                    path=unknown_field,
                    message=f"Unknown configuration field: {unknown_field}"
                )
                
        return result
        
    def _validate_field(self, field: SchemaField, value: Any, path: str) -> 'ValidationResult':
        """Validate a single field."""
        result = ValidationResult()
        
        # Custom field rules
        for rule in field.custom_rules:
            try:
                if not rule.validator(value):
                    if rule.severity == "error":
                        result.add_error(
                            path=path,
                            message=rule.error_message,
                            rule=rule.name,
                            value=value
                        )
                    elif rule.severity == "warning":
                        result.add_warning(
                            path=path,
                            message=rule.error_message,
                            rule=rule.name
                        )
            except Exception as e:
                result.add_error(
                    path=path,
                    message=f"Custom rule '{rule.name}' failed: {e}",
                    rule=rule.name,
                    value=value
                )
                
        return result
        
    def apply_defaults(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply default values to configuration."""
        result = config.copy()
        
        for name, field in self.fields.items():
            if name not in result and field.default is not None:
                result[name] = field.default
                
        return result
        
    def get_field_info(self, field_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific field."""
        if field_name not in self.fields:
            return None
            
        field = self.fields[field_name]
        return {
            "name": field.name,
            "type": field.type.value,
            "description": field.description,
            "required": field.required,
            "default": field.default,
            "constraints": {
                "enum": field.enum,
                "pattern": field.pattern,
                "minimum": field.minimum,
                "maximum": field.maximum,
                "min_length": field.min_length,
                "max_length": field.max_length,
                "format": field.format
            },
            "custom_rules": [
                {
                    "name": rule.name,
                    "description": rule.description,
                    "severity": rule.severity
                }
                for rule in field.custom_rules
            ]
        }


@dataclass
class ValidationError:
    """Validation error details."""
    path: str
    message: str
    value: Any = None
    rule: Optional[str] = None
    severity: str = "error"


class ValidationResult:
    """Result of configuration validation."""
    
    def __init__(self):
        self.errors: List[ValidationError] = []
        self.warnings: List[ValidationError] = []
        
    def is_valid(self) -> bool:
        """Check if validation passed."""
        return len(self.errors) == 0
        
    def add_error(self, path: str, message: str, value: Any = None, rule: str = None):
        """Add validation error."""
        self.errors.append(ValidationError(
            path=path,
            message=message,
            value=value,
            rule=rule,
            severity="error"
        ))
        
    def add_warning(self, path: str, message: str, value: Any = None, rule: str = None):
        """Add validation warning."""
        self.warnings.append(ValidationError(
            path=path,
            message=message,
            value=value,
            rule=rule,
            severity="warning"
        ))
        
    def merge(self, other: 'ValidationResult'):
        """Merge another validation result."""
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "valid": self.is_valid(),
            "errors": [
                {
                    "path": error.path,
                    "message": error.message,
                    "value": error.value,
                    "rule": error.rule,
                    "severity": error.severity
                }
                for error in self.errors
            ],
            "warnings": [
                {
                    "path": warning.path,
                    "message": warning.message,
                    "value": warning.value,
                    "rule": warning.rule,
                    "severity": warning.severity
                }
                for warning in self.warnings
            ]
        }
        
    def __str__(self) -> str:
        """String representation of validation result."""
        if self.is_valid():
            if self.warnings:
                return f"Valid with {len(self.warnings)} warnings"
            return "Valid"
            
        return f"Invalid: {len(self.errors)} errors, {len(self.warnings)} warnings"


class SchemaBuilder:
    """Fluent interface for building configuration schemas."""
    
    def __init__(self, name: str, version: str = "1.0.0"):
        self.schema = ConfigSchema(name, version)
        
    def string_field(self, name: str, description: str = "", required: bool = False,
                    default: str = None, pattern: str = None, min_length: int = None,
                    max_length: int = None, enum: List[str] = None,
                    format: str = None) -> 'SchemaBuilder':
        """Add a string field."""
        field = SchemaField(
            name=name,
            type=SchemaType.STRING,
            description=description,
            required=required,
            default=default,
            pattern=pattern,
            min_length=min_length,
            max_length=max_length,
            enum=enum,
            format=format
        )
        self.schema.add_field(field)
        return self
        
    def integer_field(self, name: str, description: str = "", required: bool = False,
                     default: int = None, minimum: int = None, maximum: int = None,
                     enum: List[int] = None) -> 'SchemaBuilder':
        """Add an integer field."""
        field = SchemaField(
            name=name,
            type=SchemaType.INTEGER,
            description=description,
            required=required,
            default=default,
            minimum=minimum,
            maximum=maximum,
            enum=enum
        )
        self.schema.add_field(field)
        return self
        
    def number_field(self, name: str, description: str = "", required: bool = False,
                    default: Union[int, float] = None, minimum: Union[int, float] = None,
                    maximum: Union[int, float] = None) -> 'SchemaBuilder':
        """Add a number field."""
        field = SchemaField(
            name=name,
            type=SchemaType.NUMBER,
            description=description,
            required=required,
            default=default,
            minimum=minimum,
            maximum=maximum
        )
        self.schema.add_field(field)
        return self
        
    def boolean_field(self, name: str, description: str = "", required: bool = False,
                     default: bool = None) -> 'SchemaBuilder':
        """Add a boolean field."""
        field = SchemaField(
            name=name,
            type=SchemaType.BOOLEAN,
            description=description,
            required=required,
            default=default
        )
        self.schema.add_field(field)
        return self
        
    def array_field(self, name: str, items: SchemaField, description: str = "",
                   required: bool = False, default: List[Any] = None) -> 'SchemaBuilder':
        """Add an array field."""
        field = SchemaField(
            name=name,
            type=SchemaType.ARRAY,
            description=description,
            required=required,
            default=default,
            items=items
        )
        self.schema.add_field(field)
        return self
        
    def object_field(self, name: str, properties: Dict[str, SchemaField],
                    description: str = "", required: bool = False,
                    default: Dict[str, Any] = None,
                    additional_properties: bool = True) -> 'SchemaBuilder':
        """Add an object field."""
        field = SchemaField(
            name=name,
            type=SchemaType.OBJECT,
            description=description,
            required=required,
            default=default,
            properties=properties,
            additional_properties=additional_properties
        )
        self.schema.add_field(field)
        return self
        
    def custom_rule(self, rule: ValidationRule) -> 'SchemaBuilder':
        """Add a custom validation rule."""
        self.schema.add_global_rule(rule)
        return self
        
    def build(self) -> ConfigSchema:
        """Build the configuration schema."""
        return self.schema


# Built-in validation rules
class BuiltinRules:
    """Built-in validation rules."""
    
    @staticmethod
    def url_format(value: str) -> bool:
        """Validate URL format."""
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        return bool(url_pattern.match(value))
        
    @staticmethod
    def email_format(value: str) -> bool:
        """Validate email format."""
        email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
        return bool(email_pattern.match(value))
        
    @staticmethod
    def positive_number(value: Union[int, float]) -> bool:
        """Validate positive number."""
        return isinstance(value, (int, float)) and value > 0
        
    @staticmethod
    def non_negative_number(value: Union[int, float]) -> bool:
        """Validate non-negative number."""
        return isinstance(value, (int, float)) and value >= 0
        
    @staticmethod
    def port_number(value: int) -> bool:
        """Validate port number."""
        return isinstance(value, int) and 1 <= value <= 65535
        
    @staticmethod
    def directory_exists(value: str) -> bool:
        """Validate directory exists."""
        from pathlib import Path
        return Path(value).is_dir()
        
    @staticmethod
    def file_exists(value: str) -> bool:
        """Validate file exists."""
        from pathlib import Path
        return Path(value).is_file()


# Common schema templates
def create_database_schema() -> ConfigSchema:
    """Create a database configuration schema."""
    return (SchemaBuilder("database")
            .string_field("host", "Database host", required=True, default="localhost")
            .integer_field("port", "Database port", required=True, default=5432,
                          minimum=1, maximum=65535)
            .string_field("database", "Database name", required=True)
            .string_field("username", "Database username", required=True)
            .string_field("password", "Database password", required=True)
            .boolean_field("ssl", "Use SSL connection", default=False)
            .integer_field("pool_size", "Connection pool size", default=10,
                          minimum=1, maximum=100)
            .integer_field("timeout", "Connection timeout in seconds", default=30,
                          minimum=1, maximum=300)
            .build())


def create_server_schema() -> ConfigSchema:
    """Create a server configuration schema."""
    return (SchemaBuilder("server")
            .string_field("host", "Server host", default="0.0.0.0")
            .integer_field("port", "Server port", required=True, default=8000,
                          minimum=1, maximum=65535)
            .boolean_field("debug", "Debug mode", default=False)
            .string_field("log_level", "Log level", default="INFO",
                         enum=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
            .integer_field("workers", "Number of workers", default=1, minimum=1)
            .boolean_field("reload", "Auto reload on changes", default=False)
            .build())


def create_logging_schema() -> ConfigSchema:
    """Create a logging configuration schema."""
    return (SchemaBuilder("logging")
            .string_field("level", "Log level", default="INFO",
                         enum=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
            .string_field("format", "Log format", 
                         default="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            .string_field("file", "Log file path")
            .integer_field("max_size", "Max log file size in MB", default=10, minimum=1)
            .integer_field("backup_count", "Number of backup files", default=5, minimum=0)
            .boolean_field("console", "Log to console", default=True)
            .build())