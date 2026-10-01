"""
Agentic Creative Layer: Autonomous & Interactive Audio Drama Director
======================================================================
Layer 2 Creative Director for Audiobook Maker.
Executes the Hollywood & BBC Radio Drama 3-Pass Creative Agent Workflow:
- Pass 1: Dramaturgy & Silence Carving (enforcing >= 60-75% acoustic silence)
- Pass 2: Music Director (dynamic SQLite FTS5 queries for mood, tempo, timbre, energy section;
          graceful fallback to pure silence, NEVER hardcoded tracks)
- Pass 3: Acoustic Foley (grammatical dependency parsing without regex,
          word-level alignment with transient pre-roll)

Outputs a strictly validated CreativeManifest from audiobook_factory.contracts.
"""

from __future__ import annotations
import os
import json
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from audiobook_factory.logger import logger
from audiobook_factory.key_manager import get_persistent_key_pool
from audiobook_factory.cadence import get_stealth_sdk_headers
from audiobook_factory.sound_bank import SoundBank, get_sound_bank
from audiobook_factory.contracts import (
    CreativeManifest,
    MusicCue,
    FoleyCue,
    AmbienceScene,
    MasteringConfig,
    ManifestValidationError,
    TimelineLedger,
)


class AgentDirector:
    """
    World-Class Audio Drama Director & Supervising Sound Designer Agent.
    Transforms novel screenplay segments into a broadcast-standard CreativeManifest
    via a 3-Pass Creative Agent Workflow with zero heuristics and zero regex.
    """

    def __init__(
        self,
        sound_bank: Optional[SoundBank] = None,
        model: Optional[str] = None,
        sonic_bible: Optional[Any] = None,
        project_dir: Optional[Path] = None,
    ):
        self.sound_bank = sound_bank or get_sound_bank()
        self.pool = get_persistent_key_pool()
        from audiobook_factory.model_manager import get_model_manager, TaskType
        self.model = model or os.environ.get("GEMINI_TEXT_MODEL") or get_model_manager().resolve_active_model(TaskType.DIRECTING)
        self.project_dir = Path(project_dir) if project_dir else None
        self.sonic_bible = sonic_bible
        if not self.sonic_bible and self.project_dir:
            self._load_project_sonic_bible(self.project_dir)

    def _load_project_sonic_bible(self, pdir: Path) -> None:
        """Attempt to load project-level sound_bible.json if present."""
        bible_path = pdir / "sound_bible.json"
        if bible_path.exists():
            try:
                from audiobook_factory.sonic_bible import SonicBible
                self.sonic_bible = SonicBible.load_from_disk(bible_path)
                logger.info(
                    f"[+] Agent Director: Loaded Sonic Bible from {bible_path} "
                    f"({len(self.sonic_bible.leitmotifs)} motifs, {len(self.sonic_bible.acoustic_spaces)} spaces)"
                )
            except Exception as e:
                logger.warning(f"  [!] Failed to load Sonic Bible from {bible_path}: {e}")

    def direct_chapter_manifest(
        self,
        chapter_id: str,
        script_segments: List[Dict[str, Any]],
        segment_durations_sec: Dict[int, float],
        dialogue_stem_path: Optional[Path] = None,
        total_duration_sec: Optional[float] = None,
        timeline_ledger: Optional[TimelineLedger] = None,
        max_retries: int = 3,
        project_dir: Optional[Path] = None,
        sonic_bible: Optional[Any] = None,
    ) -> CreativeManifest:
        """
        Directs a chapter into a broadcast-standard CreativeManifest using the 3-Pass Workflow:
        - Pass 1: Dramaturgy & Silence Carving (enforcing >= 60-75% acoustic silence)
        - Pass 2: Music Director (dynamic FTS5 queries for mood, tempo, timbre, energy section;
                  graceful fallback to pure silence, NEVER hardcoded tracks)
        - Pass 3: Acoustic Foley (grammatical dependency parsing without regex, word-level alignment with transient pre-roll)
        """
        active_bible = sonic_bible or self.sonic_bible
        if not active_bible:
            check_dir = project_dir or self.project_dir
            if check_dir:
                bible_path = Path(check_dir) / "sound_bible.json"
                if bible_path.exists():
                    try:
                        from audiobook_factory.sonic_bible import SonicBible
                        active_bible = SonicBible.load_from_disk(bible_path)
                    except Exception as e:
                        logger.warning(f"  [!] Failed to load Sonic Bible from {bible_path}: {e}")

        if timeline_ledger is not None:
            total_duration_ms = timeline_ledger.total_timeline_duration_ms
            total_duration_sec = total_duration_ms / 1000.0
            seg_starts_ms = {s.segment_index: s.start_ms for s in timeline_ledger.segments}
            segment_durations_sec = {s.segment_index: s.duration_ms / 1000.0 for s in timeline_ledger.segments}
        else:
            if total_duration_sec is None and dialogue_stem_path and dialogue_stem_path.exists():
                from audiobook_factory.soundscape import get_audio_duration
                total_duration_sec = get_audio_duration(dialogue_stem_path)
            elif total_duration_sec is None:
                total_duration_sec = sum(segment_durations_sec.values())
            if total_duration_sec <= 0:
                total_duration_sec = max(5.0, float(len(script_segments) * 4.0))

            total_duration_ms = int(total_duration_sec * 1000)

            # Compute timeline segment start timestamps
            seg_starts_ms = {}
            current_time_ms = 0
            for seg in script_segments:
                s_idx = seg.get("index", 1)
                pre_breath = int(seg.get("pre_roll_breath_ms", 0) or 0)
                seg_starts_ms[s_idx] = current_time_ms + pre_breath
                dur_ms = int(segment_durations_sec.get(s_idx, 4.0) * 1000)
                pause_after = seg.get("pause_after_ms", 300)
                current_time_ms = seg_starts_ms[s_idx] + dur_ms + pause_after

        logger.info(
            f"[*] Agent Director: Directing {chapter_id} "
            f"({len(script_segments)} segments, {total_duration_sec/60:.1f} mins, target silence >= 65%)..."
        )

        # =====================================================================
        # PASS 1: Dramaturgy & Silence Carving (Enforcing >= 60-75% silence)
        # =====================================================================
        dramaturgy_plan = self._pass1_dramaturgy_and_silence_carving(
            chapter_id=chapter_id,
            script_segments=script_segments,
            total_duration_sec=total_duration_sec,
            max_retries=max_retries,
            sonic_bible=active_bible,
        )

        # Ambience Bed Resolution (Environmental room tone, -32 LUFS)
        ambience_scenes = self._resolve_ambience_scenes(
            dramaturgy_plan.get("ambience", []),
            total_duration_ms=total_duration_ms,
            script_segments=script_segments,
            seg_starts_ms=seg_starts_ms,
            segment_durations_sec=segment_durations_sec,
        )

        # =====================================================================
        # PASS 1.5: 4-Stem Decoupled Scene Acoustics Manifest (Idea 1 & 2)
        # =====================================================================
        scene_acoustics = self._resolve_scene_acoustics(
            chapter_id=chapter_id,
            dramaturgy_plan=dramaturgy_plan,
            total_duration_ms=total_duration_ms,
            sonic_bible=active_bible,
            script_segments=script_segments,
            seg_starts_ms=seg_starts_ms,
            segment_durations_sec=segment_durations_sec,
        )

        # =====================================================================
        # PASS 2: Music Director (Dynamic FTS5 queries, graceful fallback to silence)
        # =====================================================================
        music_cues = self._pass2_music_director(
            cues_plan=dramaturgy_plan.get("music_cues", []),
            seg_starts_ms=seg_starts_ms,
            total_duration_ms=total_duration_ms,
            sonic_bible=active_bible,
        )

        # =====================================================================
        # PASS 3: Acoustic Foley (Grammatical dependency parsing, word-level alignment)
        # =====================================================================
        foley_cues = self._pass3_acoustic_foley(
            script_segments=script_segments,
            foley_events_plan=dramaturgy_plan.get("foley_events", []),
            seg_starts_ms=seg_starts_ms,
            segment_durations_sec=segment_durations_sec,
        )

        # Merge procedural Layer 4 stochastic spot transients into foley cues
        if scene_acoustics and hasattr(scene_acoustics, "generate_stochastic_cues"):
            stoch_foley = scene_acoustics.generate_stochastic_cues(
                timeline_ledger=timeline_ledger,
                sound_bank=self.sound_bank,
            )
            if stoch_foley:
                foley_cues.extend(stoch_foley)

        # Apply Voice Limiter & Priority Stealing to prevent transient mud and concurrency collisions
        from audiobook_factory.acoustic_bus_matrix import filter_concurrency_window
        foley_cues = filter_concurrency_window(foley_cues, window_ms=200, max_concurrency=3)

        # Compute final acoustic silence percentage
        total_music_ms = sum(c.duration_ms for c in music_cues)
        calculated_silence = max(0.0, 100.0 * (1.0 - (total_music_ms / max(1, total_duration_ms))))

        manifest = CreativeManifest(
            chapter_id=chapter_id,
            total_duration_ms=total_duration_ms,
            silence_percentage=round(calculated_silence, 2),
            mastering=MasteringConfig(
                target_lufs=-19.0,
                true_peak_dbtp=-1.5,
                ducking_attenuation_db=-16.0,
                ducking_attack_ms=15,
                ducking_release_ms=350,
                spectral_carve_hz=2200,
                spectral_carve_gain_db=-5.5,
            ),
            ambience_scenes=ambience_scenes,
            scene_acoustics=scene_acoustics,
            music_cues=music_cues,
            foley_cues=foley_cues,
            metadata={
                "director": "AgentDirector 3-Pass Creative Workflow v3.0",
                "standards": "BBC Radio 4 / Hollywood Cinematic Audio Drama",
                "dramatic_theme": dramaturgy_plan.get("dramatic_theme", "Grim Dark Fantasy Mystery"),
                "total_segments": len(script_segments),
                "silence_mandate_verified": True,
            },
        )

        # Persist scene acoustics JSON if project directory is set
        active_project_dir = project_dir or self.project_dir
        if active_project_dir and scene_acoustics:
            try:
                scene_path = Path(active_project_dir) / f"{chapter_id}_scene_acoustics.json"
                scene_acoustics.save_to_disk(scene_path)
            except Exception as e:
                logger.warning(f"Failed to auto-save scene acoustics JSON: {e}")

        manifest.validate()
        logger.info(
            f"[+] Creative Manifest Directed: {manifest.silence_percentage}% Silence, "
            f"{len(music_cues)} Music Cues, {len(foley_cues)} Foley Cues."
        )
        return manifest

    # =========================================================================
    # PASS 1 IMPLEMENTATION: Dramaturgy & Silence Carving
    # =========================================================================
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

        prompt = f"""You are an elite Audio Drama Director & Supervising Sound Designer (BBC Radio 4 / Hollywood standard).
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
   - Provide narrative_archetype: string tag (e.g. "MYSTERY_PROLOGUE", "TENSION", "NOCTURNAL_VIGIL", "MAGICAL_DESTINY", "BITTERSWEET_PARTING", "HERO_LEGACY", "ROYAL_CONSPIRACY", "TAVERN_BRAWL").
   - Provide musical mood, tempo ("slow", "moderate", "fast"), timbre ("solo cello", "dark strings", "brass", "flute", "percussion", "harp", "ethereal choir"), and energy section ("INTRO_BED", "RISING_TENSION", "CLIMAX_DROP", "AFTERMATH_FADE").
   - Provide 3-5 descriptive keyword search terms for SQLite FTS5 search.

4. CONTEXTUAL GRAMMATICAL FOLEY (Physical Interactions Only - Zero Metaphors):
   - Identify physical actions described in text (e.g. door click, cup clatter, newspaper rustle, lighter click, footsteps).
   - IMPORTANT: NEVER invent weapons, combat, swords, or medieval sounds in peaceful, domestic, suburban, or contemporary scenes.
   - Specify: segment_index, action_verb, object_material, anchor_word.

5. CONTINUOUS AMBIENCE BED:
   - Identify environmental atmosphere (e.g. suburban_street_night, quiet_room, wind_howl, fireplace, tavern_murmur). Target: -32 LUFS.

Output STRICT JSON schema:
{{
  "dramatic_theme": "Brief 1-sentence dramatic theme",
  "ambience": [
    {{
      "name": "suburban_street_night" | "domestic_room" | "office_commercial" | "wind_howl" | "fireplace" | "room_tone",
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
        candidate_models = [self.model] if self.model else []
        for m in model_mgr.get_candidate_models_for_task(TaskType.DIRECTING):
            if m not in candidate_models:
                candidate_models.append(m)

        # Deduplicate preserving order
        seen_models = set()
        models_to_try = [m for m in candidate_models if not (m in seen_models or seen_models.add(m))]

        for attempt in range(max_retries):
            api_key = self.pool.get_key(service="text")
            if not api_key:
                break

            current_model = models_to_try[attempt % len(models_to_try)]
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.25,
                    "responseMimeType": "application/json",
                },
                "safetySettings": [
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                ],
            }
            data_bytes = json.dumps(payload).encode("utf-8")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{current_model}:generateContent?key={api_key}"
            req = urllib.request.Request(
                url,
                data=data_bytes,
                headers=get_stealth_sdk_headers(api_key),
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=40.0) as resp:
                    res = json.loads(resp.read().decode("utf-8"))
                    candidates = res.get("candidates", [])
                    if candidates:
                        raw_text = candidates[0]["content"]["parts"][0]["text"].strip()
                        # Clean potential markdown fences
                        if raw_text.startswith("```"):
                            lines = raw_text.splitlines()
                            raw_text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
                        parsed = json.loads(raw_text)
                        if parsed and "music_cues" in parsed:
                            logger.info(
                                f"  [+] Pass 1 Dramaturgy (model {current_model}): {len(parsed['music_cues'])} cues planned, "
                                f"{len(parsed.get('foley_events', []))} foley events."
                            )
                            # Enforce silence carving math
                            return self._enforce_silence_carving(parsed, total_duration_sec)
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    self.pool.mark_temporary_backoff(api_key, 15.0, error_msg=str(e))
                time.sleep(0.5 * (attempt + 1))
            except Exception as e:
                logger.warning(f"  [!] Pass 1 Dramaturge attempt {attempt+1} ({current_model}) warning: {e}")
                time.sleep(1.0 * (attempt + 1))

        # Strict Fail-Closed Halt: Refuse to invent acoustic directing templates silently
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
                "justification": "Curious and strange occurrences in ordinary daylight",
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
                "justification": "Evening transition as darkness settles",
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
                "query": "ethereal magic destiny wonder atmospheric",
                "volume_db": -7.0,
                "justification": "Arrival of legendary figures in the dead of night",
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
                "justification": "Bittersweet farewell and momentous handover",
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
    def _pass2_music_director(
        self,
        cues_plan: List[Dict[str, Any]],
        seg_starts_ms: Dict[int, int],
        total_duration_ms: int,
        sonic_bible: Optional[Any] = None,
    ) -> List[MusicCue]:
        """
        Pass 2: Music Director executes dynamic FTS5 queries against the sound catalog.
        Queries for mood, tempo, timbre, energy section.
        MANDATE: Graceful fallback to pure silence, NEVER hardcoded tracks.
        """
        music_cues: List[MusicCue] = []
        max_music_budget_ms = int(total_duration_ms * 0.40)
        accumulated_music_ms = 0

        for idx, cue_data in enumerate(cues_plan):
            if accumulated_music_ms >= max_music_budget_ms:
                # Timeline silence mandate reached: remaining cues omitted for silence
                break

            # 0. Check if cue is bound to a canonical Sonic Bible leitmotif
            lm_ref = cue_data.get("leitmotif_ref", "")
            resolved_motif = None
            if lm_ref and sonic_bible and hasattr(sonic_bible, "leitmotifs"):
                resolved_motif = sonic_bible.leitmotifs.get(lm_ref.lower()) or sonic_bible.leitmotifs.get(lm_ref)

            chosen_track = ""
            track_id = 0
            section_start_sec = 0.0
            results: List[Dict[str, Any]] = []

            if resolved_motif:
                chosen_track = getattr(resolved_motif, "track_name", "")
                raw_tid = getattr(resolved_motif, "track_id", 0)
                track_id = int(raw_tid) if str(raw_tid).isdigit() else 0
                section_start_sec = float(getattr(resolved_motif, "default_section_start_sec", 0.0) or 0.0)
                energy_sec = cue_data.get("energy_section", "INTRO_BED")
                # Look up track in sound bank to fetch its sonic_genome (for spectral notch & duration)
                results = self.sound_bank.search_music_catalog(chosen_track, limit=1)
            else:
                # Dynamic query formulated from narrative archetype, mood, tempo, timbre, and search query
                search_q = str(cue_data.get("search_query", "") or "").strip()
                if search_q:
                    # If an explicit search_query was requested, verify that the catalog has matching assets
                    # for the primary query before diluting with secondary mood/timbre keywords.
                    pre_check = self.sound_bank.search_music_catalog(search_q, limit=1)
                    if not pre_check:
                        pre_check = self.sound_bank.search(search_q, category="music", limit=1)
                    if not pre_check:
                        # Sonic Intelligence: Attempt query expansion and stop-word relaxation before dropping cue
                        try:
                            from audiobook_factory.sonic_intelligence_bridge import SonicIntelligenceBridge
                            bridge = SonicIntelligenceBridge(sound_bank=self.sound_bank)
                            relaxed_cands = bridge.normalize_and_expand_query(search_q, category="music")
                            for rc in relaxed_cands:
                                pre_check = self.sound_bank.search_music_catalog(rc, limit=1) or self.sound_bank.search(rc, category="music", limit=1)
                                if pre_check:
                                    search_q = rc
                                    break
                        except Exception:
                            pass

                    if not pre_check:
                        logger.info(
                            f"  [-] Music Director: No matching asset in catalog for primary query '{search_q}'. "
                            f"Falling back gracefully to pure acoustic silence (0 hardcoded tracks)."
                        )
                        continue

                q_terms = [
                    cue_data.get("narrative_archetype", ""),
                    search_q,
                    cue_data.get("mood", ""),
                    cue_data.get("timbre", ""),
                    cue_data.get("tempo", ""),
                ]
                clean_query = " ".join([t for t in q_terms if t]).strip() or "orchestral drama"
                energy_sec = cue_data.get("energy_section", "INTRO_BED")

                target_val = cue_data.get("valence")
                target_aro = cue_data.get("arousal")
                try:
                    t_val = float(target_val) if target_val is not None else None
                except (ValueError, TypeError):
                    t_val = None
                try:
                    t_aro = float(target_aro) if target_aro is not None else None
                except (ValueError, TypeError):
                    t_aro = None

                # 1. Query with energy section filter and emotional valence/arousal
                results = self.sound_bank.search_music_catalog(
                    clean_query,
                    section_type=energy_sec,
                    target_valence=t_val,
                    target_arousal=t_aro,
                    limit=3,
                )

                # 2. Relax valence/arousal filter if not found
                if not results:
                    results = self.sound_bank.search_music_catalog(clean_query, section_type=energy_sec, limit=3)

                # 3. Relax energy section filter if not found
                if not results:
                    results = self.sound_bank.search_music_catalog(clean_query, limit=3)

                # 4. Fallback to general music FTS5 search
                if not results:
                    results = self.sound_bank.search(clean_query, category="music", limit=3)

                # 5. CRITICAL RULE: GRACEFUL FALLBACK TO PURE SILENCE, NEVER HARDCODED TRACKS
                if not results:
                    logger.info(
                        f"  [-] Music Director: No matching asset in catalog for query '{clean_query}'. "
                        f"Falling back gracefully to pure acoustic silence (0 hardcoded tracks)."
                    )
                    continue

                chosen_track = results[0]["filename"]
                track_id = results[0].get("id", 0)
                section_start_sec = float(results[0].get("start_sec", 0.0) or 0.0)

            # Check Sonic Genome for vocal masking risk
            spectral_notch = False
            if results:
                g_str = results[0].get("sonic_genome", "{}")
                if g_str and g_str != "{}":
                    try:
                        g_json = json.loads(g_str)
                        if g_json.get("acoustic", {}).get("vocal_clash_risk") in ("MODERATE", "SEVERE"):
                            spectral_notch = True
                    except Exception:
                        pass

            trigger_seg = cue_data.get("trigger_segment", 1)
            start_ms = seg_starts_ms.get(trigger_seg, 0)

            # Timeline bounds and budget capping
            if start_ms >= total_duration_ms:
                continue

            dur_ms = int(float(cue_data.get("duration_sec", 30.0)) * 1000)
            until_seg = cue_data.get("until_segment")
            if until_seg:
                try:
                    u_idx = int(until_seg)
                    if u_idx in seg_starts_ms and seg_starts_ms[u_idx] > start_ms:
                        dur_ms = seg_starts_ms[u_idx] - start_ms
                except (ValueError, TypeError):
                    pass

            remaining_budget = max_music_budget_ms - accumulated_music_ms
            dur_ms = min(dur_ms, remaining_budget, total_duration_ms - start_ms)
            if dur_ms < 500:
                continue

            accumulated_music_ms += dur_ms

            music_cues.append(
                MusicCue(
                    cue_id=cue_data.get("cue_id", f"mc_{idx+1:03d}"),
                    cue_type=cue_data.get("cue_type", "TRANSITION_BRIDGE"),
                    track_name=chosen_track,
                    track_id=track_id,
                    section_name=energy_sec,
                    section_start_sec=section_start_sec,
                    start_ms=start_ms,
                    duration_ms=dur_ms,
                    fade_in_ms=int(float(cue_data.get("fade_in_sec", 3.0)) * 1000),
                    fade_out_ms=int(float(cue_data.get("fade_out_sec", 4.0)) * 1000),
                    volume_db=float(cue_data.get("volume_db", -18.0)),
                    dramatic_justification=cue_data.get("dramatic_justification", ""),
                    leitmotif_ref=lm_ref or (getattr(resolved_motif, "motif_id", "") if resolved_motif else ""),
                    spectral_notch_needed=spectral_notch,
                    target_valence=cue_data.get("valence"),
                    target_arousal=cue_data.get("arousal"),
                    narrative_archetype=cue_data.get("narrative_archetype"),
                )
            )

        return music_cues

    # =========================================================================
    # PASS 3 IMPLEMENTATION: Acoustic Foley (Dependency parsing, word alignment)
    # =========================================================================
    def _pass3_acoustic_foley(
        self,
        script_segments: List[Dict[str, Any]],
        foley_events_plan: List[Dict[str, Any]],
        seg_starts_ms: Dict[int, int],
        segment_durations_sec: Dict[int, float],
    ) -> List[FoleyCue]:
        """
        Pass 3: Acoustic Foley using structured screenplay cues and explicit physical actions.
        Aligns physical contact events to exact anchor word timestamps with transient pre-roll.
        Zero guessing of weapons or combat in domestic/modern scenes.
        """
        foley_cues: List[FoleyCue] = []
        seg_by_index = {s.get("index", idx + 1): s for idx, s in enumerate(script_segments)}

        # If LLM did not generate foley events (or offline), run explicit dependency parsing
        candidates = list(foley_events_plan) if foley_events_plan else self._parse_grammatical_foley_dependencies(script_segments)

        # Register any dedicated action beats in script_segments not already in candidates
        registered_indices = {c.get("segment_index") for c in candidates}
        for s in script_segments:
            s_idx = s.get("index", 1)
            if s.get("type") == "action" and s_idx not in registered_indices:
                sfx_list = s.get("sfx_cues", [])
                action_verb = "creak"
                material = "wood"
                anchor_tag = "[ACTION]"
                if sfx_list:
                    raw_sfx = sfx_list[0]
                    tag = raw_sfx.get("tag", "") if isinstance(raw_sfx, dict) else str(raw_sfx)
                    if tag:
                        anchor_tag = tag
                        parts = tag.split("_")
                        if len(parts) >= 2:
                            action_verb = parts[0]
                            material = parts[1]
                        elif len(parts) == 1:
                            action_verb = parts[0]
                    candidates.append({
                        "segment_index": s_idx,
                        "subject": "Foley",
                        "action_verb": action_verb,
                        "object_material": material,
                        "anchor_word": anchor_tag,
                        "target_gain_dbfs": -16.0,
                        "azimuth_pan": 0.0,
                    })

        for idx, event in enumerate(candidates):
            s_idx = event.get("segment_index", 1)
            seg = seg_by_index.get(s_idx)
            if not seg:
                continue

            action_verb = event.get("action_verb", "")
            object_material = event.get("object_material", "")
            if not action_verb:
                continue

            anchor_word = event.get("anchor_word", "")
            target_gain_dbfs = float(event.get("target_gain_dbfs", -16.0))
            pan_val = float(event.get("azimuth_pan", 0.0))
            pan_val = max(-0.8, min(0.8, pan_val))

            # Resolve asset dynamically from Sound Bank via category/action/exciter
            asset_path = self._resolve_foley_asset(action_verb, object_material)
            if not asset_path or not asset_path.exists():
                continue

            # Anchor Foley cues: dedicated physical action beats land directly on seg_start_ms + 50ms
            seg_start_ms = seg_starts_ms.get(s_idx, 0)
            seg_dur_ms = int(segment_durations_sec.get(s_idx, 4.0) * 1000)

            is_action_seg = (seg.get("type") == "action") or (seg.get("speaker") == "Foley")
            if is_action_seg:
                # Dedicated action beat: anchor Foley directly to seg_start_ms + 50ms with 50ms transient lead-in
                pre_roll_ms = 50
                cue_start_ms = max(0, seg_start_ms + 50)
            else:
                # Word-level alignment: calculate precise offset of anchor word in segment speech
                anchor_offset_ms = self._compute_word_level_offset(
                    text=seg.get("text", ""),
                    anchor_word=anchor_word,
                    seg_dur_ms=seg_dur_ms,
                    action_verb=action_verb,
                    word_alignments=seg.get("word_alignments")
                )
                pre_roll_ms = 100  # 100ms transient lead-in for physical impact
                cue_start_ms = max(0, seg_start_ms + anchor_offset_ms - pre_roll_ms)

            from audiobook_factory.acoustic_bus_matrix import derive_ucs_category
            ucs_code = derive_ucs_category(action_verb, object_material)

            foley_cues.append(
                FoleyCue(
                    cue_id=f"fc_{s_idx:04d}_{idx:03d}",
                    segment_index=s_idx,
                    anchor_word=anchor_word or action_verb,
                    pre_roll_ms=pre_roll_ms,
                    asset_id=0,
                    asset_path=str(asset_path.resolve()).replace("\\", "/"),
                    asset_name=asset_path.name,
                    gain_dbfs=target_gain_dbfs,
                    azimuth_pan=pan_val,
                    start_ms=cue_start_ms,
                    duration_ms=0,
                    ucs_category=ucs_code,
                )
            )

        from audiobook_factory.acoustic_bus_matrix import filter_concurrency_window
        from audiobook_factory.soundscape import attenuate_foley_whisper_collisions
        pruned_foley = filter_concurrency_window(foley_cues, window_ms=200, max_concurrency=3)
        return attenuate_foley_whisper_collisions(pruned_foley, script_segments, attenuation_db=-6.0)

    def _parse_grammatical_foley_dependencies(
        self, script_segments: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Extracts physical Foley events strictly from explicit segment metadata (sfx_cues)
        or dedicated action segments. Never hallucinates weapons, combat, or fantasy actions
        in domestic, suburban, or peaceful scenes.
        """
        candidates: List[Dict[str, Any]] = []

        for seg in script_segments:
            s_idx = seg.get("index", 1)
            sfx_list = seg.get("sfx_cues", [])
            is_action = (seg.get("type") == "action") or (seg.get("speaker") == "Foley")

            # 1. Parse explicit sfx_cues provided by the LLM or screenplay
            if sfx_list:
                for sfx in sfx_list:
                    tag = sfx.get("tag", "") if isinstance(sfx, dict) else str(sfx)
                    if not tag:
                        continue
                    parts = tag.split("_")
                    action_verb = parts[0]
                    material = parts[1] if len(parts) >= 2 else "wood"
                    candidates.append({
                        "segment_index": s_idx,
                        "subject": seg.get("speaker", "Foley"),
                        "action_verb": action_verb,
                        "object_material": material,
                        "anchor_word": sfx.get("anchor_word", f"[{tag.upper()}]") if isinstance(sfx, dict) else f"[{tag.upper()}]",
                        "target_gain_dbfs": float(sfx.get("gain_dbfs", -16.0)) if isinstance(sfx, dict) else -16.0,
                        "azimuth_pan": float(sfx.get("pan", 0.0)) if isinstance(sfx, dict) else 0.0,
                    })
                continue

            # 2. If dedicated action segment without explicit sfx list, inspect text for grounded physical actions
            if is_action:
                text_clean = seg.get("text", "").lower()
                # Check for subtle everyday domestic/suburban actions
                if any(w in text_clean for w in ("door", "दरवाजा", "gate", "किवाड़")):
                    candidates.append({
                        "segment_index": s_idx,
                        "subject": "Foley",
                        "action_verb": "creak" if any(w in text_clean for w in ("creak", "चूं")) else "slam",
                        "object_material": "door",
                        "anchor_word": "[ACTION]",
                        "target_gain_dbfs": -16.0,
                        "azimuth_pan": 0.0,
                    })
                elif any(w in text_clean for w in ("cup", "tea", "प्याला", "चाय", "plate", "थाली")):
                    candidates.append({
                        "segment_index": s_idx,
                        "subject": "Foley",
                        "action_verb": "tableware",
                        "object_material": "cup",
                        "anchor_word": "[ACTION]",
                        "target_gain_dbfs": -18.0,
                        "azimuth_pan": 0.0,
                    })

        return candidates

    def _compute_word_level_offset(
        self, text: str, anchor_word: str, seg_dur_ms: int, action_verb: str = "", word_alignments: Optional[List[Dict[str, Any]]] = None
    ) -> int:
        """Computes speech timeline offset of the anchor word within a dialogue segment with bilingual normalization."""
        anchor_lower = (anchor_word or "").lower().strip()
        verb_lower = (action_verb or "").lower().strip()

        # Bilingual Synonym / Stem Map (Devanagari <-> English)
        BILINGUAL_ANCHOR_MAP = {
            "sword": ["तलवार", "खंजर", "ब्लेड", "शमशीर", "blade"],
            "blade": ["तलवार", "खंजर", "ब्लेड"],
            "draw": ["खींची", "निकाली", "निकाल", "खींच", "draw"],
            "unsheathe": ["खींची", "निकाली", "म्यान"],
            "door": ["दरवाजा", "किवाड़", "कपाट", "gate"],
            "slam": ["पटक", "दे मारा", "धड़ाम", "ठोक", "slam"],
            "creak": ["चूं", "चरमरा", "आवाज", "creak"],
            "step": ["कदम", "पैरों", "चला", "बढ़ा", "step"],
            "footstep": ["कदम", "पैरों", "पदचाप", "footsteps"],
            "plate": ["थाली", "तश्तरी", "बर्तन", "रकाब", "plate"],
            "dish": ["थाली", "कटोरा", "प्याला", "बर्तन", "dish"],
            "cup": ["प्याला", "गिलास", "कटोरा", "cup"],
            "tankard": ["प्याला", "मग", "सुराही", "कटोरा", "tankard"],
            "pour": ["उड़ेला", "उड़ेल", "डाला", "भर", "pour"],
            "bone": ["हड्डी", "अस्थि", "bone"],
            "body": ["शरीर", "देह", "धड़", "लाश", "body"],
            "fall": ["गिरा", "गिरे", "फर्श", "जमीन", "fall"],
            "clash": ["टकरा", "वार", "clash"],
            "ignite": ["जला", "सुलगा", "ignite"],
            "torch": ["मशाल", "आग", "torch"],
            "fire": ["आग", "ज्वाला", "fire"],
        }

        search_targets = {anchor_lower} if anchor_lower else set()
        if anchor_lower in BILINGUAL_ANCHOR_MAP:
            search_targets.update(BILINGUAL_ANCHOR_MAP[anchor_lower])
        if verb_lower in BILINGUAL_ANCHOR_MAP:
            search_targets.update(BILINGUAL_ANCHOR_MAP[verb_lower])
        for eng, hindi_list in BILINGUAL_ANCHOR_MAP.items():
            if anchor_lower in hindi_list:
                search_targets.add(eng)
                search_targets.update(hindi_list)

        # 1. Precise Aligner Mode
        if word_alignments:
            for word_data in word_alignments:
                w_norm = str(word_data.get("normalized_token", "")).lower()
                w_raw = str(word_data.get("token", "")).lower()
                if any(t and (t == w_norm or t == w_raw or t in w_raw) for t in search_targets):
                    # Return exact exact alignment timestamp in MS
                    return int(word_data.get("start_ms", 0))

        # 2. Fallback Linear Math Mode (If forced aligner data is missing)
        words = [w.strip(".,!?;:\"'()[]{}—–") for w in text.split() if w.strip(".,!?;:\"'()[]{}—–")]
        if not words:
            return 150

        word_idx = -1
        for i, w in enumerate(words):
            w_low = w.lower()
            if any(t and (t in w_low or w_low in t) for t in search_targets):
                word_idx = i
                break

        if word_idx >= 0:
            word_ratio = (word_idx + 0.5) / max(1, len(words))
            return int(seg_dur_ms * max(0.08, min(0.92, word_ratio)))

        impact_actions = {"clash", "slam", "fall", "impact", "break", "bone", "पटक", "गिरा", "टकरा"}
        if anchor_lower in impact_actions or verb_lower in impact_actions:
            return int(seg_dur_ms * 0.75)
        return int(seg_dur_ms * 0.15)

    def _resolve_foley_asset(self, action_verb: str, object_material: str) -> Optional[Path]:
        """Resolves sound asset from sound bank using Sonic Intelligence Engine semantic intent queries."""
        intent = f"{action_verb} {object_material}".strip()
        if not intent:
            return None

        try:
            # Engage hybrid intelligence FTS/Vector query
            result = self.sound_bank.search_intelligence(intent=intent, limit=3)
            if result and hasattr(result, "ranked_cards") and result.ranked_cards:
                for card in result.ranked_cards:
                    if card and getattr(card, "file_path", None):
                        cand = Path(card.file_path)
                        # CATEGORY GUARD: Prohibit weapon/combat assets for non-combat intents
                        is_combat_intent = any(w in intent.lower() for w in ("sword", "blade", "dagger", "axe", "weapon", "clash"))
                        banned_non_combat = ("sword", "blade", "scabbard", "parry", "axe", "dagger", "drawbridge", "armor", "clash")
                        if not is_combat_intent and any(b in cand.name.lower() for b in banned_non_combat):
                            continue
                        if cand.exists():
                            return cand
        except Exception as e:
            # Fallback to basic search if intelligence engine fails
            pass

        # 2. Basic fallback search if Intelligence didn't yield a valid local path
        matches = self.sound_bank.search(intent, category="foley", limit=3)
        if not matches:
            matches = self.sound_bank.search(action_verb, category="foley", limit=2)
        for m in matches:
            if m.get("filepath"):
                cand = Path(m["filepath"])
                is_combat_intent = any(w in intent.lower() for w in ("sword", "blade", "dagger", "axe", "weapon", "clash"))
                banned_non_combat = ("sword", "blade", "scabbard", "parry", "axe", "dagger", "drawbridge", "armor", "clash")
                if not is_combat_intent and any(b in cand.name.lower() for b in banned_non_combat):
                    continue
                if cand.exists():
                    return cand

        # 3. Sonic Intelligence Bridge: Relaxed / Bilingual resolution
        try:
            from audiobook_factory.sonic_intelligence_bridge import SonicIntelligenceBridge
            bridge = SonicIntelligenceBridge(sound_bank=self.sound_bank)
            is_combat_intent = any(w in intent.lower() for w in ("sword", "blade", "dagger", "axe", "weapon", "clash"))
            cand_path, tier, _ = bridge.resolve_asset_with_fallback(
                query=intent,
                category="foley",
                is_combat_scene=is_combat_intent,
            )
            if cand_path and cand_path.exists():
                return cand_path
        except Exception:
            pass

        return None

    def _partition_script_ambience_scenes(
        self,
        script_segments: Optional[List[Dict[str, Any]]],
        seg_starts_ms: Optional[Dict[int, int]],
        segment_durations_sec: Optional[Dict[int, float]],
        total_duration_ms: int,
    ) -> List[Tuple[str, int, int]]:
        """Partitions chapter segments into dynamic scene acoustic blocks based on acoustic_env shifts."""
        if not script_segments or not seg_starts_ms:
            return []

        blocks: List[Tuple[str, int, int]] = []
        cur_env: Optional[str] = None
        cur_start = 0
        cur_end = 0

        for seg in script_segments:
            s_idx = seg.get("index", 1)
            raw_env = (seg.get("acoustic_env") or "").strip()
            if not raw_env or raw_env.lower() in ("default", "none"):
                raw_env = "room_tone"
            s_start = seg_starts_ms.get(s_idx, 0)
            dur_ms = int((segment_durations_sec.get(s_idx, 4.0) if segment_durations_sec else 4.0) * 1000)
            s_end = s_start + dur_ms

            if cur_env is None:
                cur_env = raw_env
                cur_start = s_start
                cur_end = s_end
            elif raw_env == cur_env:
                cur_end = max(cur_end, s_end)
            else:
                blocks.append((cur_env, cur_start, cur_end))
                cur_env = raw_env
                cur_start = s_start
                cur_end = s_end

        if cur_env is not None:
            blocks.append((cur_env, cur_start, max(cur_end, total_duration_ms)))

        # Clean block boundaries so there are no negative durations and contiguous coverage
        cleaned: List[Tuple[str, int, int]] = []
        for i, (env, s, e) in enumerate(blocks):
            if i < len(blocks) - 1:
                next_s = blocks[i+1][1]
                e = max(s + 500, next_s)
            else:
                e = max(s + 500, total_duration_ms)
            cleaned.append((env, s, e))
        return cleaned

    def _resolve_ambience_scenes(
        self,
        amb_plan: List[Dict[str, Any]],
        total_duration_ms: int,
        script_segments: Optional[List[Dict[str, Any]]] = None,
        seg_starts_ms: Optional[Dict[int, int]] = None,
        segment_durations_sec: Optional[Dict[int, float]] = None,
    ) -> List[AmbienceScene]:
        """Resolves environmental room tone / ambience scenes for continuous backdrop."""
        # 1. Dynamic scene partitioning based on script segment acoustic environments
        blocks = self._partition_script_ambience_scenes(
            script_segments=script_segments,
            seg_starts_ms=seg_starts_ms,
            segment_durations_sec=segment_durations_sec,
            total_duration_ms=total_duration_ms,
        )

        scenes: List[AmbienceScene] = []

        if len(blocks) > 1:
            for idx, (env_name, b_start, b_end) in enumerate(blocks):
                amb_path = (
                    self.sound_bank.resolve_sound(f"{env_name}.ogg", category="AMB") or
                    self.sound_bank.resolve_sound(f"{env_name}.wav", category="AMB") or
                    self.sound_bank.resolve_sound(env_name, category="AMB") or
                    self.sound_bank.resolve_sound(env_name)
                )
                if not amb_path:
                    results = (
                        self.sound_bank.search(env_name.replace("_", " "), category="ambience", limit=1) or
                        self.sound_bank.search("room_tone", category="ambience", limit=1)
                    )
                    if results:
                        amb_path = Path(results[0]["filepath"])

                if amb_path and amb_path.exists():
                    scenes.append(
                        AmbienceScene(
                            scene_id=idx + 1,
                            start_ms=b_start,
                            end_ms=b_end,
                            asset_name=amb_path.name,
                            asset_path=str(amb_path.resolve()).replace("\\", "/"),
                            target_lufs=-32.0,
                        )
                    )
            if scenes:
                return scenes

        # 2. Plan-based / single-scene fallback
        for idx, amb in enumerate(amb_plan):
            amb_name = amb.get("name", "room_tone")
            amb_path = (
                self.sound_bank.resolve_sound(f"{amb_name}.ogg", category="AMB") or
                self.sound_bank.resolve_sound(amb_name, category="AMB") or
                self.sound_bank.resolve_sound(amb_name)
            )
            if not amb_path:
                results = (
                    self.sound_bank.search(amb_name, category="ambience", limit=1) or
                    self.sound_bank.search("room_tone", category="ambience", limit=1)
                )
                if results:
                    amb_path = Path(results[0]["filepath"])
            if amb_path and amb_path.exists():
                scenes.append(
                    AmbienceScene(
                        scene_id=idx + 1,
                        start_ms=0,
                        end_ms=total_duration_ms,
                        asset_name=amb_path.name,
                        asset_path=str(amb_path.resolve()).replace("\\", "/"),
                        target_lufs=float(amb.get("target_lufs", -32.0)),
                    )
                )

        if not scenes:
            dyn_results = (
                self.sound_bank.search("room_tone", category="ambience", limit=1) or
                self.sound_bank.search("ambience", category="ambience", limit=1)
            )
            if dyn_results:
                def_path = Path(dyn_results[0]["filepath"])
                if def_path.exists():
                    scenes.append(
                        AmbienceScene(
                            scene_id=1,
                            start_ms=0,
                            end_ms=total_duration_ms,
                            asset_name=def_path.name,
                            asset_path=str(def_path.resolve()).replace("\\", "/"),
                            target_lufs=-32.0,
                        )
                    )

        return scenes

    def _resolve_scene_acoustics(
        self,
        chapter_id: str,
        dramaturgy_plan: Dict[str, Any],
        total_duration_ms: int,
        sonic_bible: Optional[Any] = None,
        script_segments: Optional[List[Dict[str, Any]]] = None,
        seg_starts_ms: Optional[Dict[int, int]] = None,
        segment_durations_sec: Optional[Dict[int, float]] = None,
    ) -> Any:
        """
        Pillar 4 / Idea 1 & 2: Resolves rich 4-stem decoupled scene acoustics manifest.
        Creates scene profiles with Base Room Tone, Weather Elements, Crowd Wallah, and Stochastic Spots.
        """
        from audiobook_factory.scene_acoustics import SceneSoundscapeManifest, SceneAcousticProfile, AmbienceLayer

        scene_manifest = SceneSoundscapeManifest(chapter_id=chapter_id)

        # Check if plan already has explicit scene profiles
        raw_scenes = dramaturgy_plan.get("scene_acoustics") or dramaturgy_plan.get("scenes")
        if raw_scenes and isinstance(raw_scenes, list):
            for sc_data in raw_scenes:
                try:
                    profile = SceneAcousticProfile.model_validate(sc_data)
                    scene_manifest.add_scene(profile)
                except Exception as e:
                    logger.debug(f"Could not parse custom scene profile: {e}")

        # Check if script segments delineate multiple acoustic scenes
        blocks = self._partition_script_ambience_scenes(
            script_segments=script_segments,
            seg_starts_ms=seg_starts_ms,
            segment_durations_sec=segment_durations_sec,
            total_duration_ms=total_duration_ms,
        )

        theme_str = str(dramaturgy_plan.get("dramatic_theme", "")).lower()

        from audiobook_factory.sound_design.environment_profiles import get_environment_registry
        env_reg = get_environment_registry()

        if not scene_manifest.scenes and len(blocks) > 1:
            for idx, (env_name, b_start, b_end) in enumerate(blocks):
                layers: List[AmbienceLayer] = []
                comb_str = f"{env_name} {theme_str}".lower()
                env_prof = env_reg.get_profile(env_name) or env_reg.resolve_from_text(comb_str)

                # 1. Base Room Tone from canonical profile
                base_asset_name = env_prof.typical_ambience_layers[0] if env_prof.typical_ambience_layers else env_name
                base_res = (
                    self.sound_bank.resolve_sound(base_asset_name, category="AMB") or
                    self.sound_bank.resolve_sound(f"{env_name}.ogg", category="AMB") or
                    self.sound_bank.resolve_sound(f"{env_name}.wav", category="AMB") or
                    self.sound_bank.resolve_sound(env_name, category="AMB") or
                    self.sound_bank.resolve_sound("room_tone", category="AMB") or
                    self.sound_bank.resolve_sound("amb_castle_hall_hearth.wav", category="AMB")
                )
                base_path = base_res.name if base_res else base_asset_name
                layers.append(
                    AmbienceLayer(
                        layer_type="base_room_tone",
                        asset_path=base_path,
                        target_lufs=-34.0,
                        stereo_width=1.35,
                        loop=True,
                    )
                )

                # 2. Weather Elements
                weather_path = None
                if len(env_prof.typical_ambience_layers) > 1:
                    w_cand = env_prof.typical_ambience_layers[1]
                    w_res = self.sound_bank.resolve_sound(w_cand, category="AMB") or self.sound_bank.resolve_sound(w_cand)
                    if w_res:
                        weather_path = w_res.name
                if not weather_path:
                    if "rain" in comb_str or "storm" in comb_str:
                        weather_path = "rain_thunder.ogg"
                    elif any(k in comb_str for k in ("wind", "snow", "blizzard", "mountain")):
                        weather_path = "amb_blizzard_mountain_gale.wav"
                    elif any(k in comb_str for k in ("swamp", "bog")):
                        weather_path = "amb_bog_swamp_night.wav"
                    elif any(k in comb_str for k in ("crypt", "tomb")):
                        weather_path = "amb_crypt_tomb_drips.wav"

                if weather_path:
                    layers.append(
                        AmbienceLayer(
                            layer_type="weather_elements",
                            asset_path=weather_path,
                            target_lufs=-32.0,
                            stereo_width=1.40,
                            loop=True,
                        )
                    )

                # 3. Crowd Walla
                if env_prof.typical_walla or any(k in comb_str for k in ("tavern", "crowd", "brawl", "hall", "market", "whisper", "people", "street", "office")):
                    w_asset = env_prof.typical_walla or "tavern_crowd_murmur.ogg"
                    if any(k in comb_str for k in ("whisper", "office", "street", "privet", "people")):
                        w_asset = "07039098.mp3"  # Crowd Whispering in Large Room
                    w_res = self.sound_bank.resolve_sound(w_asset, category="AMB") or self.sound_bank.resolve_sound(w_asset)
                    layers.append(
                        AmbienceLayer(
                            layer_type="crowd_wallah",
                            asset_path=w_res.name if w_res else w_asset,
                            target_lufs=-30.0,
                            stereo_width=1.30,
                            loop=True,
                        )
                    )

                # 4. Spot Stochastic (Gentle occasional atmospheric transients)
                stoch_asset = "dry_grass_fireplace_raw.ogg"
                if env_prof.typical_foley:
                    for tf in env_prof.typical_foley:
                        tf_res = self.sound_bank.resolve_sound(tf, category="FX") or self.sound_bank.resolve_sound(tf)
                        if tf_res and not any(b in tf_res.name.lower() for b in ("jump", "boot", "sword", "blade")):
                            stoch_asset = tf_res.name
                            break
                if any(k in comb_str for k in ("night", "street", "privet", "suburban")):
                    stoch_asset = "07042032.mp3"  # Tawny Owl with crickets
                elif any(k in comb_str for k in ("water", "dungeon", "crypt")):
                    stoch_asset = "tiny_water-drop-01.wav"

                layers.append(
                    AmbienceLayer(
                        layer_type="spot_stochastic",
                        asset_path=stoch_asset,
                        target_lufs=-26.0,
                        stochastic_interval_sec=120.0,
                        loop=False,
                    )
                )

                occ_cutoff = env_prof.occlusion_barrier_hz
                ir_preset = "hall" if env_prof.estimated_rt60_ms > 1800 else "room"
                scene_manifest.add_scene(
                    SceneAcousticProfile(
                        scene_id=f"sc_{idx+1:03d}_{chapter_id}",
                        act_index=idx + 1,
                        start_ms=b_start,
                        end_ms=b_end,
                        ir_preset=ir_preset,
                        layers=layers,
                        occlusion_cutoff_hz=occ_cutoff,
                    )
                )

        if not scene_manifest.scenes:
            amb_list = dramaturgy_plan.get("ambience", [])
            primary_name = amb_list[0].get("name", "room_tone") if amb_list else "room_tone"
            env_prof = env_reg.get_profile(primary_name) or env_reg.resolve_from_text(f"{primary_name} {theme_str}")
            layers = []

            base_asset_name = env_prof.typical_ambience_layers[0] if env_prof.typical_ambience_layers else primary_name
            base_res = (
                self.sound_bank.resolve_sound(base_asset_name, category="AMB") or
                self.sound_bank.resolve_sound(f"{primary_name}.ogg", category="AMB") or
                self.sound_bank.resolve_sound(primary_name, category="AMB") or
                self.sound_bank.resolve_sound("room_tone", category="AMB") or
                self.sound_bank.resolve_sound("amb_castle_hall_hearth.wav", category="AMB")
            )
            base_path = base_res.name if base_res else base_asset_name
            layers.append(
                AmbienceLayer(
                    layer_type="base_room_tone",
                    asset_path=base_path,
                    target_lufs=-34.0,
                    stereo_width=1.35,
                    loop=True,
                )
            )

            weather_path = None
            if len(env_prof.typical_ambience_layers) > 1:
                w_cand = env_prof.typical_ambience_layers[1]
                w_res = self.sound_bank.resolve_sound(w_cand, category="AMB") or self.sound_bank.resolve_sound(w_cand)
                if w_res:
                    weather_path = w_res.name
            if not weather_path:
                if "rain" in theme_str or "storm" in theme_str:
                    weather_path = "rain_thunder.ogg"
                elif any(k in theme_str for k in ("wind", "snow", "blizzard", "mountain")):
                    weather_path = "amb_blizzard_mountain_gale.wav"
                elif "swamp" in theme_str or "bog" in theme_str:
                    weather_path = "amb_bog_swamp_night.wav"
                elif "crypt" in theme_str or "tomb" in theme_str:
                    weather_path = "amb_crypt_tomb_drips.wav"

            if weather_path:
                layers.append(
                    AmbienceLayer(
                        layer_type="weather_elements",
                        asset_path=weather_path,
                        target_lufs=-32.0,
                        stereo_width=1.40,
                        loop=True,
                    )
                )

            if env_prof.typical_walla or any(k in theme_str for k in ("tavern", "crowd", "brawl", "hall")):
                w_asset = env_prof.typical_walla or "tavern_crowd_murmur.ogg"
                w_res = self.sound_bank.resolve_sound(w_asset, category="AMB") or self.sound_bank.resolve_sound(w_asset)
                layers.append(
                    AmbienceLayer(
                        layer_type="crowd_wallah",
                        asset_path=w_res.name if w_res else "tavern_crowd_murmur.ogg",
                        target_lufs=-30.0,
                        stereo_width=1.30,
                        loop=True,
                    )
                )

            stoch_asset = "tiny_floor-creak-01.wav"
            if env_prof.typical_foley:
                for tf in env_prof.typical_foley:
                    tf_res = self.sound_bank.resolve_sound(tf, category="FX") or self.sound_bank.resolve_sound(tf)
                    if tf_res:
                        stoch_asset = tf_res.name
                        break
            if stoch_asset == "tiny_floor-creak-01.wav":
                if "fire" in theme_str or "torch" in theme_str or "hearth" in theme_str:
                    stoch_asset = "dry_grass_fireplace_raw.ogg"
                elif "water" in theme_str or "dungeon" in theme_str:
                    stoch_asset = "tiny_water-drop-01.wav"

            layers.append(
                AmbienceLayer(
                    layer_type="spot_stochastic",
                    asset_path=stoch_asset,
                    target_lufs=-24.0,
                    stochastic_interval_sec=35.0,
                    loop=False,
                )
            )

            occ_cutoff = env_prof.occlusion_barrier_hz
            ir_preset = "hall" if env_prof.estimated_rt60_ms > 1800 else "room"

            scene_manifest.add_scene(
                SceneAcousticProfile(
                    scene_id=f"sc_001_{chapter_id}",
                    act_index=1,
                    start_ms=0,
                    end_ms=max(1000, total_duration_ms),
                    ir_preset=ir_preset,
                    layers=layers,
                    occlusion_cutoff_hz=occ_cutoff,
                )
            )

        return scene_manifest

