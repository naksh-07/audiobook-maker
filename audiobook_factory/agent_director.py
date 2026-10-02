#!/usr/bin/env python3
"""
Agentic Creative Layer: Autonomous & Interactive Audio Drama Director Facade.
Maintains 100% backward compatibility by re-exporting modular components from audiobook_factory.director.
"""

from __future__ import annotations

from audiobook_factory.director import (
    AgentDirector,
    DramaturgyMixin,
    MusicDirectorMixin,
    FoleyDirectorMixin,
    SceneAcousticsMixin,
)

# Re-export commonly co-imported symbols for backward compatibility
from audiobook_factory.contracts import (
    CreativeManifest,
    MusicCue,
    FoleyCue,
    AmbienceScene,
    MasteringConfig,
    ManifestValidationError,
    TimelineLedger,
)

from audiobook_factory.key_manager import get_persistent_key_pool

__all__ = [
    "AgentDirector",
    "DramaturgyMixin",
    "MusicDirectorMixin",
    "FoleyDirectorMixin",
    "SceneAcousticsMixin",
    "CreativeManifest",
    "MusicCue",
    "FoleyCue",
    "AmbienceScene",
    "MasteringConfig",
    "ManifestValidationError",
    "TimelineLedger",
    "get_persistent_key_pool",
]
