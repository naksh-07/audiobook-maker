#!/usr/bin/env python3
"""
Audiobook Factory - Core KeyManager Platform Service.
Standard: v6.0-ENTERPRISE-DAG
Provides 120+ SQLite round-robin key rotation, cool-down tracking, and token-bucket concurrency.
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional

from audiobook_factory.key_manager import (
    AllKeysExhaustedTodayError,
    PersistentKeyPool,
    get_persistent_key_pool,
    register_all_local_keys,
)

__all__ = [
    "PersistentKeyPool",
    "get_persistent_key_pool",
    "register_all_local_keys",
    "AllKeysExhaustedTodayError",
]
