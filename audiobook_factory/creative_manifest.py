"""
Creative Manifest Schema & Contract
====================================
Re-exports the Layer 1 / Layer 2 Pydantic v2 contracts from audiobook_factory.contracts
for backward-compatibility.
"""

from audiobook_factory.contracts import (
    ManifestValidationError,
    MasteringConfig,
    MusicCue,
    FoleyCue,
    AmbienceScene,
    CreativeManifest,
)

__all__ = [
    "ManifestValidationError",
    "MasteringConfig",
    "MusicCue",
    "FoleyCue",
    "AmbienceScene",
    "CreativeManifest",
]
