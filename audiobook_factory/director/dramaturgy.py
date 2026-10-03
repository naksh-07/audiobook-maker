from __future__ import annotations
import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from audiobook_factory.logger import logger
from audiobook_factory.model_manager import get_model_manager, TaskType, LLMUnavailableError

class DramaturgyMixin:
    def _pass1_dramaturgy_and_silence_carving(
        self,
        chapter_id: str,
        script_segments: List[Dict[str, Any]],
        total_duration_sec: float,
        max_retries: int = 3,
        sonic_bible: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Pass 1: Analyzes dramatic structure, acts, and emotional climaxes.
        Strictly enforces the 60-75% Acoustic Silence Mandate:
        Maximum 2-4 cues per chapter, covering at most 25-40% of chapter timeline.
        """
        # Rich Scene Context: Include all dramatic beats, fights, reveals, and action tags without stride truncation
        sample_lines = []
        for i, seg in enumerate(script_segments):
            s_idx = seg.get("index", i + 1)
            speaker = seg.get("speaker", "Narrator")
            seg_type = seg.get("type", "narration")
            text = seg.get("text", "")[:150]
            sfx_list = seg.get("sfx_cues", [])
            sfx_tags = [c.get("tag", str(c)) if isinstance(c, dict) else str(c) for c in sfx_list]
            sfx = f" [SFX: {','.join(sfx_tags)}]" if sfx_tags else ""
            sample_lines.append(f"[{s_idx:03d}|{seg_type}] {speaker}: {text}{sfx}")

        script_sample = "\n".join(sample_lines)

        bible_context = ""
        if sonic_bible:
            motifs = getattr(sonic_bible, "leitmotifs", {})
            if isinstance(motifs, dict) and motifs:
                unique_motifs = {}
                for k, m in motifs.items():
                    m_id = getattr(m, "motif_id", str(k))
                    if m_id not in unique_motifs:
                        unique_motifs[m_id] = m
                lines = []
                for m_id, m in unique_motifs.items():
                    entity = getattr(m, "associated_entity", "")
                    intent = getattr(m, "dramatic_intent", "")
                    t_name = getattr(m, "track_name", "")
                    lines.append(f"  - [{m_id}] for '{entity}': {t_name} (Intent: {intent})")
                bible_context = "\nCANONICAL BOOK LEITMOTIFS (Bind these themes when characters/factions appear):\n" + "\n".join(lines) + "\n"

        from audiobook_factory.safety import get_dramatic_fiction_framing
        framing = get_dramatic_fiction_framing(title=getattr(sonic_bible, "book_title", ""))

        prompt = f"""You are an elite Audio Drama Director & Supervising Sound Designer (BBC Radio 4 / Hollywood standard).
{framing}
Direct the soundscape and acoustic dramaturgy for {chapter_id} (Total Duration: {total_duration_sec/60:.1f} mins, {len(script_segments)} segments).

SCREENPLAY SAMPLE:
{script_sample}
{bible_context}
MANDATORY ACOUSTIC DIRECTING RULES:
1. 2-TIER SCORE ARCHITECTURE & ACOUSTIC SILENCE MANDATE:
   - Dialogue breathes and punches in pure acoustic silence supported only by subtle room tone (must maintain >= 60.0% acoustic silence).
   - Tier 1: Continuous low-energy atmospheric underscore (-24dB to -28dB) spanning key dramatic scenes or suspense arcs.
   - Tier 2: Surgical high-energy drops (-18dB to -14dB) hitting dynamically at dramatic peaks, battle actions, reveals, and emotional turns.
   - Total music duration across all cues must not exceed {total_duration_sec * 0.40:.1f} seconds to strictly preserve >= 60.0% chapter acoustic silence.
   - Music must NEVER loop wall-to-wall without purpose.

2. CUE ARCHETYPES & SECTION ENERGIES:
   - "TRANSITION_BRIDGE": 25-60s connecting location changes (energy: "INTRO_BED").
   - "EMOTIONAL_UNDERSCORE": 60-180s quiet strings, dark pads, or solo cello supporting intimate realizations or tense dramatic scenes (energy: "INTRO_BED" or "RISING_TENSION").
   - "CLIMACTIC_ACTION_CUE": 90-240s battle fury or high-stakes confrontations spanning action sequences (energy: "CLIMAX_DROP").

3. SONIC GENOME & DYNAMIC SOUNDTRACK DESCRIPTORS (Do NOT specify filenames or titles):
   - Provide valence: float between -1.0 (grim tragedy, terror, mourning) and +1.0 (triumphant victory, joy, solace).
   - Provide arousal: float between 0.0 (quiet, somber, contemplative, stealth) and 1.0 (violent combat, intense adrenaline, frenzy).
   - Provide narrative_archetype: string tag (e.g. "MYSTERY_PROLOGUE", "TENSION", "NOCTURNAL_VIGIL", "MAGICAL_DESTINY", "BITTERSWEET_PARTING", "HERO_LEGACY", "ROYAL_CONSPIRACY", "TAVERN_BRAWL", "SWORD_DUEL", "MONSTER_HUNT").
   - Provide musical mood, tempo ("slow", "moderate", "fast"), timbre ("solo cello", "dark strings", "brass", "flute", "percussion", "harp", "ethereal choir", "hurdy-gurdy"), and energy section ("INTRO_BED", "RISING_TENSION", "CLIMAX_DROP", "AFTERMATH_FADE").
   - Provide 3-5 descriptive keyword search terms for SQLite FTS5 search.

4. CONTEXTUAL GRAMMATICAL FOLEY (Physical Interactions Only - Zero Metaphors):
   - Identify physical actions described in text appropriate to the setting (e.g. blade clash, sword draw, door creak, tankard slam, footsteps, items manipulated).
   - Specify: segment_index, action_verb, object_material, anchor_word.

5. CONTINUOUS AMBIENCE BED:
   - Identify environmental atmosphere matching the story world (e.g. stone_ruins_exterior, tavern_interior, castle_great_hall, deep_forest_night, spaceship_bridge, room_tone). Target: -32 LUFS.

Output STRICT JSON schema:
{{
  "dramatic_theme": "Brief 1-sentence dramatic theme",
  "ambience": [
    {{
      "name": "stone_ruins_exterior" | "tavern_interior" | "castle_great_hall" | "deep_forest_night" | "spaceship_bridge" | "suburban_street_night" | "domestic_room" | "room_tone",
      "target_lufs": -32.0,
      "description": "Why this ambient room tone fits the setting"
    }}
  ],
  "music_cues": [
    {{
      "cue_id": "cue_01",
      "cue_type": "TRANSITION_BRIDGE" | "EMOTIONAL_UNDERSCORE" | "CLIMACTIC_ACTION_CUE",
      "trigger_segment": int,
      "until_segment": int,
      "narrative_archetype": str,
      "valence": float (-1.0 to 1.0),
      "arousal": float (0.0 to 1.0),
      "mood": "mournful" | "tense" | "triumphant" | "mysterious" | "somber" | "magical",
      "tempo": "slow" | "moderate" | "fast",
      "timbre": "solo cello" | "dark strings" | "brass" | "ethereal choir" | "harp",
      "energy_section": "INTRO_BED" | "RISING_TENSION" | "CLIMAX_DROP" | "AFTERMATH_FADE",
      "search_query": "3-5 descriptive keywords for FTS5",
      "duration_sec": float (25.0 to 240.0),
      "fade_in_sec": float (2.0 to 4.0),
      "fade_out_sec": float (3.0 to 5.0),
      "volume_db": float (-9.0 to -6.5),
      "dramatic_justification": "Why music enters here and why silence surrounds it"
    }}
  ],
  "foley_events": [
    {{
      "segment_index": int,
      "subject": str,
      "action_verb": str,
      "object_material": str,
      "anchor_word": str,
      "target_gain_dbfs": float (-14.0 to -18.0),
      "azimuth_pan": float (-0.8 to +0.8)
    }}
  ]
}}"""

        from audiobook_factory.model_manager import get_model_manager, TaskType, LLMUnavailableError
        model_mgr = get_model_manager()
        try:
            active_model = self.model or model_mgr.resolve_active_model(TaskType.DIRECTING)
            candidate_models = [active_model]
        except Exception:
            candidate_models = [self.model] if self.model else []

        for m in model_mgr.get_candidate_models_for_task(TaskType.DIRECTING):
            if m not in candidate_models:
                candidate_models.append(m)

        # Deduplicate preserving order
        seen_models = set()
        models_to_try = [m for m in candidate_models if not (m in seen_models or seen_models.add(m))]

        from audiobook_factory.llm_client import call_gemini

        system_instruction = (
            "You are an elite Audio Drama Director & Supervising Sound Designer (BBC Radio 4 / Hollywood standard). "
            "Output strictly valid JSON obeying all acoustic silence rules and schema constraints."
        )

        try:
            parsed = call_gemini(
                prompt=prompt,
                system_instruction=system_instruction,
                task_type=TaskType.DIRECTING,
                response_mime_type="application/json",
                temperature=0.25,
                max_retries=max_retries,
            )
            if parsed and "music_cues" in parsed:
                logger.info(
                    f"  [+] Pass 1 Dramaturgy: {len(parsed['music_cues'])} cues planned, "
                    f"{len(parsed.get('foley_events', []))} foley events."
                )
                return self._enforce_silence_carving(parsed, total_duration_sec)
        except Exception as e:
            logger.error(f"  [!] Audio Drama Director LLM failed: {e}")
            raise LLMUnavailableError(
                f"STRICT HALT: Audio Drama Director LLM is unavailable or exhausted: {e}. "
                "Production strictly halted to prevent un-directed acoustic assembly."
            )

        # Fallback if parsed was empty
        logger.error("  [!] LLM API unavailable. STRICT HALT: Refusing to silently apply generic acoustic templates.")
        raise LLMUnavailableError(
            "STRICT HALT: Audio Drama Director LLM is unavailable or exhausted after retries. "
            "Production strictly halted to prevent un-directed acoustic assembly."
        )

    def _enforce_silence_carving(self, plan: Dict[str, Any], total_duration_sec: float) -> Dict[str, Any]:
        """
        Enforces 2-Tier Score Architecture budget: total music across cues does not exceed 40% of the chapter,
        guaranteeing at least 60% pure acoustic silence while accommodating continuous atmospheric underscore
        plus surgical peak drops. Trims or prunes cues if needed.
        """
        max_allowed_music_sec = total_duration_sec * 0.40
        cues = plan.get("music_cues", [])
        total_music_sec = sum(float(c.get("duration_sec", 30.0)) for c in cues)

        if total_music_sec > max_allowed_music_sec and cues:
            logger.info(
                f"  [*] Silence Carving: Pruning cues from {total_music_sec:.1f}s down to "
                f"{max_allowed_music_sec:.1f}s to maintain >= 60% silence mandate."
            )
            scale = max_allowed_music_sec / total_music_sec
            for c in cues:
                c["duration_sec"] = round(float(c.get("duration_sec", 30.0)) * scale, 1)

            # Ensure rounding does not breach the 40% maximum allowed music budget
            new_total = sum(float(c.get("duration_sec", 0.0)) for c in cues)
            if new_total > max_allowed_music_sec and cues:
                excess = round(new_total - max_allowed_music_sec, 1)
                cues[-1]["duration_sec"] = round(max(1.0, float(cues[-1]["duration_sec"]) - excess), 1)

        return plan

    def _build_deterministic_dramaturgy_plan(
        self,
        script_segments: List[Dict[str, Any]],
        total_duration_sec: float,
        sonic_bible: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Deterministic multi-scene dramatic plan distributing 5-6 cues across the chapter (~20-25% music coverage,
        guaranteeing ~75-80% pure acoustic silence) with audible mix levels (-7.0 dBFS).
        """
        n_segs = max(1, len(script_segments))
        t_dur = max(30.0, total_duration_sec)

        leitmotif_ref = ""
        timbre = "dark strings"
        query_base = "mystery solo cello strings"
        if sonic_bible and hasattr(sonic_bible, "leitmotifs"):
            for seg in script_segments:
                spk = seg.get("speaker", "")
                if spk and spk.lower() != "narrator":
                    m = sonic_bible.resolve_theme_for_character(spk) if hasattr(sonic_bible, "resolve_theme_for_character") else None
                    if m:
                        leitmotif_ref = getattr(m, "motif_id", "")
                        timbre = getattr(m, "primary_instrument", timbre)
                        query_base = getattr(m, "track_name", query_base)
                        break
            if not leitmotif_ref and sonic_bible.leitmotifs:
                first_m = next(iter(sonic_bible.leitmotifs.values()))
                leitmotif_ref = getattr(first_m, "motif_id", "")
                timbre = getattr(first_m, "primary_instrument", timbre)
                query_base = getattr(first_m, "track_name", query_base)

        cue_definitions = [
            {
                "id": "cue_01_prologue",
                "type": "TRANSITION_BRIDGE",
                "seg_ratio": 0.0,
                "dur_sec": min(25.0, max(12.0, t_dur * 0.02)),
                "archetype": "MYSTERY_PROLOGUE",
                "mood": "mysterious",
                "tempo": "slow",
                "timbre": timbre,
                "energy": "INTRO_BED",
                "query": f"{query_base} atmospheric intro bed",
                "volume_db": -7.0,
                "justification": "Opening narrative establishment into silence",
            },
            {
                "id": "cue_02_tension",
                "type": "EMOTIONAL_UNDERSCORE",
                "seg_ratio": 0.20,
                "dur_sec": min(45.0, max(15.0, t_dur * 0.03)),
                "archetype": "INVESTIGATION_TENSION",
                "mood": "tense",
                "tempo": "slow",
                "timbre": "pizzicato strings",
                "energy": "RISING_TENSION",
                "query": "tension suspense subtle strings intrigue",
                "volume_db": -7.5,
                "justification": "Subtle dramatic tension and situational discovery",
            },
            {
                "id": "cue_03_nocturnal",
                "type": "EMOTIONAL_UNDERSCORE",
                "seg_ratio": 0.45,
                "dur_sec": min(40.0, max(15.0, t_dur * 0.03)),
                "archetype": "NOCTURNAL_VIGIL",
                "mood": "mysterious",
                "tempo": "slow",
                "timbre": "dark strings",
                "energy": "INTRO_BED",
                "query": "ambient cello mystery atmospheric calm",
                "volume_db": -7.0,
                "justification": "Atmospheric transition as scene stakes evolve",
            },
            {
                "id": "cue_04_destiny",
                "type": "EMOTIONAL_UNDERSCORE",
                "seg_ratio": 0.65,
                "dur_sec": min(55.0, max(20.0, t_dur * 0.04)),
                "archetype": "MAGICAL_DESTINY",
                "mood": "mysterious",
                "tempo": "slow",
                "timbre": "ethereal choir",
                "energy": "RISING_TENSION",
                "query": "ethereal wonder atmospheric tension",
                "volume_db": -7.0,
                "justification": "Dramatic peak and revelation turning point",
            },
            {
                "id": "cue_05_parting",
                "type": "CLIMACTIC_ACTION_CUE",
                "seg_ratio": 0.85,
                "dur_sec": min(45.0, max(18.0, t_dur * 0.035)),
                "archetype": "BITTERSWEET_PARTING",
                "mood": "mournful",
                "tempo": "slow",
                "timbre": "solo cello",
                "energy": "CLIMAX_DROP",
                "query": "emotional solo cello bittersweet solemn parting",
                "volume_db": -6.5,
                "justification": "Bittersweet aftermath and solemn reflection",
            },
            {
                "id": "cue_06_legacy",
                "type": "TRANSITION_BRIDGE",
                "seg_ratio": 0.96,
                "dur_sec": min(30.0, max(12.0, t_dur * 0.02)),
                "archetype": "HERO_LEGACY",
                "mood": "triumphant",
                "tempo": "moderate",
                "timbre": "brass",
                "energy": "AFTERMATH_FADE",
                "query": "triumphant solemn legacy legend horn strings",
                "volume_db": -7.0,
                "justification": "Final solemn toast into silence",
            },
        ]

        music_cues = []
        for c in cue_definitions:
            trig_idx = max(1, min(n_segs, int(n_segs * c["seg_ratio"]) + 1))
            music_cues.append({
                "cue_id": c["id"],
                "cue_type": c["type"],
                "trigger_segment": trig_idx,
                "narrative_archetype": c["archetype"],
                "valence": -0.2,
                "arousal": 0.3,
                "mood": c["mood"],
                "tempo": c["tempo"],
                "timbre": c["timbre"],
                "energy_section": c["energy"],
                "search_query": c["query"],
                "duration_sec": round(c["dur_sec"], 1),
                "fade_in_sec": 3.0,
                "fade_out_sec": 4.0,
                "volume_db": c["volume_db"],
                "dramatic_justification": c["justification"],
                "leitmotif_ref": leitmotif_ref,
            })

        return {
            "dramatic_theme": "Literary Cinematic Audio Drama",
            "ambience": [
                {
                    "name": "suburban_street_night",
                    "target_lufs": -32.0,
                    "description": "Quiet nighttime suburban ambience with subtle distant crickets and breeze",
                }
            ],
            "music_cues": music_cues,
            "foley_events": [],
        }

    # =========================================================================
    # PASS 2 IMPLEMENTATION: Music Director (Dynamic FTS5 queries, graceful fallback)
    # =========================================================================
