"""
Virtual Catalog Module - Sonic Intelligence Catalog & JIT Sound Bank.
====================================================================
Adapters and utilities for indexing open-source sound libraries (Incompetech,
BBC Sound Effects, Sonniss GDC Archives, Kenney CC0 / OpenGameArt) as lightweight,
metadata-only virtual assets with Just-In-Time on-demand audio streaming.
"""

from audiobook_factory.virtual_catalog.base_adapter import BaseSourceAdapter
from audiobook_factory.virtual_catalog.incompetech_adapter import IncompetechAdapter
from audiobook_factory.virtual_catalog.bbc_sfx_adapter import BBCSoundEffectsAdapter
from audiobook_factory.virtual_catalog.sonniss_gdc_adapter import SonnissGDCAdapter
from audiobook_factory.virtual_catalog.kenney_oga_adapter import KenneyOGAAdapter
from audiobook_factory.virtual_catalog.seed_generator import (
    generate_seed_file,
    hydrate_from_seed,
    SEED_FILE_PATH,
)

__all__ = [
    "BaseSourceAdapter",
    "IncompetechAdapter",
    "BBCSoundEffectsAdapter",
    "SonnissGDCAdapter",
    "KenneyOGAAdapter",
    "generate_seed_file",
    "hydrate_from_seed",
    "SEED_FILE_PATH",
]
