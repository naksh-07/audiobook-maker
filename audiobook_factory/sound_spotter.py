#!/usr/bin/env python3
"""
Audiobook Factory - Stage 3.5: Specialist Multi-Agent Sound Spotting Engine.
=============================================================================
Decouples sound design from dialogue screenplay generation into 3 dedicated
specialist LLM agents powered concurrently by the 100+ rotating API key pool:
1. Foley & Prop Spotter: Physical props, actions, doors, cars, tea cups, footsteps.
2. Ambience & Acoustic Designer: Story setting, room tones, weather, day/night.
3. Music Scoring Director: Dramatic tension, emotional swells, >= 60% silence rule.

Outputs an explicit, inspectable `chapter_XXX_sound_script.json` (Audio Cue Sheet).
Enforces Era & Setting negative filters (no medieval swamps in modern suburbs).
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


# Era-specific negative keyword blacklists
ERA_BANNED_TAGS = {
    "MODERN": {
        "swamp", "bog", "crypt", "dungeon", "sword", "blade", "armor", "scabbard",
        "drawbridge", "tavern", "tavern_brawl", "gore", "clash", "parry", "battle_axe",
        "shield", "spear", "crossbow", "arrow"
    },
    "MEDIEVAL_FANTASY": {
        "car", "automobile", "engine", "traffic", "gunshot", "phone", "telephone",
        "siren", "computer", "subway", "train", "airplane", "helicopter"
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
        era: str = "MODERN",
        project_dir: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """
        Executes concurrent 3-agent sound spotting session and compiles
        the explicit `chapter_XXX_sound_script.json` Audio Cue Sheet.
        """
        logger.info(
            f"[*] SoundSpotter: Launching Multi-Agent Spotting Session for {chapter_id} "
            f"(Era: {era}, {len(script_segments)} segments, Duration: {total_duration_sec:.1f}s)..."
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
            future_foley = executor.submit(self._run_foley_spotter, scene_prose, era)
            future_amb = executor.submit(self._run_ambience_spotter, scene_prose, era)
            future_music = executor.submit(self._run_music_spotter, scene_prose, total_duration_sec)

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
        banned_tags = ERA_BANNED_TAGS.get(era.upper(), set())

        resolved_foley = self._resolve_foley_cues(
            foley_events=foley_events,
            script_segments=script_segments,
            seg_starts_ms=seg_starts_ms,
            segment_durations_sec=segment_durations_sec,
            banned_tags=banned_tags,
        )

        resolved_ambience = self._resolve_ambience_beds(
            ambience_scenes=ambience_scenes,
            total_duration_ms=total_duration_ms,
            banned_tags=banned_tags,
            era=era,
        )

        resolved_music = self._resolve_music_cues(
            music_cues=music_cues,
            seg_starts_ms=seg_starts_ms,
            total_duration_ms=total_duration_ms,
            banned_tags=banned_tags,
        )

        sound_script = {
            "chapter_id": chapter_id,
            "era": era,
            "total_duration_ms": total_duration_ms,
            "foley_cues": resolved_foley,
            "ambience_scenes": resolved_ambience,
            "music_cues": resolved_music,
            "metadata": {
                "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "spotting_engine": "SoundSpotter Multi-Agent v3.0",
                "era_enforced": era,
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
    def _run_foley_spotter(self, scene_prose: str, era: str) -> List[Dict[str, Any]]:
        """Scans prose strictly for physical props, actions, and sounds."""
        sys_prompt = (
            "You are a Hollywood Foley Supervisor & Sound Designer. "
            "Analyze the scene text and identify REAL PHYSICAL ACTIONS and props explicitly happening. "
            "Examples: car door close, car engine humming, briefcase latch opening/closing, tea cup clink, "
            "footsteps on pavement, owl wings fluttering, cat purr, paper rustle. "
            f"STRICT INVARIANT: The scene is in {era} era. NEVER invent fantasy or medieval weapons/sounds if modern!"
        )

        prompt = f"""Scene Text:
\"\"\"
{scene_prose[:8000]}
\"\"\"

Return a JSON array of physical Foley events where each object has:
- "segment_index": int (1-based segment where this physical action occurs)
- "action_verb": string (e.g. "car_door", "car_engine", "briefcase", "footsteps", "cup", "flutter")
- "object_material": string (e.g. "metal", "wood", "glass", "pavement", "wings")
- "anchor_word": string (specific word or tag in the segment text anchoring the sound)
- "gain_dbfs": float (-14.0 to -22.0)
- "pan": float (-0.6 to 0.6)
- "description": string (brief description)
"""
        return self._call_gemini_json(prompt, sys_prompt)

    # =========================================================================
    # SPECIALIST AGENT 2: Ambience & Acoustic Space Designer
    # =========================================================================
    def _run_ambience_spotter(self, scene_prose: str, era: str) -> List[Dict[str, Any]]:
        """Scans prose to determine environmental room tone, location, and weather."""
        sys_prompt = (
            "You are a Supervising Acoustic Environment Designer for audio drama. "
            "Determine the ambient environment, room tone, time of day, and weather of the scene. "
            f"STRICT INVARIANT: Scene era is {era}. For a 1990s suburban domestic house, the room tone is "
            "'domestic_room_quiet' or 'suburban_house_tone'. NEVER assign swamp, crypt, or castle ambience to modern suburbs!"
        )

        prompt = f"""Scene Text:
