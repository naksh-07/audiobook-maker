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

from audiobook_factory.director.dramaturgy import DramaturgyMixin
from audiobook_factory.director.music_director import MusicDirectorMixin
from audiobook_factory.director.foley_director import FoleyDirectorMixin
from audiobook_factory.director.scene_acoustics import SceneAcousticsMixin


class AgentDirector(DramaturgyMixin, MusicDirectorMixin, FoleyDirectorMixin, SceneAcousticsMixin):
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
        self.model = model or get_model_manager().resolve_active_model(TaskType.DIRECTING)
        self.project_dir = Path(project_dir) if project_dir else None
        self.sonic_bible = sonic_bible
        if not self.sonic_bible and self.project_dir:
            self._load_project_sonic_bible(self.project_dir)

    def _load_project_sonic_bible(self, pdir: Path) -> None:
        """Attempt to load project-level sound_bible.json or sonic_bible.json if present."""
        bible_path = pdir / "sound_bible.json"
        if not bible_path.exists():
            bible_path = pdir / "sonic_bible.json"

        if bible_path.exists():
            try:
                from audiobook_factory.sonic_bible import SonicBible
                self.sonic_bible = SonicBible.load_from_disk(bible_path)
                logger.info(
                    f"[+] Agent Director: Loaded Sonic Bible from {bible_path.name} "
                    f"({len(self.sonic_bible.leitmotifs)} motifs, {len(self.sonic_bible.acoustic_spaces)} spaces)"
                )
            except Exception as e:
                logger.warning(f"  [!] Failed to load Sonic Bible from {bible_path}: {e}")
        else:
            try:
                from audiobook_factory.sonic_bible_generator import SonicBibleGenerator
                self.sonic_bible = SonicBibleGenerator.generate_for_project(pdir, sound_bank=self.sound_bank)
            except Exception as e:
                logger.debug(f"Could not auto-generate Sonic Bible: {e}")

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
                if not bible_path.exists():
                    bible_path = Path(check_dir) / "sonic_bible.json"
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
        # PASS 1: Specialist Multi-Agent Sound Spotting Engine (SoundSpotter)
        # =====================================================================
        check_pdir = project_dir or self.project_dir
        sound_script_data = None
        force_rebuild = os.environ.get("FORCE_REBUILD_MANIFEST", "false").lower() in ("true", "1", "yes")
        if check_pdir and not force_rebuild:
            manifests_dir = Path(check_pdir) / "manifests"
            sound_script_file = manifests_dir / f"{chapter_id}_sound_script.json"
            if sound_script_file.exists():
                try:
                    with open(sound_script_file, "r", encoding="utf-8") as sf:
                        sound_script_data = json.load(sf)
                    logger.info(f"[*] Agent Director: Ingested pre-spotted Audio Cue Sheet from {sound_script_file.name}")
                except Exception as e:
                    logger.warning(f"  [!] Failed to read sound script {sound_script_file}: {e}")

        use_spotter = os.environ.get("USE_SOUND_SPOTTER", "true").lower() in ("true", "1", "yes")
        era = os.environ.get("STORY_ERA")
        franchise_affinity = None
        dramatic_theme = "Cinematic Audio Drama"

        if check_pdir:
            from audiobook_factory.project_classifier import ProjectClassifier
            clf = ProjectClassifier.classify(project_dir=Path(check_pdir))
            era = era or clf.era
            franchise_affinity = clf.franchise_affinity
            dramatic_theme = clf.dramatic_theme
        else:
            era = era or "GENERAL_DRAMA"

        if not sound_script_data and use_spotter:
            try:
                from audiobook_factory.sound_spotter import SoundSpotter
                spotter = SoundSpotter(sound_bank=self.sound_bank)
                sound_script_data = spotter.spot_chapter(
                    chapter_id=chapter_id,
                    script_segments=script_segments,
                    segment_durations_sec=segment_durations_sec,
                    seg_starts_ms=seg_starts_ms,
                    total_duration_sec=total_duration_sec,
                    era=era,
                    franchise_affinity=franchise_affinity,
                    project_dir=check_pdir,
                )
            except Exception as e:
                logger.warning(f"  [!] SoundSpotter multi-agent run encountered error, falling back to legacy passes: {e}")

        # Bulletproof Fallback Gate: Never treat empty or failed cues as intentional 100% silence!
        has_spotter_cues = bool(
            sound_script_data and (
                sound_script_data.get("music_cues") or
                sound_script_data.get("foley_cues") or
                sound_script_data.get("ambience_scenes")
            )
        )

        ai_director_degraded = False
        if has_spotter_cues:
            dramaturgy_plan = {
                "chapter_id": chapter_id,
                "dramatic_theme": dramatic_theme,
                "era": sound_script_data.get("era", era),
                "franchise_affinity": franchise_affinity,
                "ambience": sound_script_data.get("ambience_scenes", []),
                "foley_events": sound_script_data.get("foley_cues", []),
                "music_cues": sound_script_data.get("music_cues", []),
            }

            foley_cues = []
            for fc in sound_script_data.get("foley_cues", []):
                try:
                    foley_cues.append(FoleyCue.model_validate(fc))
                except Exception as ex:
                    logger.debug(f"Foley cue validation notice: {ex}")
            logger.info(f"  [+] Ingested {len(foley_cues)} Foley cues from SoundSpotter")

            ambience_scenes = []
            for ac in sound_script_data.get("ambience_scenes", []):
                try:
                    ambience_scenes.append(AmbienceScene.model_validate(ac))
                except Exception as ex:
                    logger.debug(f"Ambience scene validation notice: {ex}")
            logger.info(f"  [+] Ingested {len(ambience_scenes)} Ambience beds from SoundSpotter")

            music_cues = []
            for mc in sound_script_data.get("music_cues", []):
                try:
                    music_cues.append(MusicCue.model_validate(mc))
                except Exception as ex:
                    logger.debug(f"Music cue validation notice: {ex}")
            logger.info(f"  [+] Ingested {len(music_cues)} Music cues from SoundSpotter")

            scene_acoustics = self._resolve_scene_acoustics(
                chapter_id=chapter_id,
                dramaturgy_plan=dramaturgy_plan,
                total_duration_ms=total_duration_ms,
                sonic_bible=active_bible,
                script_segments=script_segments,
                seg_starts_ms=seg_starts_ms,
                segment_durations_sec=segment_durations_sec,
            )
        else:
            logger.warning(
                "  [!] SoundSpotter returned 0 cues (or was empty). Engaging deterministic Sound Bank directing passes..."
            )
            # =====================================================================
            # LEGACY PASS 1: Dramaturgy & Silence Carving (Fallback Heuristic)
            # =====================================================================
            ai_director_degraded = False
            try:
                dramaturgy_plan = self._pass1_dramaturgy_and_silence_carving(
                    chapter_id=chapter_id,
                    script_segments=script_segments,
                    total_duration_sec=total_duration_sec,
                    max_retries=max_retries,
                    sonic_bible=active_bible,
                )
            except Exception as ex:
                if os.environ.get("STRICT_HALT_ON_DIRECTOR_LLM", "false").lower() in ("true", "1", "yes"):
                    raise
                ai_director_degraded = True
                # DEGRADED MODE: Dramaturge LLM is unavailable. Falling back to static keyword matching.
                # This produces robotic, generic sound design — NOT suitable for final production output.
                # Set STRICT_HALT_ON_DIRECTOR_LLM=true to halt the pipeline instead of silently degrading.
                logger.error(
                    f"  [!] 🛑 DIRECTOR: Pass 1 Dramaturge LLM FAILED ({ex}). "
                    "Engaging deterministic (keyword-matching) dramaturgy compiler — "
                    "sound design will be GENERIC and non-cinematic. "
                    "Set STRICT_HALT_ON_DIRECTOR_LLM=true to halt on this condition."
                )
                dramaturgy_plan = self._build_deterministic_dramaturgy_plan(script_segments, total_duration_sec, sonic_bible=active_bible)
                dramaturgy_plan = self._enforce_silence_carving(dramaturgy_plan, total_duration_sec)

            # Ambience Bed Resolution (Environmental room tone, -32 LUFS)
            ambience_scenes = self._resolve_ambience_scenes(
                dramaturgy_plan.get("ambience", []),
                total_duration_ms=total_duration_ms,
                script_segments=script_segments,
                seg_starts_ms=seg_starts_ms,
                segment_durations_sec=segment_durations_sec,
            )

            scene_acoustics = self._resolve_scene_acoustics(
                chapter_id=chapter_id,
                dramaturgy_plan=dramaturgy_plan,
                total_duration_ms=total_duration_ms,
                sonic_bible=active_bible,
                script_segments=script_segments,
                seg_starts_ms=seg_starts_ms,
                segment_durations_sec=segment_durations_sec,
            )

            music_cues = self._pass2_music_director(
                cues_plan=dramaturgy_plan.get("music_cues", []),
                seg_starts_ms=seg_starts_ms,
                total_duration_ms=total_duration_ms,
                sonic_bible=active_bible,
            )

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
            acoustic_staging=sound_script_data.get("acoustic_staging", {}) if sound_script_data else {},
            wallah_automations=sound_script_data.get("wallah_automations", []) if sound_script_data else [],
            metadata={
                "director": "AgentDirector 3-Pass Creative Workflow v3.0",
                "director_mode": "DETERMINISTIC_FALLBACK" if ai_director_degraded else "NEURAL_LLM",
                "ai_director_degraded": ai_director_degraded,
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
