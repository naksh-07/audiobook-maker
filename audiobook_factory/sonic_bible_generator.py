#!/usr/bin/env python3
"""
Audiobook Factory - Stage 0.6: Automated Sonic Bible Generator.
=============================================================================
Synthesizes an authoritative, project-level `sound_bible.json` by matching book
characters, narrative world environments, and franchise catalog assets with zero
hardcoded manual intervention.
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

from audiobook_factory.logger import logger
from audiobook_factory.sound_bank import SoundBank, get_sound_bank
from audiobook_factory.sonic_bible import (
    SonicBible,
    LeitmotifDefinition,
    WorldAcousticProfile,
    GlobalLoudnessPolicy,
)
from audiobook_factory.project_classifier import ProjectClassifier, ProjectClassification
from audiobook_factory.sound_design.environment_profiles import get_environment_registry


class SonicBibleGenerator:
    """Automated compiler that constructs a production-ready Sonic Bible for any novel."""

    @classmethod
    def generate_for_project(
        cls,
        project_dir: Path,
        sound_bank: Optional[SoundBank] = None,
        force_rebuild: bool = False,
    ) -> SonicBible:
        pdir = Path(project_dir).resolve()
        target_path = pdir / "sound_bible.json"
        alt_path = pdir / "sonic_bible.json"

        # Return existing bible if present and not force rebuilding
        if not force_rebuild:
            for p in (target_path, alt_path):
                if p.exists():
                    try:
                        return SonicBible.load_from_disk(p)
                    except Exception:
                        pass

        sb = sound_bank or get_sound_bank()
        classification = ProjectClassifier.classify(project_dir=pdir)

        # 1. Read metadata & book bible
        meta_data: Dict[str, Any] = {}
        meta_file = pdir / "metadata.json"
        if meta_file.exists():
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    meta_data = json.load(f)
            except Exception:
                pass

        book_title = meta_data.get("title") or pdir.name.replace("_", " ").title()
        project_id = meta_data.get("book_id") or pdir.name

        book_bible_data: Dict[str, Any] = {}
        bb_file = pdir / "book_bible.json"
        if bb_file.exists():
            try:
                with open(bb_file, "r", encoding="utf-8") as f:
                    book_bible_data = json.load(f)
            except Exception:
                pass

        sonic_bible = SonicBible(
            bible_version="2.0",
            book_title=book_title,
            project_id=project_id,
            loudness_policy=GlobalLoudnessPolicy(
                target_lufs=-19.0,
                true_peak_dbtp=-1.5,
                loudness_range_lra_max=8.5,
                min_dialogue_to_music_ratio_db=14.0,
                min_phase_correlation=0.20,
            ),
            metadata={
                "era": classification.era,
                "genre": classification.genre,
                "franchise_affinity": classification.franchise_affinity,
                "dramatic_theme": classification.dramatic_theme,
            },
        )

        # 2. Register Canonical World Acoustic Spaces
        env_reg = get_environment_registry()
        # Ensure key environments for the era are registered
        spaces_to_register = [
            "room_tone",
            classification.primary_acoustic_env,
        ]
        if classification.era == "MEDIEVAL_FANTASY":
            spaces_to_register.extend([
                "stone_ruins_exterior",
                "tavern_interior",
                "castle_great_hall",
                "castle_stone_corridor",
                "deep_forest_night",
                "crypt_catacomb",
                "mountain_pass_blizzard",
                "city_market_square",
            ])
        elif classification.era in ("SPACE_OPERA_SCIFI", "RETRO_FUTURE_CYBERPUNK"):
            spaces_to_register.extend([
                "spaceship_bridge",
                "cyberpunk_alley_rain",
                "office_commercial",
            ])
        else:
            spaces_to_register.extend([
                "domestic_room",
                "office_commercial",
                "suburban_street_day",
                "suburban_street_night",
            ])

        for env_id in set(spaces_to_register):
            try:
                w_prof = env_reg.to_world_acoustic_profile(env_id)
                sonic_bible.register_space(w_prof)
            except Exception as e:
                logger.debug(f"Could not register space {env_id}: {e}")

        # 3. Discover and Bind Leitmotifs for Characters and Themes
        characters = book_bible_data.get("characters", {})
        if not characters:
            # If no character registry, discover common entity mentions
            characters = {"Protagonist": {"category": "character"}, "Tension": {"category": "philosophical_theme"}}

        franchise = classification.franchise_affinity

        # Discover top music tracks in sound bank for this franchise/genre
        for char_name, c_info in list(characters.items())[:8]:
            c_name_clean = char_name.strip()
            if not c_name_clean:
                continue

            query = f"{c_name_clean} theme"
            results = sb.search(
                query=c_name_clean,
                category="music",
                limit=3,
                franchise_affinity=franchise,
                era=classification.era,
            )
            if not results:
                results = sb.search_music_catalog(
                    query=c_name_clean,
                    limit=3,
                    franchise_affinity=franchise,
                )
            if not results:
                # Fallback to genre query
                results = sb.search_music_catalog(
                    query=f"{classification.genre} tension",
                    limit=3,
                    franchise_affinity=franchise,
                )

            if results:
                top_track = results[0]
                t_name = top_track.get("filename") or top_track.get("title") or "Thematic Underscore"
                t_id = top_track.get("id", 1)
                slug = c_name_clean.lower().replace(" ", "_")

                motif = LeitmotifDefinition(
                    motif_id=f"lm_{slug}",
                    entity_type="character" if c_info.get("category") == "character" else "philosophical_theme",
                    associated_entity=c_name_clean,
                    track_id=str(t_id),
                    track_name=t_name,
                    primary_instrument="solo cello / slavic folk" if classification.era == "MEDIEVAL_FANTASY" else "dark strings / orchestra",
                    canonical_tempo_bpm=85,
                    dramatic_intent=f"Thematic leitmotif for {c_name_clean} in {classification.dramatic_theme}",
                    priority_level=8 if "geralt" in slug or "protagonist" in slug else 5,
                    default_section_start_sec=0.0,
                )
                sonic_bible.register_leitmotif(motif)

        # Ensure general narrative leitmotifs exist
        generic_themes = [
            ("Tension", "tension", "RISING_TENSION"),
            ("Mystery", "mystery", "INTRO_BED"),
            ("Combat", "combat battle duel", "CLIMAX_DROP"),
            ("Journey", "trail journey road", "INTRO_BED"),
        ]
        for theme_name, query_str, energy in generic_themes:
            slug = theme_name.lower()
            if slug not in sonic_bible.leitmotifs:
                res = sb.search_music_catalog(query_str, section_type=energy, limit=2, franchise_affinity=franchise)
                if not res:
                    res = sb.search(query_str, category="music", limit=2, franchise_affinity=franchise)
                if res:
                    top_t = res[0]
                    motif = LeitmotifDefinition(
                        motif_id=f"lm_{slug}",
                        entity_type="philosophical_theme",
                        associated_entity=theme_name,
                        track_id=str(top_t.get("id", 1)),
                        track_name=top_t.get("filename", theme_name),
                        primary_instrument="orchestral strings / ethnic woodwinds",
                        canonical_tempo_bpm=95,
                        dramatic_intent=f"Narrative cue for {theme_name} dramatic turns",
                        priority_level=6,
                        default_section_start_sec=float(top_t.get("start_sec", 0.0) or 0.0),
                    )
                    sonic_bible.register_leitmotif(motif)

        # 4. Save to disk (both sound_bible.json and sonic_bible.json)
        sonic_bible.save_to_disk(target_path)
        sonic_bible.save_to_disk(alt_path)

        logger.info(
            f"[+] SonicBibleGenerator: Successfully compiled Sonic Bible for '{book_title}' -> "
            f"{len(sonic_bible.leitmotifs)} leitmotifs, {len(sonic_bible.acoustic_spaces)} acoustic spaces."
        )
        return sonic_bible
