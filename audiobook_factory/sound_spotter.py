#!/usr/bin/env python3
"""
Audiobook Factory - Stage 3.5: Specialist Multi-Agent Sound Spotting Engine.
=============================================================================
Decouples sound design from dialogue screenplay generation into 3 dedicated
specialist LLM agents powered concurrently by the 100+ rotating API key pool:
1. Foley & Prop Spotter: Physical props, interactions, weapons, and tactile actions.
2. Ambience & Acoustic Designer: Story setting, room tone, environmental weather.
3. Music Scoring Director: Dramatic tension, emotional swells, >= 60% silence rule.

Outputs an explicit, inspectable `chapter_XXX_sound_script.json` (Audio Cue Sheet).
Enforces dynamic Era & Setting filters with zero single-novel biases.
"""

from __future__ import annotations
import os
import json
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from audiobook_factory.logger import logger
from audiobook_factory.key_manager import get_persistent_key_pool
from audiobook_factory.cadence import get_stealth_sdk_headers
from audiobook_factory.model_manager import get_model_manager, TaskType
from audiobook_factory.sound_bank import SoundBank, get_sound_bank
from audiobook_factory.safety import get_dramatic_fiction_framing, get_universal_safety_settings
from audiobook_factory.project_classifier import ProjectClassifier


# Semantic era conflict filters (prevents blatant chronological anachronisms)
ERA_BANNED_TAGS: Dict[str, set[str]] = {
    "MODERN": {
        "catapult", "drawbridge", "trebuchet", "battering_ram", "swamp", "sword", "dungeon", "crypt"
    },
    "MODERN_CONTEMPORARY": {
        "catapult", "drawbridge", "trebuchet", "battering_ram", "swamp", "sword", "dungeon", "crypt"
    },
    "MEDIEVAL_FANTASY": {
        "car", "automobile", "engine", "traffic", "gunshot", "phone", "telephone",
        "siren", "computer", "subway", "train", "airplane", "helicopter", "television"
    },
    "SPACE_OPERA_SCIFI": {
        "horse_carriage", "stagecoach", "musket", "flintlock"
    },
    "PULP_NOIR_1940S": {
        "smartphone", "internet", "laser", "cyborg", "spacesuit"
    },
    "VICTORIAN_EDWARDIAN": {
        "automobile", "airplane", "television", "computer", "cell_phone"
    },
}


