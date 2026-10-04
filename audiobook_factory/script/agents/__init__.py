#!/usr/bin/env python3
"""
Audiobook Factory - Room 3: Screenplay Dramaturgy & Spatial Staging Agents.
Deconstructs screenplay generation into 4 collaborative specialists:
1. DialogueTurnIsolator: Attributed speaker and line extraction.
2. StanislavskiSubtextDirector: Transitive actioning verbs, psychological subtext & intensity.
3. PhysicalBlockingDirector: Actor spatial blocking, movement & azimuth panning.
4. DramaturgyConsistencyJudge: Dialogue integrity, speaker continuity & spatial smoothness audit.
"""

from .dialogue_isolator import DialogueTurnIsolator
from .stanislavski_director import StanislavskiSubtextDirector
from .physical_blocking_director import PhysicalBlockingDirector
from .dramaturgy_judge import DramaturgyConsistencyJudge
from .script_room import ScreenplayDramaturgyRoom, get_screenplay_room

__all__ = [
    "DialogueTurnIsolator",
    "StanislavskiSubtextDirector",
    "PhysicalBlockingDirector",
    "DramaturgyConsistencyJudge",
    "ScreenplayDramaturgyRoom",
    "get_screenplay_room",
]
