"""
Persistence Module

Phase XVII-B: Unified persistence layer supporting multiple backends.
"""

from .base import PersistenceBackend
from .json_fallback import JSONBackend
from .sqlite import SQLiteBackend

__all__ = ["PersistenceBackend", "SQLiteBackend", "JSONBackend"]