class SoundSpotter:
    """Specialist multi-agent sound spotting engine for audio drama production."""

    def __init__(self, sound_bank: Optional[SoundBank] = None):
        self.sound_bank = sound_bank or get_sound_bank()
        self.pool = get_persistent_key_pool()
        self.model_mgr = get_model_manager()

    def spot_chapter(
        self,
        chapter_id: str,
        script_segments: List[Dict[str, Any]],
        segment_durations_sec: Dict[int, float],
        seg_starts_ms: Dict[int, int],
        total_duration_sec: float,
        era: Optional[str] = None,
        franchise_affinity: Optional[str] = None,
        project_dir: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """
        Executes concurrent 3-agent sound spotting session and compiles
        the explicit `chapter_XXX_sound_script.json` Audio Cue Sheet.
        """
        # Auto-resolve Era, Genre & Franchise from project if unspecified
        title = ""
        author = ""
        if project_dir:
            pdir = Path(project_dir)
            meta_file = pdir / "metadata.json"
            if meta_file.exists():
                try:
                    with open(meta_file, "r", encoding="utf-8") as f:
                        m_data = json.load(f)
                        title = m_data.get("title", "")
                        author = m_data.get("author", "")
                        if not era or era.upper() in ("MODERN", "DEFAULT"):
                            era = m_data.get("era")
                        if not franchise_affinity:
                            franchise_affinity = m_data.get("franchise_affinity") or m_data.get("franchise")
                except Exception:
                    pass

            if not era or era.upper() in ("MODERN", "DEFAULT"):
                classification = ProjectClassifier.classify(project_dir=pdir)
                era = classification.era
                if not franchise_affinity:
                    franchise_affinity = classification.franchise_affinity

        active_era = (era or "GENERAL_DRAMA").upper()

        logger.info(
            f"[*] SoundSpotter: Launching Multi-Agent Spotting Session for {chapter_id} "
            f"(Era: {active_era}, Franchise: {franchise_affinity or 'None'}, {len(script_segments)} segments, Duration: {total_duration_sec:.1f}s)..."
        )

        total_duration_ms = int(total_duration_sec * 1000)

        # Prepare concise prose summary for spotting agents
        prose_lines = []
        for s in script_segments:
            s_idx = s.get("index", 1)
            spk = s.get("speaker", "Narrator")
            styp = s.get("type", "narration")
            txt = (s.get("text") or "").strip()
            prose_lines.append(f"[{s_idx:03d} | {styp.upper()} | {spk}]: {txt}")
        scene_prose = "\n".join(prose_lines)

        # Concurrent execution of the 3 specialist agents across key pool
        foley_events = []
        ambience_scenes = []
        music_cues = []

        with ThreadPoolExecutor(max_workers=3) as executor:
            future_foley = executor.submit(self._run_foley_spotter, scene_prose, active_era, title, author)
            future_amb = executor.submit(self._run_ambience_spotter, scene_prose, active_era, title, author)
            future_music = executor.submit(self._run_music_spotter, scene_prose, total_duration_sec, active_era, title, author)

            try:
                foley_events = future_foley.result(timeout=60.0)
            except Exception as e:
                logger.warning(f"  [!] Foley Spotter warning: {e}")

            try:
                ambience_scenes = future_amb.result(timeout=60.0)
            except Exception as e:
                logger.warning(f"  [!] Ambience Spotter warning: {e}")

            try:
                music_cues = future_music.result(timeout=60.0)
            except Exception as e:
                logger.warning(f"  [!] Music Spotter warning: {e}")

        logger.info(
            f"  [+] Multi-Agent Spotting Output: {len(foley_events)} Foley events, "
            f"{len(ambience_scenes)} Ambience beds, {len(music_cues)} Music cues."
        )

        # Era-aware sound bank asset resolution
        banned_tags = ERA_BANNED_TAGS.get(active_era, set())

        resolved_foley = self._resolve_foley_cues(
            foley_events=foley_events,
            script_segments=script_segments,
            seg_starts_ms=seg_starts_ms,
            segment_durations_sec=segment_durations_sec,
            banned_tags=banned_tags,
            era=active_era,
            franchise_affinity=franchise_affinity,
        )

        resolved_ambience = self._resolve_ambience_beds(
            ambience_scenes=ambience_scenes,
            total_duration_ms=total_duration_ms,
            banned_tags=banned_tags,
            era=active_era,
            franchise_affinity=franchise_affinity,
        )

        resolved_music = self._resolve_music_cues(
            music_cues=music_cues,
            seg_starts_ms=seg_starts_ms,
            total_duration_ms=total_duration_ms,
            banned_tags=banned_tags,
            franchise_affinity=franchise_affinity,
        )

        sound_script = {
            "chapter_id": chapter_id,
            "era": active_era,
            "franchise_affinity": franchise_affinity,
            "total_duration_ms": total_duration_ms,
            "foley_cues": resolved_foley,
            "ambience_scenes": resolved_ambience,
            "music_cues": resolved_music,
            "metadata": {
                "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "spotting_engine": "SoundSpotter Multi-Agent v3.1 Universal",
                "era_enforced": active_era,
                "franchise_affinity": franchise_affinity,
            },
        }

        # Save to disk if project directory is provided
        if project_dir:
            manifests_dir = Path(project_dir) / "manifests"
            manifests_dir.mkdir(parents=True, exist_ok=True)
            out_file = manifests_dir / f"{chapter_id}_sound_script.json"
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(sound_script, f, ensure_ascii=False, indent=2)
            logger.info(f"[+] SoundSpotter: Audio Cue Sheet saved to {out_file.name}")

        return sound_script

    # =========================================================================
    # SPECIALIST AGENT 1: Foley & Physical Prop Spotter
    # =========================================================================
    def _run_foley_spotter(self, scene_prose: str, era: str, title: str = "", author: str = "") -> List[Dict[str, Any]]:
        """Scans prose strictly for physical props, actions, and sounds."""
        framing = get_dramatic_fiction_framing(title, author)

        # Dynamic era-specific examples
        if era == "MEDIEVAL_FANTASY":
            era_guidance = (
                "Era: Medieval Fantasy. Identify authentic period and fantasy props: "
                "sword draw, blade clash, scabbard creak, shield bash, armor rattle, torch sizzle, "
                "tankard slam, coin pouch clink, tavern door creak, horse bridle rattle, footsteps on gravel/cobblestones."
            )
        elif era in ("SPACE_OPERA_SCIFI", "RETRO_FUTURE_CYBERPUNK"):
            era_guidance = (
                "Era: Sci-Fi / Cyberpunk. Identify technological and atmospheric physical actions: "
                "hydraulic airlock hiss, console keypad chirp, weapon holster click, plasma hum, "
                "footsteps on metal grating, cyberware whirr, comm link beep."
            )
        else:
            era_guidance = (
                f"Era: {era}. Identify authentic physical interactions: "
                "door open/close, footsteps on floor/pavement, cup clink, chair shift, coat rustle, "
                "keys rattling, paper rustling, physical impacts."
            )

        sys_prompt = (
            "You are an elite Hollywood Foley Supervisor & Sound Designer. "
            f"{framing}"
            "Analyze the scene text and identify REAL PHYSICAL ACTIONS and props explicitly happening. "
            f"{era_guidance} "
            "Never invent metaphoric sounds; spot only physical interactions explicitly rooted in the action."
        )

        prompt = f"""Scene Text:
\"\"\"
{scene_prose[:8000]}
\"\"\"

Return a JSON array of physical Foley events where each object has:
- "segment_index": int (1-based segment where this physical action occurs)
- "action_verb": string (e.g. "sword_draw", "tankard_slam", "door_creak", "footsteps", "blade_clash", "coin_drop")
- "object_material": string (e.g. "metal", "wood", "glass", "stone", "leather", "gravel")
- "anchor_word": string (specific word or tag in the segment text anchoring the sound)
- "gain_dbfs": float (-14.0 to -22.0)
- "pan": float (-0.6 to 0.6)
- "description": string (brief description)
"""
        return self._call_gemini_json(prompt, sys_prompt)

    # =========================================================================
    # SPECIALIST AGENT 2: Ambience & Acoustic Space Designer
    # =========================================================================
    def _run_ambience_spotter(self, scene_prose: str, era: str, title: str = "", author: str = "") -> List[Dict[str, Any]]:
        """Scans prose to determine environmental room tone, location, and weather."""
        framing = get_dramatic_fiction_framing(title, author)

        if era == "MEDIEVAL_FANTASY":
            era_ambience = (
                "Appropriate environments: stone_ruins_exterior, tavern_interior, castle_great_hall, "
                "crypt_catacomb, deep_forest_night, swamp_marsh_night, mountain_pass_blizzard, city_market_square."
            )
        elif era in ("SPACE_OPERA_SCIFI", "RETRO_FUTURE_CYBERPUNK"):
            era_ambience = (
                "Appropriate environments: spaceship_bridge, cyberpunk_alley_rain, engine_room_hum, "
                "orbital_station_concourse, futuristic_corridor."
            )
        else:
            era_ambience = (
                "Appropriate environments: room_tone, domestic_room, office_commercial, city_street_day, "
                "suburban_street_night, rain_gentle, quiet_park."
            )

        sys_prompt = (
            "You are a Supervising Acoustic Environment Designer for audio drama. "
            f"{framing}"
            "Determine the ambient environment, room tone, time of day, and weather of the scene. "
            f"Scene era is {era}. {era_ambience}"
        )

        prompt = f"""Scene Text:
\"\"\"
{scene_prose[:8000]}
\"\"\"

Return a JSON array of Ambience beds where each object has:
- "name": string (standard environment slug matching the scene location, e.g. "stone_ruins_exterior", "tavern_interior", "room_tone", "spaceship_bridge")
- "setting": string (e.g. "Crumbling ruins outside cavern entrance", "Bustling tavern taproom", "Spaceship command deck")
- "target_lufs": float (-30.0 to -34.0, default -32.0)
- "reverb_preset": string ("room", "hall", "plate", or "none")
"""
        return self._call_gemini_json(prompt, sys_prompt)

    # =========================================================================
    # SPECIALIST AGENT 3: Music Scoring Director
    # =========================================================================
    def _run_music_spotter(self, scene_prose: str, total_duration_sec: float, era: str = "", title: str = "", author: str = "") -> List[Dict[str, Any]]:
        """Maps dramatic tension swells and transitions while respecting the 60% silence rule."""
        max_music_sec = total_duration_sec * 0.38
        framing = get_dramatic_fiction_framing(title, author)

        sys_prompt = (
            "You are an Academy-Award winning Audio Drama Music Composer and Scoring Director. "
            f"{framing}"
            "Spot surgical musical cues to underline dramatic tension, mystery, reveals, or emotional turns. "
            "CRITICAL MANDATE: At least 60-65% of the scene timeline MUST remain in pure acoustic silence "
            f"(only dialogue + subtle room tone). Total music across all cues MUST NOT exceed {max_music_sec:.1f} seconds! "
            "Maximum 2-3 surgical cues per scene. Music must NEVER play wall-to-wall without purpose."
        )

        prompt = f"""Scene Text:
\"\"\"
{scene_prose[:8000]}
\"\"\"

Return a JSON array of Music cues where each object has:
- "trigger_segment": int (segment index where the cue starts)
- "duration_sec": float (15.0 to 60.0)
- "narrative_archetype": string (e.g. "MYSTERY_PROLOGUE", "TENSION", "NOCTURNAL_VIGIL", "SWORD_DUEL", "MONSTER_HUNT", "BITTERSWEET_PARTING", "ROYAL_CONSPIRACY")
- "mood": string ("mysterious", "tense", "peaceful", "emotional", "epic", "dramatic")
- "tempo": string ("slow", "moderate", "fast")
- "timbre": string ("dark strings", "solo cello", "hurdy-gurdy", "slavic folk instruments", "brass", "atmospheric pads")
- "energy_section": string ("INTRO_BED", "RISING_TENSION", "CLIMAX_DROP")
- "search_query": string (optimal 3-word query for music search)
- "volume_db": float (-7.0 to -9.0)
- "dramatic_justification": string
"""
        return self._call_gemini_json(prompt, sys_prompt)

    # =========================================================================
    # RESOLUTION HELPERS: Sound Bank Lookup & Franchise Priority
    # =========================================================================
    def _search_sound_bank(
        self,
        query: str,
        category: str,
        limit: int = 5,
        franchise_affinity: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        try:
            return self.sound_bank.search(
                query,
                category=category,
                limit=limit,
                franchise_affinity=franchise_affinity,
            )
        except TypeError:
            return self.sound_bank.search(
                query,
                category=category,
                limit=limit,
            )

    def _resolve_foley_cues(
        self,
        foley_events: List[Dict[str, Any]],
        script_segments: List[Dict[str, Any]],
        seg_starts_ms: Dict[int, int],
        segment_durations_sec: Dict[int, float],
        banned_tags: set[str],
        era: str = "GENERAL_DRAMA",
        franchise_affinity: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        resolved = []
        for idx, ev in enumerate(foley_events):
            s_idx = ev.get("segment_index", 1)
            verb = ev.get("action_verb", "").strip()
            mat = ev.get("object_material", "").strip()
            if not verb:
                continue

            query = f"{verb} {mat}".strip()
            valid_asset = self.sound_bank.resolve_sound(
                query=query,
                category="foley",
                era=era,
                franchise_affinity=franchise_affinity,
                verify=True,
                is_continuous_bed=False,
            )
            if not valid_asset:
                valid_asset = self.sound_bank.resolve_sound(
                    query=verb,
                    category="foley",
                    era=era,
                    franchise_affinity=franchise_affinity,
                    verify=True,
                    is_continuous_bed=False,
                )

            if not valid_asset:
                continue

            seg_start = seg_starts_ms.get(s_idx, 0)
            cue_start_ms = max(0, seg_start + 100)

            resolved.append({
                "cue_id": f"fc_{s_idx:04d}_{idx:03d}",
                "segment_index": s_idx,
                "anchor_word": ev.get("anchor_word", verb),
                "pre_roll_ms": 100,
                "asset_path": str(valid_asset.resolve()).replace("\\", "/"),
                "asset_name": valid_asset.name,
                "gain_dbfs": float(ev.get("gain_dbfs", -16.0)),
                "azimuth_pan": float(ev.get("pan", 0.0)),
                "start_ms": cue_start_ms,
                "duration_ms": 0,
                "ucs_category": "MISCGnl",
            })
        return resolved

    def _resolve_ambience_beds(
        self,
        ambience_scenes: List[Dict[str, Any]],
        total_duration_ms: int,
        banned_tags: set[str],
        era: str,
        franchise_affinity: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        resolved = []
        n_scenes = max(1, len(ambience_scenes))
        scene_dur_ms = total_duration_ms // n_scenes

        for idx, amb in enumerate(ambience_scenes):
            name = amb.get("name", "room_tone")
            query = name.replace("_", " ")

            valid_asset = self.sound_bank.resolve_sound(
                query=query,
                category="ambience",
                era=era,
                franchise_affinity=franchise_affinity,
                verify=True,
                is_continuous_bed=True,
            )
            if not valid_asset:
                valid_asset = self.sound_bank.resolve_sound(
                    query="ambient room tone background",
                    category="ambience",
                    era=era,
                    franchise_affinity=franchise_affinity,
                    verify=True,
                    is_continuous_bed=True,
                )

            if valid_asset:
                st_ms = amb.get("start_ms", idx * scene_dur_ms)
                et_ms = amb.get("end_ms", (idx + 1) * scene_dur_ms if idx < n_scenes - 1 else total_duration_ms)
                resolved.append({
                    "scene_id": idx + 1,
                    "start_ms": st_ms,
                    "end_ms": et_ms,
                    "asset_path": str(valid_asset.resolve()).replace("\\", "/"),
                    "asset_name": valid_asset.name,
                    "target_lufs": float(amb.get("target_lufs", -34.0)),
                    "reverb_preset": amb.get("reverb_preset", "room"),
                })
        return resolved

    def _resolve_music_cues(
        self,
        music_cues: List[Dict[str, Any]],
        seg_starts_ms: Dict[int, int],
        total_duration_ms: int,
        banned_tags: set[str],
        franchise_affinity: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        resolved = []
        max_music_budget_ms = int(total_duration_ms * 0.40)
        accumulated_ms = 0

        for idx, mc in enumerate(music_cues):
            if accumulated_ms >= max_music_budget_ms:
                break

            q = mc.get("search_query") or f"{mc.get('narrative_archetype', '')} {mc.get('mood', '')} {mc.get('timbre', '')}"
            sec_type = mc.get("energy_section", "INTRO_BED")
            results = self.sound_bank.search_music_catalog(q, section_type=sec_type, limit=3)
            if not results:
                results = self.sound_bank.search(
                    q,
                    category="music",
                    limit=3,
                    franchise_affinity=franchise_affinity,
                )

            valid_asset = None
            track_name = ""
            track_id = 0
            start_sec = 0.0

            for r in results:
                fpath = r.get("filepath", "")
                fname = r.get("filename", "").lower()
                if any(b in fname for b in banned_tags):
                    continue
                cand_path = Path(fpath)
                if cand_path.exists():
                    valid_asset = cand_path
                    track_name = r.get("filename", cand_path.name)
                    track_id = r.get("id", idx + 1)
                    start_sec = float(r.get("start_sec", 0.0) or 0.0)
                    break

            if not valid_asset:
                continue

            t_seg = mc.get("trigger_segment", 1)
            start_ms = seg_starts_ms.get(t_seg, 0)
            if start_ms >= total_duration_ms:
                continue

            dur_ms = int(float(mc.get("duration_sec", 30.0)) * 1000)
            remaining = max_music_budget_ms - accumulated_ms
            dur_ms = min(dur_ms, remaining, total_duration_ms - start_ms)
            if dur_ms < 5000:
                continue

            accumulated_ms += dur_ms

            resolved.append({
                "cue_id": f"cue_{idx+1:02d}",
                "cue_type": "EMOTIONAL_UNDERSCORE",
                "track_id": track_id,
                "track_name": track_name,
                "section_name": sec_type,
                "section_start_sec": start_sec,
                "start_ms": start_ms,
                "duration_ms": dur_ms,
                "fade_in_ms": 2500,
                "fade_out_ms": 3500,
                "volume_db": float(mc.get("volume_db", -7.5)),
                "dramatic_justification": mc.get("dramatic_justification", "Atmospheric dramatic underscore"),
                "narrative_archetype": mc.get("narrative_archetype", "TENSION"),
            })
        return resolved

    def _call_gemini_json(self, prompt: str, system_instruction: str) -> List[Dict[str, Any]]:
        """Invokes Gemini with rotating keys from key pool via centralized llm_client."""
        from audiobook_factory.llm_client import call_gemini
        from audiobook_factory.model_manager import LLMUnavailableError

        try:
            parsed = call_gemini(
                task_type=TaskType.DIRECTING,
                prompt=prompt,
                system_instruction=system_instruction,
                temperature=0.25,
                response_mime_type="application/json",
            )
            if isinstance(parsed, list):
                return parsed
            elif isinstance(parsed, dict):
                for k in ("events", "cues", "scenes", "foley_events", "ambience_scenes", "music_cues"):
                    if k in parsed and isinstance(parsed[k], list):
                        return parsed[k]
                return [parsed]
            return []
        except LLMUnavailableError:
            raise
        except Exception as e:
            logger.warning(f"  [!] SoundSpotter agent error: {e}")
            return []
