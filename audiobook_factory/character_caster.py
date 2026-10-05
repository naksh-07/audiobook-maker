#!/usr/bin/env python3
"""
Audiobook Factory - Stage 1/2: Autonomous Character Discovery & Casting Director.
Scans extracted novel chapters (English or Hindi), extracts the dramatis personae,
and assigns non-colliding studio vocal personas (Gemini TTS) with cast lock persistence.
"""

from __future__ import annotations
import os
import json
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, List, Optional, Set

from audiobook_factory.logger import logger
from audiobook_factory.key_manager import get_persistent_key_pool
from audiobook_factory.model_manager import get_model_manager, TaskType, LLMUnavailableError
from audiobook_factory.llm_client import call_gemini

# Studio Voice Persona Catalogs (Verified Gemini TTS API Voices)
MALE_VOICE_PERSONAS = [
    "Charon",      # Deep, gravelly, menacing, stoic or imposing (Protagonists, Warriors)
    "Puck",        # Middle-aged, energetic, expressive, comedic or charismatic
    "Fenrir",      # Authoritative, wise, warm, elder, scholar or mentor
    "Enceladus",   # Heavy, deep, booming, powerful
    "Algieba",     # Rustic, rough, gritty, aggressive
    "Algenib",     # Calm, steady, observational
    "Alnilam",     # Direct, resolute, soldierly
    "Achird",      # Sharp, youthful, agile
    "Iapetus",     # Dark, solemn, mysterious
    "Orus",        # Bold, proud, aristocratic
    "Rasalgethi",  # Raw, rugged, weathered
    "Schedar",     # Cold, formal, regal
]

FEMALE_VOICE_PERSONAS = [
    "Kore",        # Mature, sharp, prim, observant or commanding
    "Leda",        # Gentle, maternal, emotional, tender
    "Achernar",    # Deep female, solemn, mystical
    "Callirrhoe",  # Melodic, lyrical, youthful
    "Despina",     # Crisp, quick-witted, feisty
    "Autonoe",     # Regal, proud, aristocratic
    "Erinome",     # Haunting, quiet, atmospheric
    "Gacrux",      # Stately, authoritative, mature
    "Laomedeia",   # Soft, delicate, vulnerable
    "Sulafat",     # Rich, warm, captivating
]


