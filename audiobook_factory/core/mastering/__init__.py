#!/usr/bin/env python3
"""
Audiobook Factory - Broadcast Mastering & M4B Packaging Platform.
Standard: v6.0-ENTERPRISE-DAG
Provides Two-Pass Measured Linear EBU R128 (-19 LUFS) vocal mastering
and chaptered M4B container packaging.
"""

from .loudnorm import TwoPassLoudnormEngine, MasteringSpec
from .packager import M4BPackager, ChapterMetadata

__all__ = [
    "TwoPassLoudnormEngine",
    "MasteringSpec",
    "M4BPackager",
    "ChapterMetadata",
]
