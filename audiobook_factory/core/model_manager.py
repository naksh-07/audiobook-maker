#!/usr/bin/env python3
"""
Audiobook Factory - Core ModelManager Platform Service.
Standard: v6.0-ENTERPRISE-DAG
Provides Tier-1 Flagship model routing, capability floor enforcement,
and BLOCK_NONE permissive safety configuration for uncompromised literary fidelity.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional

from audiobook_factory.model_manager import (
    ModelManager,
    ModelTier,
    TaskType,
    TASK_MINIMUM_TIERS,
    get_model_manager,
)


def get_permissive_safety_settings() -> List[Dict[str, str]]:
    """
    Returns standard BLOCK_NONE safety settings for Google Gemini API
    to prevent false-positive truncation of visceral literary fiction.
    """
    return [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    ]


__all__ = [
    "ModelManager",
    "ModelTier",
    "TaskType",
    "TASK_MINIMUM_TIERS",
    "get_model_manager",
    "get_permissive_safety_settings",
]