\"\"\"
{scene_prose[:8000]}
\"\"\"

Return a JSON array of Ambience beds where each object has:
- "name": string (e.g. "domestic_room_quiet", "suburban_street_day", "office_interior", "rain_gentle")
- "setting": string (e.g. "Suburban house bedroom", "Quiet English street morning", "Busy commute")
- "target_lufs": float (-30.0 to -34.0, default -32.0)
- "reverb_preset": string ("room", "hall", "plate", or "none")
"""
        return self._call_gemini_json(prompt, sys_prompt)

    # =========================================================================
    # SPECIALIST AGENT 3: Music Scoring Director
    # =========================================================================
    def _run_music_spotter(self, scene_prose: str, total_duration_sec: float) -> List[Dict[str, Any]]:
        """Maps dramatic tension swells and transitions while respecting the 60% silence rule."""
        max_music_sec = total_duration_sec * 0.38
        sys_prompt = (
            "You are an Academy-Award winning Audio Drama Music Composer and Scoring Director. "
            "Spot surgical musical cues to underline dramatic tension, mystery, or emotional turns. "
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
- "narrative_archetype": string (e.g. "MYSTERY_PROLOGUE", "TENSION", "NOCTURNAL_VIGIL", "BITTERSWEET_PARTING")
- "mood": string ("mysterious", "tense", "peaceful", "emotional", "epic")
- "tempo": string ("slow", "moderate")
- "timbre": string ("dark strings", "solo cello", "pizzicato strings", "atmospheric pads")
- "energy_section": string ("INTRO_BED", "RISING_TENSION", "CLIMAX_DROP")
- "search_query": string (optimal 3-word query for music search)
- "volume_db": float (-7.0 to -9.0)
- "dramatic_justification": string
"""
        return self._call_gemini_json(prompt, sys_prompt)

    # =========================================================================
    # RESOLUTION HELPERS: Era Negative Filter & Sound Bank Lookup
    # =========================================================================
    def _resolve_foley_cues(
        self,
        foley_events: List[Dict[str, Any]],
        script_segments: List[Dict[str, Any]],
        seg_starts_ms: Dict[int, int],
        segment_durations_sec: Dict[int, float],
        banned_tags: set[str],
    ) -> List[Dict[str, Any]]:
        resolved = []
        for idx, ev in enumerate(foley_events):
            s_idx = ev.get("segment_index", 1)
            verb = ev.get("action_verb", "").strip()
            mat = ev.get("object_material", "").strip()
            if not verb:
                continue

            query = f"{verb} {mat}".strip()
            results = self.sound_bank.search(query, category="foley", limit=5)
            if not results:
                results = self.sound_bank.search(verb, category="foley", limit=5)

            # Filter out banned era tags
            valid_asset = None
            for r in results:
                fpath = r.get("filepath", "")
                fname = r.get("filename", "").lower()
                tags = r.get("tags", "").lower()
                if any(b in fname or b in tags for b in banned_tags):
                    continue
                cand_path = Path(fpath)
                if cand_path.exists():
                    valid_asset = cand_path
                    break

            # If no valid asset without banned tags, fall back gracefully to silence (NEVER use wrong genre)
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
    ) -> List[Dict[str, Any]]:
        resolved = []
        for idx, amb in enumerate(ambience_scenes):
            name = amb.get("name", "domestic_room_quiet")
            results = self.sound_bank.search(name.replace("_", " "), category="ambience", limit=5)
            if not results:
                # Fallback to general quiet room tone
                results = self.sound_bank.search("room tone quiet", category="ambience", limit=5)

            valid_asset = None
            for r in results:
                fpath = r.get("filepath", "")
                fname = r.get("filename", "").lower()
                tags = r.get("tags", "").lower()
                if any(b in fname or b in tags for b in banned_tags):
                    continue
                cand_path = Path(fpath)
                if cand_path.exists():
                    valid_asset = cand_path
                    break

            if not valid_asset and results and Path(results[0]["filepath"]).exists():
                # Verify that top result is not a swamp/bog/crypt
                first_p = Path(results[0]["filepath"])
                if not any(b in first_p.name.lower() for b in banned_tags):
                    valid_asset = first_p

            if valid_asset:
                resolved.append({
                    "scene_id": idx + 1,
                    "start_ms": 0,
                    "end_ms": total_duration_ms,
                    "asset_path": str(valid_asset.resolve()).replace("\\", "/"),
                    "asset_name": valid_asset.name,
                    "target_lufs": float(amb.get("target_lufs", -32.0)),
                    "reverb_preset": amb.get("reverb_preset", "room"),
                })
        return resolved

    def _resolve_music_cues(
        self,
        music_cues: List[Dict[str, Any]],
        seg_starts_ms: Dict[int, int],
        total_duration_ms: int,
        banned_tags: set[str],
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
                results = self.sound_bank.search(q, category="music", limit=3)

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
        from audiobook_factory.exceptions import LLMUnavailableError

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
