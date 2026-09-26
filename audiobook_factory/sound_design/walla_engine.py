#!/usr/bin/env python3
"""
Audiobook Factory - Capability 06: Walla & Background Human Activity Engine.
=============================================================================
Manages crowd, patron, assembly, and communal background human activity.
- Contextual activity classification (murmur, bustle, whispers, panic, rally, chanting).
- Density, proximity, and emotional valence modeling.
- Dialogue subordination intent (always flags ducking under primary speech).
- Restraint & Suppression: Completely pruned in solitary, intimate, or isolated settings.
- Interfaces with AssetRetriever to ensure approved asset provenance.
"""

from __future__ import annotations
import re
from typing import Dict, Any, List, Optional
from pathlib import Path

from audiobook_factory.logger import logger
from audiobook_factory.sound_design.contracts import (
    WallaLayerSpec,
    WallaActivityType,
    ProximityZone,
    RelativeIntensity,
    MixIntent,
)
from audiobook_factory.sound_design.environment_profiles import get_environment_registry
from audiobook_factory.sound_design.asset_retriever import get_asset_retriever, AssetRetriever
from audiobook_factory.scene_acoustics import AmbienceLayer


# Explicit environments that strictly forbid human crowd walla by default
SOLITARY_ENVIRONMENTS = {
    "dark_forest",
    "crypt_subterranean",
    "cave_depths",
    "solitary_study",
    "private_bedroom",
    "abandoned_tower",
    "dungeon_cell",
    "ancient_ruins",
    "mountain_pass",
}

# Regex cues that indicate crowd presence in scene text
CROWD_TRIGGER_PATTERNS = [
    re.compile(r"\b(crowd|patrons|onlookers|courtiers|students|mob|throng|assembly|gathering|congregation|spectators|market\s+goers|troops)\b", re.IGNORECASE),
    re.compile(r"\b(murmurs?|chatter|whispers?\s+rippled|cheers?|gasped?\s+in\s+unison|applause|clamor|ruckus|bustle)\b", re.IGNORECASE),
    re.compile(r"\b(banquet|feast|celebrat\w*|servants|guests|brawlers?|brawl\w*|soldiers?|warriors?|lords?|ladies|patrons|rally|cheering)\b", re.IGNORECASE),
]


# Regex cues that indicate solitary, secret, or stealth context
SOLITARY_TRIGGER_PATTERNS = [
    re.compile(r"\b(alone|solitary|in\s+secret|empty\s+room|deserted|not\s+a\s+soul|silent\s+hall|isolated|hushed\s+solitude)\b", re.IGNORECASE),
]


