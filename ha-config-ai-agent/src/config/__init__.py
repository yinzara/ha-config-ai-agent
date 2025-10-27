"""
Configuration Management Module - Phase 2

Provides safe configuration file operations with:
- Comment-preserving YAML parsing (ruamel.yaml)
- Atomic writes with automatic rollback
- Backup system with rotation
- Home Assistant validation integration
"""
from .manager import (
    ConfigurationManager,
    ConfigurationError,
    ValidationError
)

__all__ = [
    'ConfigurationManager',
    'ConfigurationError',
    'ValidationError'
]