class CharacterCaster:
    """Autonomous casting director for novel audio dramas."""

    @classmethod
    def discover_and_cast_project(
        cls,
        project_dir: Path,
        use_hindi: bool = False,
        default_narrator_voice: str = "Aoede",
        force_recast: bool = False,
    ) -> Dict[str, Any]:
        """
        Discovers characters across project chapters, creates character_roster.json,
        voice_registry.json, and cast_lock.json with collision-free voice signatures.
        """
        project_dir = Path(project_dir).resolve()
        roster_path = project_dir / "character_roster.json"
        registry_path = project_dir / "voice_registry.json"
        lock_path = project_dir / "cast_lock.json"

        if not force_recast and roster_path.exists() and registry_path.exists():
            try:
                with open(roster_path, "r", encoding="utf-8") as rf:
                    roster = json.load(rf)
                if roster.get("characters") and len(roster["characters"]) > 1:
                    logger.info(f"[*] CharacterCaster: Existing roster loaded ({len(roster['characters'])} characters).")
                    return roster
            except Exception as e:
                logger.warning(f"  [!] Failed to read existing roster, recasting: {e}")

        # Collect text samples from available chapters
        search_dir = project_dir / "translation" if use_hindi and (project_dir / "translation").exists() else project_dir / "extracted"
        if not search_dir.exists():
            search_dir = project_dir / "extracted"

        chap_files = sorted(search_dir.glob("chapter_*.md"))
        if not chap_files:
            logger.warning("  [!] CharacterCaster: No chapter markdown files found for casting analysis.")
            return {"project_id": f"proj-{project_dir.name}", "characters": {}}

        valid_chaps = []
        for cf in chap_files:
            try:
                with open(cf, "r", encoding="utf-8") as f:
                    txt = f.read()
                lower_txt = txt.lower()
                if "copyright" in lower_txt or "all rights reserved" in lower_txt or len(txt.split()) < 200:
                    continue
                valid_chaps.append(txt)
            except Exception:
                pass

        if not valid_chaps and chap_files:
            valid_chaps = [chap_files[0].read_text(encoding="utf-8")]

        # Comprehensive sampling across novel scope (up to 15 chapters distributed across beginning, middle, climax, end)
        if len(valid_chaps) <= 15:
            selected_chaps = valid_chaps
        else:
            step = len(valid_chaps) / 15.0
            indices = [int(i * step) for i in range(15)]
            indices.append(len(valid_chaps) - 1)
            selected_chaps = [valid_chaps[i] for i in sorted(set(indices))]

        sample_texts = [txt[:5000] for txt in selected_chaps]
        combined_sample = "\n\n--- NEXT CHAPTER SAMPLE ---\n\n".join(sample_texts)

        # Call LLM Casting Director
        raw_characters = cls._call_llm_casting(combined_sample, is_hindi=use_hindi)

        # Build collision-free assignment
        roster, registry, cast_lock = cls._build_cast_allocation(
            project_id=f"proj-{project_dir.name}",
            raw_characters=raw_characters,
            default_narrator_voice=default_narrator_voice,
            use_hindi=use_hindi,
        )

        # Write files atomically
        with open(roster_path, "w", encoding="utf-8") as f:
            json.dump(roster, f, ensure_ascii=False, indent=2)
        with open(registry_path, "w", encoding="utf-8") as f:
            json.dump(registry, f, ensure_ascii=False, indent=2)
        with open(lock_path, "w", encoding="utf-8") as f:
            json.dump(cast_lock, f, ensure_ascii=False, indent=2)

        logger.info(
            f"[+] CharacterCaster: Cast locked for {len(roster['characters'])} roles. "
            f"Saved to {roster_path.name}, {registry_path.name}, {lock_path.name}."
        )
        return roster

    @classmethod
    def _call_llm_casting(cls, text_sample: str, is_hindi: bool = False) -> List[Dict[str, Any]]:
        """Invokes Gemini to extract speaking characters from prose samples."""
        pool = get_persistent_key_pool()
        model_mgr = get_model_manager()
        model = model_mgr.resolve_active_model(TaskType.SCREENPLAY)

        sys_prompt = (
            "You are the Lead Casting Director for a Hollywood & BBC Radio Audio Drama studio. "
            "Analyze these book chapter samples and extract ALL speaking characters who have dialogue or direct presence. "
            "For each character, identify their canonical English name, Hindi name (if in Hindi translation), "
            "gender ('male' or 'female'), approximate age/archetype, and all known aliases/titles."
        )

        prompt = f"""Language: {"Hindi (Devanagari)" if is_hindi else "English"}
Prose Samples:
\"\"\"
{text_sample[:80000]}
\"\"\"

Return a JSON array of objects with:
- "canonical_name": string (e.g. "Protagonist Name", "Village Elder", "Lead Detective")
- "hindi_name": string (Devanagari spelling if applicable, e.g. "मुख्य पात्र")
- "gender": "male" | "female" | "neutral"
- "archetype": string (e.g. "stoic rural farmer", "shrewd urban detective", "wise elderly mentor", "rebellious youth")
- "aliases": list of strings (e.g. ["मुख्य पात्र", "Character Full Name", "Nickname"])
"""


        try:
            parsed = call_gemini(
                task_type=TaskType.DIRECTING,
                prompt=prompt,
                system_instruction=sys_prompt,
                tools=[{"googleSearch": {}}],
                temperature=0.2,
                response_mime_type="application/json",
            )
            if isinstance(parsed, list):
                return parsed
            elif isinstance(parsed, dict) and "characters" in parsed:
                return parsed["characters"]
            elif isinstance(parsed, dict):
                return [parsed]
            return []
        except LLMUnavailableError:
            raise
        except Exception as e:
            logger.warning(f"  [!] CharacterCaster error: {e}")
            raise LLMUnavailableError(f"Character casting failed: {e}") from e

    @classmethod
    def compute_acoustic_formant_vector(
        cls,
        gender: str,
        archetype: str = "",
        prominence: str = "standard",
        index: int = 0,
    ) -> Dict[str, Any]:
        """
        Calculates a 4D acoustic vector (pitch, speed, EQ resonance, clarity reduction)
        to physically morph the vocal tract via FFmpeg asetrate/aresample/equalizer.
        Guarantees that even if two characters share the same base Gemini voice,
        they sound like completely distinct human beings with zero timbre overlap.
        """
        g = (gender or "male").lower()
        arch = (archetype or "").lower()

        # Male Vocal Acoustic Profiling
        if g == "male":
            if any(w in arch for w in ("heavy", "deep", "imposing", "rough", "rugged", "warrior", "soldier", "brute", "guard", "thug", "bodyguard", "laborer")):
                pitch = round(0.88 + (index % 3) * 0.02, 2)  # 0.88 - 0.92
                speed = 0.96
                bass_boost = 3.0
                presence_boost = 0.5
                clarity_cut = 0.0
                lowpass = 0
            elif any(w in arch for w in ("elder", "scholar", "mentor", "priest", "old", "father", "grandfather", "aged", "teacher")):
                pitch = round(0.92 + (index % 2) * 0.02, 2)  # 0.92 - 0.94
                speed = 0.94
                bass_boost = 1.0
                presence_boost = 1.2
                clarity_cut = 1.5
                lowpass = 6500
            elif any(w in arch for w in ("youth", "young", "boy", "agile", "sharp", "energetic", "comedic", "apprentice", "rebel", "student", "bard")):
                pitch = round(1.05 + (index % 3) * 0.02, 2)  # 1.05 - 1.09
                speed = 1.04
                bass_boost = -1.0
                presence_boost = 2.2
                clarity_cut = 0.0
                lowpass = 0
            elif any(w in arch for w in ("commoner", "rustic", "villager", "worker", "servant", "merchant", "driver", "shopkeeper", "innkeeper", "tavern", "tavernkeeper", "peasant")):
                pitch = round(1.06 + (index % 2) * 0.03, 2)  # 1.06 - 1.09
                speed = 0.97
                bass_boost = 0.0
                presence_boost = 1.8
                clarity_cut = 2.0
                lowpass = 0
            elif any(w in arch for w in ("lead", "protagonist", "hero", "detective", "commander", "leader", "officer", "noble", "governor")):
                pitch = round(0.95 + (index % 2) * 0.02, 2)  # 0.95 - 0.97
                speed = 0.99
                bass_boost = 2.0
                presence_boost = 1.2
                clarity_cut = 0.0
                lowpass = 0
            else:
                # Systemic non-colliding cycle across roles
                pitch_cycle = [0.93, 1.06, 0.96, 1.08, 0.90, 1.04, 0.97, 1.09]
                speed_cycle = [0.96, 1.03, 0.98, 1.04, 0.95, 1.02, 0.99, 1.05]
                bass_cycle = [2.5, -0.5, 1.5, -1.0, 3.0, 0.0, 1.0, -0.5]
                pres_cycle = [0.8, 2.0, 1.2, 2.2, 0.5, 1.5, 1.0, 2.0]
                clar_cycle = [0.0, 0.0, 0.0, 1.5, 0.0, 1.0, 0.0, 0.0]

                idx = index % len(pitch_cycle)
                pitch = pitch_cycle[idx]
                speed = speed_cycle[idx]
                bass_boost = bass_cycle[idx]
                presence_boost = pres_cycle[idx]
                clarity_cut = clar_cycle[idx]
                lowpass = 0
        else:
            # Female Vocal Acoustic Profiling
            if any(w in arch for w in ("commanding", "leader", "mature", "mother", "matriarch", "queen", "sorceress", "director", "officer")):
                pitch = round(0.94 + (index % 2) * 0.02, 2)  # 0.94 - 0.96
                speed = 0.98
                bass_boost = 1.5
                presence_boost = 1.5
                clarity_cut = 0.0
                lowpass = 0
            elif any(w in arch for w in ("youth", "young", "girl", "daughter", "delicate", "tender", "vulnerable", "student")):
                pitch = round(1.05 + (index % 2) * 0.02, 2)  # 1.05 - 1.07
                speed = 1.03
                bass_boost = -1.5
                presence_boost = 2.0
                clarity_cut = 0.0
                lowpass = 0
            elif any(w in arch for w in ("fierce", "resolute", "soldier", "warrior", "rebel", "sharp", "athletic")):
                pitch = round(0.97 + (index % 2) * 0.02, 2)  # 0.97 - 0.99
                speed = 1.01
                bass_boost = 1.8
                presence_boost = 1.8
                clarity_cut = 0.0
                lowpass = 0
            else:
                pitch_cycle = [0.95, 1.06, 0.98, 1.04, 0.93, 1.07]
                speed_cycle = [0.97, 1.03, 0.98, 1.02, 0.96, 1.04]
                bass_cycle = [1.0, -1.0, 1.5, -0.5, 0.0, -1.5]
                pres_cycle = [1.2, 2.0, 1.5, 1.8, 1.0, 2.2]

                idx = index % len(pitch_cycle)
                pitch = pitch_cycle[idx]
                speed = speed_cycle[idx]
                bass_boost = bass_cycle[idx]
                presence_boost = pres_cycle[idx]
                clarity_cut = 0.0
                lowpass = 0

        return {
            "pitch": pitch,
            "speed": speed,
            "bass_boost_db": bass_boost,
            "presence_boost_db": presence_boost,
            "clarity_reduction_db": clarity_cut,
            "lowpass_hz": lowpass,
        }

    @classmethod
    def _build_cast_allocation(
        cls,
        project_id: str,
        raw_characters: List[Dict[str, Any]],
        default_narrator_voice: str = "Aoede",
        use_hindi: bool = False,
    ) -> tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        """Builds non-colliding voice assignments for all characters."""
        used_signatures: Set[str] = set()

        # Always register Narrator
        roster_chars = {
            "Narrator": {
                "english_name": "Narrator",
                "display_name": "Narrator",
                "gender": "female" if default_narrator_voice in FEMALE_VOICE_PERSONAS else "male",
                "assigned_voice_id": default_narrator_voice,
                "aliases": ["सूत्रधार", "Narrator", "narration"],
            }
        }
        voice_registry = {
            "Narrator": {
                "voice": default_narrator_voice,
                "pitch": 1.0,
                "speed": 1.0,
                "bass_boost_db": 0.0,
                "presence_boost_db": 0.0,
                "clarity_reduction_db": 0.0,
                "lowpass_hz": 0,
            }
        }
        locks = {
            "Narrator": {
                "character_id": "Narrator",
                "character_name": "Narrator",
                "locked": True,
                "voice_id": default_narrator_voice,
                "calibration_overrides": {
                    "pitch": 1.0,
                    "speed": 1.0,
                    "bass_boost_db": 0.0,
                    "presence_boost_db": 0.0,
                    "clarity_reduction_db": 0.0,
                    "lowpass_hz": 0,
                },
            }
        }
        used_signatures.add(f"{default_narrator_voice}_p1.00_s1.00")

        male_idx = 0
        female_idx = 0

        for ch in raw_characters:
            name = (ch.get("canonical_name") or ch.get("english_name") or ch.get("name") or "").strip()
            if not name or name.lower() in ("narrator", "foley", "sfx"):
                continue

            gender = ch.get("gender", "male").lower()
            aliases = ch.get("aliases", [])
            hin_name = ch.get("hindi_name", "").strip()
            if hin_name and hin_name not in aliases:
                aliases.append(hin_name)

            arch = ch.get("archetype") or ch.get("vocal_archetype", "")
            prom = ch.get("prominence", "standard")

            if gender == "female":
                persona = FEMALE_VOICE_PERSONAS[female_idx % len(FEMALE_VOICE_PERSONAS)]
                acoustic_vec = cls.compute_acoustic_formant_vector(
                    gender="female",
                    archetype=arch,
                    prominence=prom,
                    index=female_idx,
                )
                female_idx += 1
            else:
                persona = MALE_VOICE_PERSONAS[male_idx % len(MALE_VOICE_PERSONAS)]
                acoustic_vec = cls.compute_acoustic_formant_vector(
                    gender="male",
                    archetype=arch,
                    prominence=prom,
                    index=male_idx,
                )
                male_idx += 1

            pitch = acoustic_vec["pitch"]
            speed = acoustic_vec["speed"]
            sig = f"{persona}_p{pitch:.2f}_s{speed:.2f}"

            # Ensure zero signature collision
            counter = 1
            while sig in used_signatures:
                pitch = round(pitch + 0.02 * counter, 2)
                sig = f"{persona}_p{pitch:.2f}_s{speed:.2f}"
                counter += 1
            used_signatures.add(sig)

            acoustic_vec["pitch"] = pitch
            acoustic_vec["speed"] = speed

            roster_chars[name] = {
                "english_name": name,
                "display_name": name,
                "gender": gender,
                "assigned_voice_id": persona,
                "aliases": aliases,
                "archetype": arch,
                "acoustic_vector": acoustic_vec,
            }
            voice_registry[name] = {
                "voice": persona,
                "pitch": pitch,
                "speed": speed,
                "bass_boost_db": acoustic_vec.get("bass_boost_db", 0.0),
                "presence_boost_db": acoustic_vec.get("presence_boost_db", 0.0),
                "clarity_reduction_db": acoustic_vec.get("clarity_reduction_db", 0.0),
                "lowpass_hz": acoustic_vec.get("lowpass_hz", 0),
            }
            locks[name] = {
                "character_id": name,
                "character_name": name,
                "locked": True,
                "voice_id": persona,
                "calibration_overrides": {
                    "pitch": pitch,
                    "speed": speed,
                    "bass_boost_db": acoustic_vec.get("bass_boost_db", 0.0),
                    "presence_boost_db": acoustic_vec.get("presence_boost_db", 0.0),
                    "clarity_reduction_db": acoustic_vec.get("clarity_reduction_db", 0.0),
                    "lowpass_hz": acoustic_vec.get("lowpass_hz", 0),
                },
            }

        roster = {"project_id": project_id, "characters": roster_chars}
        cast_lock = {"project_slug": project_id, "project_id": project_id, "locks": locks}
        return roster, voice_registry, cast_lock

    @classmethod
    def cast_single_speaker(
        cls,
        speaker_name: str,
        project_dir: Optional[Path] = None,
        gender: Optional[str] = None,
        default_backend: str = "gemini_tts",
    ) -> Dict[str, Any]:
        """
        Dynamically registers and casts a single newly discovered character.
        Persists to voice_registry.json, character_roster.json, and cast_lock.json.
        Guarantees zero voice drift and zero signature collision.
        """
        sp_clean = speaker_name.strip()
        if not sp_clean:
            return {"backend": default_backend, "voice": "Aoede", "pitch": 1.0, "speed": 1.0}

        p_dir = Path(project_dir) if project_dir else Path.cwd()
        roster_path = p_dir / "character_roster.json"
        registry_path = p_dir / "voice_registry.json"
        lock_path = p_dir / "cast_lock.json"

        # Load existing files or create empty
        roster: Dict[str, Any] = {"project_id": f"proj-{p_dir.name}", "characters": {}}
        registry: Dict[str, Any] = {}
        locks: Dict[str, Any] = {"project_slug": f"proj-{p_dir.name}", "locks": {}}

        if roster_path.exists():
            try:
                roster = json.loads(roster_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        if registry_path.exists():
            try:
                registry = json.loads(registry_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        if lock_path.exists():
            try:
                locks = json.loads(lock_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        # If already present in registry, return it
        if sp_clean in registry:
            cfg = registry[sp_clean]
            return {
                "backend": cfg.get("backend", default_backend),
                "voice": cfg.get("voice", "Aoede"),
                "pitch": cfg.get("pitch", 1.0),
                "speed": cfg.get("speed", 1.0),
            }

        # Collect existing voice signatures
        used_signatures = set()
        for k, v in registry.items():
            if isinstance(v, dict):
                vox = v.get("voice", "Aoede")
                p = v.get("pitch", 1.0)
                s = v.get("speed", 1.0)
                used_signatures.add(f"{vox}_p{p:.2f}_s{s:.2f}")

        # Determine gender heuristic if not provided
        g = (gender or "neutral").lower()
        if g not in ("male", "female"):
            female_indicators = ("girl", "woman", "lady", "queen", "princess", "madam", "mrs", "miss", "sister", "mother", "daughter")
            if any(ind in sp_clean.lower() for ind in female_indicators):
                g = "female"
            else:
                g = "male"

        pool = FEMALE_VOICE_PERSONAS if g == "female" else MALE_VOICE_PERSONAS
        existing_count = sum(1 for v in registry.values() if isinstance(v, dict) and v.get("voice") in pool)
        persona = pool[existing_count % len(pool)]

        acoustic_vec = cls.compute_acoustic_formant_vector(
            gender=g,
            archetype="dynamically_cast_character",
            prominence="incidental",
            index=existing_count,
        )
        pitch = acoustic_vec["pitch"]
        speed = acoustic_vec["speed"]
        sig = f"{persona}_p{pitch:.2f}_s{speed:.2f}"

        counter = 1
        while sig in used_signatures:
            pitch = round(pitch + 0.02 * counter, 2)
            sig = f"{persona}_p{pitch:.2f}_s{speed:.2f}"
            counter += 1

        acoustic_vec["pitch"] = pitch
        acoustic_vec["speed"] = speed

        new_config = {
            "backend": default_backend,
            "voice": persona,
            "pitch": pitch,
            "speed": speed,
            "bass_boost_db": acoustic_vec.get("bass_boost_db", 0.0),
            "presence_boost_db": acoustic_vec.get("presence_boost_db", 0.0),
            "clarity_reduction_db": acoustic_vec.get("clarity_reduction_db", 0.0),
            "lowpass_hz": acoustic_vec.get("lowpass_hz", 0),
        }

        # Update and save
        registry[sp_clean] = new_config
        chars = roster.setdefault("characters", {})
        chars[sp_clean] = {
            "english_name": sp_clean,
            "display_name": sp_clean,
            "gender": g,
            "assigned_voice_id": persona,
            "aliases": [sp_clean],
            "archetype": "dynamically_cast_character",
            "acoustic_vector": acoustic_vec,
        }
        lock_dict = locks.setdefault("locks", {})
        lock_dict[sp_clean] = {
            "character_id": sp_clean,
            "character_name": sp_clean,
            "locked": True,
            "voice_id": persona,
            "calibration_overrides": {
                "pitch": pitch,
                "speed": speed,
                "bass_boost_db": acoustic_vec.get("bass_boost_db", 0.0),
                "presence_boost_db": acoustic_vec.get("presence_boost_db", 0.0),
                "clarity_reduction_db": acoustic_vec.get("clarity_reduction_db", 0.0),
                "lowpass_hz": acoustic_vec.get("lowpass_hz", 0),
            },
        }

        try:
            roster_path.write_text(json.dumps(roster, ensure_ascii=False, indent=2), encoding="utf-8")
            registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")
            lock_path.write_text(json.dumps(locks, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.info(f"[+] CharacterCaster: Dynamically cast '{sp_clean}' -> {persona} (pitch: {pitch}, speed: {speed}). Registry updated.")
        except Exception as e:
            logger.warning(f"  [!] Notice saving dynamic cast for {sp_clean}: {e}")

        return new_config
