#!/usr/bin/env python3
"""
Audiobook Factory - Room 1: Pre-Production & World Lore Studio.
One-time master ingestion room producing locked novel master state:
- book_bible.json (Characters, Lore, Terminology, Relationships)
- sonic_bible.json (World Acoustic DNA, Room Impulse Reverbs, Foley Palettes)
- cast_lock.json (Collision-free Voice Allocations)
"""

from .book_dna_agent import BookDNAAgent
from .dramatis_personae_agent import DramatisPersonaeAgent
from .sonic_world_architect import SonicWorldArchitect
from .phonetic_lexicon_dramaturge import PhoneticLexiconDramaturge
from .novel_deepsearch import NovelDeepSearchEngine, DeepSearchNovelDossier
from .preproduction_supervisor import PreProductionSupervisor, run_preproduction

__all__ = [
    "NovelDeepSearchEngine",
    "DeepSearchNovelDossier",
    "BookDNAAgent",
    "DramatisPersonaeAgent",
    "SonicWorldArchitect",
    "PhoneticLexiconDramaturge",
    "PreProductionSupervisor",
    "run_preproduction",
]