class WallaEngine:
    """
    Contextual Walla (Crowd / Group Atmosphere) Generation Engine.
    """

    def __init__(self, asset_retriever: Optional[AssetRetriever] = None):
        self.retriever = asset_retriever or get_asset_retriever()
        self.env_registry = get_environment_registry()

    def should_suppress_walla(
        self,
        environment_id: str,
        character_count: int = 1,
        dramatic_beat: Optional[str] = None,
        scene_text: str = "",
        explicit_requires_flag: bool = False,
        sfx_cues: Optional[List[str]] = None,
    ) -> bool:
        """
        Determines whether background crowd activity should be suppressed.
        Enforces strict restraint: no gratuitous crowd audio in solitary,
        intimate, or isolated wilderness scenes.
        """
        if explicit_requires_flag:
            return False

        # 1. Check solitary environments
        normalized_env = environment_id.lower()
        for sol_env in SOLITARY_ENVIRONMENTS:
            if sol_env in normalized_env:
                return True

        # Combine text and sfx cues
        cues_joined = " ".join(str(c) for c in sfx_cues) if sfx_cues else ""
        corpus = f"{scene_text} {cues_joined}".strip()

        # 2. Check solitary text patterns
        if corpus:
            for pat in SOLITARY_TRIGGER_PATTERNS:
                if pat.search(corpus):
                    return True

        # 3. Low character count without explicit crowd triggers
        if character_count <= 2:
            has_crowd_mention = False
            if corpus:
                for pat in CROWD_TRIGGER_PATTERNS:
                    if pat.search(corpus):
                        has_crowd_mention = True
                        break
            if not has_crowd_mention:
                # Intimate or private two-person scene
                return True

        # 4. Check environment registry typical walla
        env_profile = self.env_registry.get_profile(environment_id)
        if env_profile and not env_profile.typical_walla:

            # Environment has no crowd profile by default (e.g. carriage interior, forest)
            has_explicit_crowd = any(pat.search(scene_text) for pat in CROWD_TRIGGER_PATTERNS) if scene_text else False
            if not has_explicit_crowd:
                return True

        return False

    def classify_activity_type(
        self,
        environment_id: str,
        scene_text: str = "",
        tension_level: float = 0.5,
        dominant_emotion: str = "neutral",
    ) -> WallaActivityType:
        """
        Determines appropriate WallaActivityType based on physical location and dramatic mood.
        """
        env_lower = environment_id.lower()
        text_lower = scene_text.lower() if scene_text else ""

        # High tension / panic takes precedence
        if tension_level > 0.8 or any(w in text_lower for w in ["scream", "fled", "stampede", "terror", "panic"]):
            return "crowd_panic"

        # Battle or martial rally
        if "battle" in env_lower or any(w in text_lower for w in ["charge", "rally", "swords", "soldiers", "regiment", "warriors"]):
            return "battle_rally"

        # Festival or cheering
        if any(w in text_lower for w in ["cheer", "applause", "roared with joy", "celebrat", "toast", "festival"]):
            return "festival_cheering"

        # Temple or sacred place
        if "temple" in env_lower or "sanctuary" in env_lower or "chant" in text_lower:
            return "temple_chanting"

        # Market or street bustle
        if "market" in env_lower or "street" in env_lower or "bazaar" in env_lower or "square" in env_lower:
            return "market_bustle"

        # Classroom or library study
        if "classroom" in env_lower or "library" in env_lower or "lecture" in text_lower:
            return "classroom_mutter"

        # Court or formal hall
        if "great_hall" in env_lower or "court" in env_lower or "throne" in env_lower:
            if tension_level > 0.6 or "gasp" in text_lower or "whisper" in text_lower:
                return "whispers_and_gasps"
            return "court_whispers"

        # Tavern, inn, pub
        if "tavern" in env_lower or "inn" in env_lower or "common_room" in env_lower or "pub" in env_lower:
            if "quiet" in text_lower or "sparse" in text_lower:
                return "sparse_patrons"
            return "tavern_murmur"

        # Default fallback
        if tension_level > 0.6:
            return "whispers_and_gasps"
        return "tavern_murmur"

    def build_scene_walla(
        self,
        scene_id: str,
        environment_id: str,
        characters_present: Optional[List[str]] = None,
        scene_text: str = "",
        tension_level: float = 0.5,
        dominant_emotion: str = "neutral",
        requires_walla: bool = False,
        walla_description: Optional[str] = None,
        sfx_cues: Optional[List[str]] = None,
    ) -> Optional[WallaLayerSpec]:
        """
        Generates contextual WallaLayerSpec for a scene, or returns None if suppressed.
        """
        chars = characters_present or []
        char_count = len(chars)

        if self.should_suppress_walla(
            environment_id=environment_id,
            character_count=char_count,
            scene_text=scene_text,
            explicit_requires_flag=requires_walla,
            sfx_cues=sfx_cues,
        ):
            logger.debug(
                f"[WallaEngine] Walla suppressed for scene '{scene_id}' in env '{environment_id}' (restraint enforced)."
            )
            return None

        # Determine activity
        activity_type = self.classify_activity_type(
            environment_id=environment_id,
            scene_text=scene_text,
            tension_level=tension_level,
            dominant_emotion=dominant_emotion,
        )

        # Determine density
        if activity_type in ("crowd_panic", "battle_rally", "festival_cheering"):
            density = "dense" if tension_level < 0.85 else "packed"
        elif activity_type in ("sparse_patrons", "classroom_mutter"):
            density = "sparse"
        elif tension_level > 0.7:
            density = "dense"
        else:
            density = "moderate"

        # Determine distance & intensity (Dialogue subordination)
        distance: ProximityZone = "mid_distance"
        rel_intensity: RelativeIntensity = "subtle_bed"

        if activity_type == "sparse_patrons":
            distance = "distant"
            rel_intensity = "whisper_quiet"
        elif activity_type in ("court_whispers", "classroom_mutter"):
            distance = "mid_distance"
            rel_intensity = "whisper_quiet"
        elif activity_type in ("crowd_panic", "battle_rally"):
            distance = "close" if tension_level > 0.85 else "mid_distance"
            rel_intensity = "prominent"


        # Retrieve asset via AssetRetriever
        query_kw = walla_description or activity_type.replace("_", " ")
        asset_desc = self.retriever.resolve_ambience_asset(f"crowd {query_kw}", tier="MIDGROUND")
        asset_path = asset_desc.filepath if asset_desc else f"ambience_walla_{activity_type}.wav"

        walla_spec = WallaLayerSpec(
            activity_type=activity_type,
            density=density,
            distance=distance,
            emotion=dominant_emotion,
            relative_intensity=rel_intensity,
            asset_path=asset_path,
            mix_intent=MixIntent(
                duck_under_dialogue=True,
                swell_in_dialogue_pauses=True,
            ),
        )

        logger.debug(
            f"[WallaEngine] Planned walla for scene '{scene_id}': type={activity_type}, density={density}, intensity={rel_intensity}"
        )
        return walla_spec

    def to_legacy_ambience_layer(self, walla_spec: WallaLayerSpec) -> AmbienceLayer:
        """
        Converts WallaLayerSpec into standard AmbienceLayer (layer_type='crowd_wallah')
        for full backward compatibility with SceneAcousticProfile and AgentDirector.
        """
        lufs = -32.0
        if walla_spec.relative_intensity == "whisper_quiet":
            lufs = -38.0
        elif walla_spec.relative_intensity == "prominent":
            lufs = -26.0

        return AmbienceLayer(
            layer_type="crowd_wallah",
            asset_path=walla_spec.asset_path or "crowd_wallah.wav",
            target_lufs=lufs,
            stereo_width=1.45,
            loop=True,
        )


_GLOBAL_WALLA_ENGINE: Optional[WallaEngine] = None

def get_walla_engine() -> WallaEngine:
    """Returns singleton instance of WallaEngine."""
    global _GLOBAL_WALLA_ENGINE
    if _GLOBAL_WALLA_ENGINE is None:
        _GLOBAL_WALLA_ENGINE = WallaEngine()
    return _GLOBAL_WALLA_ENGINE
