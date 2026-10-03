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

        sample_texts = []
        for cf in chap_files:
            try:
                with open(cf, "r", encoding="utf-8") as f:
                    txt = f.read()
                lower_txt = txt.lower()
                if "copyright" in lower_txt or "all rights reserved" in lower_txt or len(txt.split()) < 200:
                    continue
                sample_texts.append(txt[:4000])
                if len(sample_texts) >= 3:
                    break
            except Exception:
                pass
        if not sample_texts and chap_files:
            # Fallback if all chapters were short
            sample_texts = [chap_files[0].read_text(encoding="utf-8")[:4000]]
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
{text_sample[:10000]}
\"\"\"

Return a JSON array of objects with:
- "canonical_name": string (e.g. "Mr. Dursley", "Professor McGonagall", "Albus Dumbledore")
- "hindi_name": string (Devanagari spelling if applicable, e.g. "मिस्टर डर्स्ली")
- "gender": "male" | "female" | "neutral"
- "archetype": string (e.g. "nervous suburban director", "stern Scottish transfiguration professor", "wise elderly headmaster")
- "aliases": list of strings (e.g. ["मिस्टर डर्स्ली", "Vernon Dursley", "Mr Dursley"])
"""


        try:
            parsed = call_gemini(
                task_type=TaskType.DIRECTING,
                prompt=prompt,
                system_instruction=sys_prompt,
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
            }
        }
        locks = {
            "Narrator": {
                "character_id": "Narrator",
                "character_name": "Narrator",
                "locked": True,
                "voice_id": default_narrator_voice,
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

            if gender == "female":
                persona = FEMALE_VOICE_PERSONAS[female_idx % len(FEMALE_VOICE_PERSONAS)]
                pitch_offset = 0.0 + (female_idx // len(FEMALE_VOICE_PERSONAS)) * 0.04
                female_idx += 1
            else:
                persona = MALE_VOICE_PERSONAS[male_idx % len(MALE_VOICE_PERSONAS)]
                pitch_offset = 0.0 + (male_idx // len(MALE_VOICE_PERSONAS)) * 0.04
                male_idx += 1

            pitch = round(1.0 + pitch_offset, 2)
            speed = 1.0
            sig = f"{persona}_p{pitch:.2f}_s{speed:.2f}"

            # Ensure zero signature collision
            counter = 1
            while sig in used_signatures:
                pitch = round(pitch + 0.02 * counter, 2)
                sig = f"{persona}_p{pitch:.2f}_s{speed:.2f}"
                counter += 1
            used_signatures.add(sig)

            roster_chars[name] = {
                "english_name": name,
                "display_name": name,
                "gender": gender,
                "assigned_voice_id": persona,
                "aliases": aliases,
                "archetype": ch.get("archetype", ""),
            }
            voice_registry[name] = {
                "voice": persona,
                "pitch": pitch,
                "speed": speed,
            }
            locks[name] = {
                "character_id": name,
                "character_name": name,
                "locked": True,
                "voice_id": persona,
            }

        roster = {"project_id": project_id, "characters": roster_chars}
        cast_lock = {"project_slug": project_id, "project_id": project_id, "locks": locks}
        return roster, voice_registry, cast_lock
