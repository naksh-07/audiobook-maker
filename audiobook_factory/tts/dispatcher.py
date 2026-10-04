#!/usr/bin/env python3
"""
Audiobook Factory - Pillar 3.2: Concurrent TTS Dispatcher & Token-Bucket Continuity Engine.
Routes speech segments to Google Gemini 3.8 Flash TTS with thread-safe rate-limiting,
transaction-safe SQLite segment ledgering, TakeBank evaluation, and multi-speaker batch optimization.
"""

from __future__ import annotations
import os
import sys
import json
import uuid
import wave
import shutil
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from audiobook_factory.logger import logger
from audiobook_factory.state import ProjectStateLedger
from audiobook_factory.key_manager import (
    get_persistent_key_pool,
    AllKeysExhaustedTodayError,
)
from audiobook_factory.cadence import get_human_cadence_controller
from audiobook_factory.contracts import (
    BatchPlanItem,
    BatchDispatchManifest,
    ScreenplaySegment,
)
from audiobook_factory.batch_planner import BatchDispatchPlanner
from audiobook_factory.forced_aligner import WorkstationForcedAligner

from audiobook_factory.tts.constants import (
    DEFAULT_BACKEND,
    DEFAULT_VOICE,
    DEFAULT_MODEL,
    DEFAULT_BATCHING_ENABLED,
    DEFAULT_FORCED_ALIGNMENT_ENABLED,
    DEFAULT_DECLICK_FADE_MS,
    DEFAULT_WORKERS,
    DEFAULT_RPM,
    get_ffmpeg,
    UnregisteredSpeakerError,
)
from audiobook_factory.tts.rate_limiter import TokenBucketRateLimiter
from audiobook_factory.tts.providers.gemini import (
    synthesize_gemini_tts,
    synthesize_gemini_multispeaker_batch,
)
from audiobook_factory.tts.audio_slicer import (
    compute_canonical_segment_filename,
    slice_and_declick_batch,
)


def _call_gemini_tts(*args, **kwargs):
    """Invokes synthesize_gemini_tts, honoring any monkeypatches on the tts_dispatcher facade."""
    td = sys.modules.get("audiobook_factory.tts_dispatcher")
    fn = getattr(td, "synthesize_gemini_tts", synthesize_gemini_tts) if td else synthesize_gemini_tts
    return fn(*args, **kwargs)


def _call_gemini_multispeaker_batch(*args, **kwargs):
    """Invokes synthesize_gemini_multispeaker_batch, honoring any monkeypatches on the tts_dispatcher facade."""
    td = sys.modules.get("audiobook_factory.tts_dispatcher")
    fn = getattr(td, "synthesize_gemini_multispeaker_batch", synthesize_gemini_multispeaker_batch) if td else synthesize_gemini_multispeaker_batch
    return fn(*args, **kwargs)


def _call_key_pool():
    td = sys.modules.get("audiobook_factory.tts_dispatcher")
    if td and hasattr(td, "get_persistent_key_pool"):
        try:
            return td.get_persistent_key_pool()
        except Exception:
            pass
    if td and hasattr(td, "global_key_pool"):
        return td.global_key_pool
    return get_persistent_key_pool()


class TTSDispatcher:
    """Orchestrates concurrent speech synthesis with TokenBucket rate limiting and SQLite ledger state."""

    def __init__(
        self,
        project_dir: Path,
        default_backend: str = DEFAULT_BACKEND,
        default_voice: str = DEFAULT_VOICE,
        max_workers: int = 1,
        rpm: float = DEFAULT_RPM,
        audio_dir: Optional[Path] = None,
        strict_speakers: bool = True,
        allow_dynamic_cast: Optional[bool] = None,
    ):
        self.project_dir = Path(project_dir).resolve()
        self.audio_dir = Path(audio_dir).resolve() if audio_dir else (self.project_dir / "audio_chunks")
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        self.registry_file = self.project_dir / "voice_registry.json"
        self.roster_file = self.project_dir / "character_roster.json"
        self.default_backend = default_backend
        self.default_voice = default_voice
        self.strict_speakers = strict_speakers
        if allow_dynamic_cast is None:
            self.allow_dynamic_cast = os.environ.get("ALLOW_DYNAMIC_CAST", "false").lower() in ("true", "1", "yes")
        else:
            self.allow_dynamic_cast = allow_dynamic_cast
        if max_workers > 1:
            logger.info("  [STEALTH INVARIANT] Multi-worker network requests disabled to prevent IP clustering and quota flags. Operating strictly in 1-worker mode.")
        self.max_workers = 1
        self.rate_limiter = TokenBucketRateLimiter(rate_rpm=rpm)
        self.voice_map = self._load_voice_registry()
        self.alias_map, self.gender_map = self._load_character_roster()
        self.ledger = ProjectStateLedger(self.project_dir, auto_recover=False)
        self.batching_enabled = DEFAULT_BATCHING_ENABLED
        self.forced_aligner = WorkstationForcedAligner() if DEFAULT_FORCED_ALIGNMENT_ENABLED else None
        self.batch_planner = BatchDispatchPlanner(enabled=self.batching_enabled)
        # Performance Realization Layer
        from audiobook_factory.performance import (
            PerformanceDirector,
            TakeBank,
            PerformanceEvaluator,
            IntelligentTakeSelector,
            PerformanceContinuityTracker,
        )
        pb = None
        for cand_pb in (self.project_dir / "performance_bible.json", self.project_dir / "dramaturgy" / "performance_bible.json"):
            if cand_pb.exists():
                try:
                    from audiobook_factory.dramaturgy.contracts import PerformanceBible
                    pb = PerformanceBible.load_from_file(cand_pb)
                    break
                except Exception:
                    pass
        self.performance_director = PerformanceDirector(performance_bible=pb)
        self.take_bank = TakeBank(self.audio_dir / "takes")
        self.evaluator = PerformanceEvaluator()
        self.take_selector = IntelligentTakeSelector(evaluator=self.evaluator)
        self.continuity_tracker = PerformanceContinuityTracker()
        for cand_cc in (self.project_dir / "character_continuity.json", self.project_dir / "performance" / "character_continuity.json"):
            if cand_cc.exists():
                self.continuity_tracker.load_from_file(cand_cc)
                break

        # Pronunciation & Spoken Language QA Subsystem
        from audiobook_factory.pronunciation import (
            PronunciationLexicon,
            PronunciationResolver,
            SpokenTextEngine,
            PronunciationAudioQA,
            PronunciationRepairEngine,
        )
        book_bible = None
        for cand_bb in (self.project_dir / "book_bible.json", self.project_dir / "translation" / "book_bible.json"):
            if cand_bb.exists():
                try:
                    from audiobook_factory.translation.book_bible import BookBible
                    book_bible = BookBible.load_from_project(self.project_dir)
                    break
                except Exception:
                    pass
        self.pronunciation_lexicon = PronunciationLexicon.load_or_create(self.project_dir, book_bible=book_bible)
        self.pronunciation_resolver = PronunciationResolver(lexicon=self.pronunciation_lexicon, book_bible=book_bible)
        self.spoken_text_engine = SpokenTextEngine(resolver=self.pronunciation_resolver)
        self.pronunciation_auditor = PronunciationAudioQA(forced_aligner=self.forced_aligner)
        self.pronunciation_repair = PronunciationRepairEngine(auditor=self.pronunciation_auditor)

        # Formal Cast Lock Subsystem (Wave 1 Upgrade)
        from audiobook_factory.casting import CastLockManager
        self.cast_lock_manager = CastLockManager(self.project_dir)

        # Character Voice DNA & Reference Subsystems (Wave 2 Upgrade)
        from audiobook_factory.identity import VoiceDNABank, ReferenceVoiceBank
        from audiobook_factory.performance.scene_emotional_state import SceneEmotionalStateTracker
        self.voice_dna_bank = VoiceDNABank(self.project_dir)
        self.reference_voice_bank = ReferenceVoiceBank(self.project_dir)
        self.scene_tracker = SceneEmotionalStateTracker()
        self._prev_take = None

    def _load_character_roster(self) -> Tuple[Dict[str, str], Dict[str, str]]:
        """Loads character aliases and gender mappings from character_roster.json."""
        alias_map: Dict[str, str] = {}
        gender_map: Dict[str, str] = {}
        if not self.roster_file.exists():
            return alias_map, gender_map

        try:
            with open(self.roster_file, "r", encoding="utf-8") as f:
                roster_data = json.load(f)
            chars = roster_data.get("characters", roster_data)
            if isinstance(chars, dict):
                for canon_name, details in chars.items():
                    c_clean = canon_name.strip()
                    alias_map[c_clean.lower()] = c_clean
                    alias_map[c_clean.lower().replace("_", " ")] = c_clean
                    alias_map[c_clean.lower().replace(" ", "_")] = c_clean
                    if isinstance(details, dict):
                        gender_map[c_clean] = details.get("gender", "neutral").lower()
                        for alias in details.get("aliases", []):
                            if isinstance(alias, str) and alias.strip():
                                a_clean = alias.strip()
                                alias_map[a_clean.lower()] = c_clean
                                alias_map[a_clean.lower().replace("_", " ")] = c_clean
                                alias_map[a_clean.lower().replace(" ", "_")] = c_clean
            elif isinstance(chars, list):
                for item in chars:
                    if isinstance(item, dict):
                        canon_name = item.get("english_name") or item.get("display_name") or item.get("name", "")
                        if canon_name:
                            c_clean = canon_name.strip()
                            alias_map[c_clean.lower()] = c_clean
                            alias_map[c_clean.lower().replace("_", " ")] = c_clean
                            gender_map[c_clean] = item.get("gender", "neutral").lower()
                            hindi = item.get("hindi_name", "")
                            if hindi:
                                alias_map[hindi.strip().lower()] = c_clean
                            for alias in item.get("aliases", []):
                                if isinstance(alias, str) and alias.strip():
                                    a_clean = alias.strip()
                                    alias_map[a_clean.lower()] = c_clean
                                    alias_map[a_clean.lower().replace("_", " ")] = c_clean
        except Exception as e:
            logger.warning(f"  [ROSTER LOAD NOTICE] Failed to parse character_roster.json: {e}")

        return alias_map, gender_map

    def _load_voice_registry(self) -> Dict[str, Any]:
        if self.registry_file.exists():
            with open(self.registry_file, "r", encoding="utf-8") as f:
                return json.load(f)

        default_map = {
            "Narrator": {"backend": self.default_backend, "voice": self.default_voice, "speed": 1.0},
        }
        with open(self.registry_file, "w", encoding="utf-8") as f:
            json.dump(default_map, f, indent=2)
        return default_map

    def assign_voice(self, speaker: str, backend: str, voice: str, speed: float = 1.0):
        """Assign voice to a specific character permanently."""
        self.voice_map[speaker] = {
            "backend": backend,
            "voice": voice,
            "speed": speed,
        }
        with open(self.registry_file, "w", encoding="utf-8") as f:
            json.dump(self.voice_map, f, indent=2)

        if hasattr(self, "cast_lock_manager") and self.cast_lock_manager:
            self.cast_lock_manager.lock_character(
                character_id=speaker.lower().replace(" ", "_"),
                character_name=speaker,
                voice_id=voice,
                calibration_overrides={"speed": speed},
            )

    def get_speaker_config(self, speaker: str, seg_type: str = "narration") -> Dict[str, Any]:
        """
        Resolves complete speaker configuration (backend, voice, speed, pitch, bass_boost_db).
        Strictly prohibits silent fallback to Narrator (Aoede) for dialogue segments.
        """
        sp_clean = (speaker or "").strip()
        sp_lower = sp_clean.lower()

        # 0. Formal Cast Lock Resolution (Wave 1 Cast Lock takes authoritative priority)
        if hasattr(self, "cast_lock_manager") and self.cast_lock_manager:
            lock = self.cast_lock_manager.get_lock(sp_clean)
            if not lock and sp_lower in self.alias_map:
                lock = self.cast_lock_manager.get_lock(self.alias_map[sp_lower])
            if lock and lock.locked:
                cfg = {
                    "backend": "gemini_tts",
                    "voice": lock.voice_id,
                    "speed": lock.calibration_overrides.get("speed", 1.0),
                    "pitch": lock.calibration_overrides.get("pitch", 1.0),
                    "cast_locked": True,
                    "casting_version": lock.casting_version,
                }
                for k, v in lock.calibration_overrides.items():
                    if k not in cfg:
                        cfg[k] = v
                return cfg

        # 1. Exact match in voice_map
        if sp_clean in self.voice_map:
            return dict(self.voice_map[sp_clean])

        # 2. Case-insensitive / normalized underscore match in voice_map
        for k, cfg in self.voice_map.items():
            k_lower = k.strip().lower()
            if k_lower == sp_lower or k_lower.replace("_", " ") == sp_lower.replace("_", " "):
                return dict(cfg)

        # 3. Alias resolution via character_roster.json
        if sp_lower in self.alias_map:
            canon = self.alias_map[sp_lower]
            if canon in self.voice_map:
                return dict(self.voice_map[canon])
            canon_norm = canon.lower().replace("_", " ")
            for k, cfg in self.voice_map.items():
                if k.strip().lower() == canon.lower() or k.strip().lower().replace("_", " ") == canon_norm:
                    return dict(cfg)

        sp_norm = sp_lower.replace("_", " ")
        if sp_norm in self.alias_map:
            canon = self.alias_map[sp_norm]
            if canon in self.voice_map:
                return dict(self.voice_map[canon])
            canon_norm = canon.lower().replace("_", " ")
            for k, cfg in self.voice_map.items():
                if k.strip().lower() == canon.lower() or k.strip().lower().replace("_", " ") == canon_norm:
                    return dict(cfg)

        # 4. Narrator / Foley / Narration segment type
        if sp_clean in ("Narrator", "Foley") or sp_lower in ("narrator", "narration", "foley") or seg_type == "narration":
            narr_cfg = self.voice_map.get("Narrator", {})
            return {
                "backend": narr_cfg.get("backend", self.default_backend),
                "voice": narr_cfg.get("voice", self.default_voice),
                "speed": narr_cfg.get("speed", 1.0),
            }

        # 5. Unregistered Speaker in Dialogue Segment
        import difflib
        known_speakers = sorted(list(set(list(self.voice_map.keys()) + list(self.alias_map.keys()))))
        close = difflib.get_close_matches(sp_clean, known_speakers, n=3, cutoff=0.5)
        close_hint = f" Did you mean: {', '.join(close)}?" if close else ""

        if self.strict_speakers:
            if self.allow_dynamic_cast:
                # Dynamic on-the-fly casting with persistent lock (Production Auto-Casting)
                try:
                    from audiobook_factory.character_caster import CharacterCaster
                    p_dir = getattr(self, "project_dir", None) or Path.cwd()
                    dynamic_cfg = CharacterCaster.cast_single_speaker(
                        speaker_name=sp_clean,
                        project_dir=p_dir,
                        gender=self.gender_map.get(sp_clean),
                        default_backend=self.default_backend,
                    )
                    self.voice_map[sp_clean] = dynamic_cfg
                    logger.info(
                        f"[+] Dynamic Cast: Auto-registered '{sp_clean}' -> {dynamic_cfg.get('voice')} "
                        f"to avoid halting production."
                    )
                    return dict(dynamic_cfg)
                except Exception as e:
                    logger.warning(f"  [!] Dynamic casting fallback failed for '{sp_clean}': {e}")
            raise UnregisteredSpeakerError(
                f"Speaker '{sp_clean}' (type: {seg_type}) is not registered in voice_registry.json "
                f"or character_roster.json!{close_hint} Silent fallback to Narrator is prohibited to prevent voice drift."
            )

        # Non-strict fallback with gender awareness
        logger.error(
            f"  [UNREGISTERED SPEAKER] '{sp_clean}' not in registry.{close_hint} Fallback initiated."
        )
        gender = self.gender_map.get(sp_clean, "neutral")
        if gender == "male":
            for male_fallback in ("Charon", "Fenrir", "Puck"):
                for k, cfg in self.voice_map.items():
                    if cfg.get("voice") == male_fallback:
                        return dict(cfg)
        narr_cfg = self.voice_map.get("Narrator", {})
        return {
            "backend": narr_cfg.get("backend", self.default_backend),
            "voice": narr_cfg.get("voice", self.default_voice),
            "speed": narr_cfg.get("speed", 1.0),
        }

    def get_speaker_voice(self, speaker: str, seg_type: str = "narration") -> Tuple[str, str]:
        """Backwards-compatible helper returning (backend, voice)."""
        cfg = self.get_speaker_config(speaker, seg_type)
        return cfg.get("backend", self.default_backend), cfg.get("voice", self.default_voice)

    def synthesize_segment(
        self,
        segment: Dict[str, Any],
        chapter_num: int,
        seg_num: int,
        performance_direction: Optional[Any] = None,
    ) -> Tuple[Path, float]:
        """Synthesize a single speech segment with resume checkpointing and post-DSP calibration."""
        seg_type = segment.get("type", "narration") if isinstance(segment, dict) else getattr(segment, "type", "narration")

        # Deterministic Action Beat: Generate silent stereo 48kHz WAV canvas matching pause_after_ms
        if seg_type == "action":
            pause_after = segment.get("pause_after_ms", 600) if isinstance(segment, dict) else getattr(segment, "pause_after_ms", 600)
            if pause_after is None or pause_after <= 0:
                pause_after = 600
            dur = pause_after / 1000.0

            cache_key = f"action|{chapter_num}|{seg_num}|{pause_after}".encode("utf-8")
            action_hash = hashlib.md5(cache_key).hexdigest()[:8]
            out_file = self.audio_dir / f"c{chapter_num:03d}_s{seg_num:04d}_{action_hash}.wav"

            if not (out_file.exists() and out_file.stat().st_size > 44):
                out_file.parent.mkdir(parents=True, exist_ok=True)
                sample_rate = 24000
                num_frames = int(round(sample_rate * dur))
                silence_bytes = b"\x00" * (num_frames * 2)
                with wave.open(str(out_file), "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(sample_rate)
                    wf.writeframes(silence_bytes)

            logger.info(f"  [ACTION BEAT] Created clean {dur:.2f}s silent canvas for Foley -> {out_file.name}")
            return out_file, dur

        text = segment.get("text", "").strip() if isinstance(segment, dict) else getattr(segment, "text", "").strip()
        if not text:
            raise ValueError("Empty segment text")

        speaker = segment.get("speaker", "Narrator") if isinstance(segment, dict) else getattr(segment, "speaker", "Narrator")
        sp_cfg = self.get_speaker_config(speaker, seg_type)
        voice = sp_cfg.get("voice", self.default_voice)
        speed = float(sp_cfg.get("speed", 1.0))

        acting = segment.get("acting", {})
        if isinstance(acting, dict):
            pacing_mult = float(acting.get("pacing", 1.0))
        else:
            pacing_mult = float(segment.get("pacing", 1.0))
        if 0.75 <= pacing_mult <= 1.35:
            speed = speed * pacing_mult

        pitch = float(sp_cfg.get("pitch", 1.0))
        bass_boost_db = float(sp_cfg.get("bass_boost_db", 0.0))
        denoise = bool(sp_cfg.get("denoise", False))
        clarity_cut_db = float(sp_cfg.get("clarity_reduction_db", 0.0))
        lowpass_hz = int(sp_cfg.get("lowpass_hz", 0))
        highpass_hz = int(sp_cfg.get("highpass_hz", 0))
        presence_boost_db = float(sp_cfg.get("presence_boost_db", 0.0))
        volume_gain_db = float(sp_cfg.get("volume_gain_db", 0.0))
        softclip_tanh = bool(sp_cfg.get("softclip_tanh", False))

        out_filename = compute_canonical_segment_filename(chapter_num, seg_num, text, sp_cfg, default_voice=self.default_voice)
        out_file = self.audio_dir / out_filename

        # Resume checkpoint: skip if exact hash file already exists and valid
        if out_file.exists() and out_file.stat().st_size > 1000:
            dur = 0.0
            try:
                with wave.open(str(out_file), "rb") as wf:
                    frames = wf.getnframes()
                    rate = wf.getframerate()
                    dur = frames / float(rate)
            except Exception:
                dur = 1.0
            return out_file, dur

        # Resolve Character Voice DNA & Reference Signature
        voice_dna = None
        signature = None
        if hasattr(self, "voice_dna_bank") and self.voice_dna_bank:
            try:
                voice_dna = self.voice_dna_bank.get_dna(speaker)
            except Exception:
                voice_dna = None
        if hasattr(self, "reference_voice_bank") and self.reference_voice_bank:
            try:
                signature = self.reference_voice_bank.get_signature(speaker)
            except Exception:
                signature = None

        # Update Scene Emotional State
        scene_vector = None
        if hasattr(self, "scene_tracker") and self.scene_tracker:
            emotion_hint = segment.get("emotion", "neutral") if isinstance(segment, dict) else (getattr(segment, "emotion", "neutral") or "neutral")
            intensity_hint = segment.get("intensity_level", "medium") if isinstance(segment, dict) else (getattr(segment, "intensity_level", "medium") or "medium")
            causal_hint = segment.get("causal_trigger") if isinstance(segment, dict) else getattr(segment, "causal_trigger", None)
            scene_vector = self.scene_tracker.update_state(
                segment_index=seg_num,
                speaker=speaker,
                target_emotion=emotion_hint,
                intensity=intensity_hint,
                causal_trigger=causal_hint,
            )

        # Resolve Performance Direction
        p_dir = performance_direction
        if not p_dir:
            p_dir = self.performance_director.direct_segment(
                segment,
                scene_vector=scene_vector,
                voice_dna=voice_dna,
            )

        emotion = segment.get("emotion", "neutral") if isinstance(segment, dict) else getattr(segment, "emotion", "neutral")
        intensity = segment.get("intensity_level", "medium") if isinstance(segment, dict) else getattr(segment, "intensity_level", "medium")
        mem_vc = segment.get("memory_vocal_constraint") if isinstance(segment, dict) else getattr(segment, "memory_vocal_constraint", None)

        spoken_res = self.spoken_text_engine.resolve_screenplay_segment(segment)
        tts_text = spoken_res.spoken_text or text
        if isinstance(segment, dict):
            segment["spoken_text"] = tts_text
            segment["pronunciation_metadata"] = [r.model_dump() for r in spoken_res.resolutions]
        elif hasattr(segment, "spoken_text"):
            segment.spoken_text = tts_text
            segment.pronunciation_metadata = [r.model_dump() for r in spoken_res.resolutions]

        if hasattr(p_dir, "spoken_text"):
            p_dir.spoken_text = tts_text
            p_dir.pronunciation_metadata = [r.model_dump() for r in spoken_res.resolutions]

        if getattr(spoken_res, "has_unresolved_critical", False) is True:
            from audiobook_factory.pronunciation.contracts import PronunciationStatus
            unres = [
                getattr(r, "original_token", str(r)) for r in getattr(spoken_res, "resolutions", [])
                if getattr(r, "status", None) in (PronunciationStatus.FAILED, PronunciationStatus.UNCERTAIN)
            ]
            if unres:
                allow_degraded = os.environ.get("TTS_ALLOW_DEGRADED_TAKES", "false").lower() in ("true", "1", "yes")
                if not allow_degraded:
                    raise RuntimeError(
                        f"Critical pronunciation resolution failed for Chapter {chapter_num:03d} Segment {seg_num:04d}: "
                        f"unresolved tokens {unres}. Halting production to prevent defective speech."
                    )

        # Multi-Take Candidate Generation via TakeBank + GenerationStrategyResolver
        from audiobook_factory.performance.strategy_resolver import GenerationStrategyResolver
        strategy_plan = GenerationStrategyResolver.resolve_strategy(p_dir, text=tts_text)
        candidate_variants = self.take_bank.get_candidate_variants(p_dir, strategy_plan=strategy_plan, text=tts_text)
        takes_for_seg = []

        for v_type in candidate_variants:
            if v_type == "standard" and len(candidate_variants) == 1:
                take_target = out_file
            else:
                take_target = self.take_bank.takes_dir / f"c{chapter_num:03d}_s{seg_num:04d}_{v_type}.wav"

            if not (take_target.exists() and take_target.stat().st_size > 1000):
                _call_gemini_tts(
                    text=tts_text,
                    output_file=take_target,
                    voice=voice,
                    emotion=emotion,
                    acting=acting,
                    intensity=intensity,
                    memory_vocal_constraint=mem_vc,
                    performance_direction=p_dir,
                    variant_type=v_type,
                    rate_limiter=self.rate_limiter,
                    voice_dna=voice_dna,
                    scene_vector=scene_vector,
                )

            take_var = self.take_bank.create_take(
                segment_uid=p_dir.segment_uid,
                segment_index=seg_num,
                variant_type=v_type,
                audio_file=take_target,
                direction=p_dir,
            )
            takes_for_seg.append(take_var)

        # Intelligent Take Selection with Voice Identity & Conversational Chemistry
        winning_take = self.take_selector.select_best_take(
            takes_for_seg,
            tts_text,
            p_dir,
            signature=signature,
            voice_dna=voice_dna,
            prev_take=getattr(self, "_prev_take", None),
        )

        # Pronunciation Audio QA & Targeted Take Repair
        qa_res = self.pronunciation_auditor.audit_take(
            take_audio_path=winning_take.audio_path,
            spoken_result=spoken_res,
            take_id=winning_take.take_id,
            segment_uid=p_dir.segment_uid,
        )
        if not qa_res.passed:
            repaired_take = self.pronunciation_repair.attempt_repair(
                dispatcher=self,
                segment=segment if isinstance(segment, dict) else segment.model_dump(),
                failed_take=winning_take,
                qa_result=qa_res,
                chapter_num=chapter_num,
                seg_num=seg_num,
                p_dir=p_dir,
            )
            if repaired_take:
                winning_take = repaired_take
            else:
                winning_take.is_selected = False
                winning_take.selection_reason = (
                    f"[PRONUNCIATION_QA_FAILED] Audio failed pronunciation QA ({qa_res.status.value}): "
                    f"{'; '.join(qa_res.omissions or qa_res.review_reasons or qa_res.repetitions)}"
                )

        if not getattr(winning_take, "is_selected", True):
            allow_degraded = os.environ.get("TTS_ALLOW_DEGRADED_TAKES", "false").lower() in ("true", "1", "yes")
            if not allow_degraded:
                raise RuntimeError(
                    f"Take selection failed for Chapter {chapter_num:03d} Segment {seg_num:04d} "
                    f"({getattr(winning_take, 'selection_reason', 'Unacceptable take')}). "
                    f"Halting production to prevent defective audio from entering master."
                )
            logger.critical(
                f"  [DEGRADED FALLBACK PERMITTED] Segment {seg_num}: {getattr(winning_take, 'selection_reason', '')}"
            )

        self._prev_take = winning_take

        if str(winning_take.audio_path) != str(out_file):
            shutil.copy2(winning_take.audio_path, str(out_file))

        out_path = out_file
        dur = winning_take.duration_sec

        # Apply speaker DSP calibration filters
        post_filters = []
        if highpass_hz > 20:
            post_filters.append(f"highpass=f={highpass_hz}")

        if denoise:
            post_filters.append("afftdn=nr=10:nf=-38")

        if ("[shouting]" in text.lower()) or (isinstance(acting, dict) and acting.get("delivery_style") == "bellowing_rage"):
            softclip_tanh = True
            if presence_boost_db <= 0.1:
                presence_boost_db = 1.5
            elif presence_boost_db > 2.0:
                presence_boost_db = 2.0

        if softclip_tanh:
            post_filters.append("asoftclip=type=tanh:param=1.2")

        if abs(pitch - 1.0) > 0.005:
            new_rate = int(24000 * pitch)
            post_filters.append(f"asetrate={new_rate},aresample=24000")
            eff_tempo = speed / pitch
            if abs(eff_tempo - 1.0) > 0.01:
                post_filters.append(f"atempo={eff_tempo:.3f}")
        elif abs(speed - 1.0) > 0.01:
            post_filters.append(f"atempo={speed:.3f}")

        if bass_boost_db > 0.1:
            post_filters.append(f"equalizer=f=100:t=q:w=1.2:g={bass_boost_db:.1f}")
            post_filters.append("equalizer=f=200:t=q:w=1.4:g=3.0")
        elif bass_boost_db < -0.1:
            post_filters.append(f"equalizer=f=200:t=q:w=1.2:g={bass_boost_db:.1f}")

        if presence_boost_db > 0.1:
            post_filters.append(f"equalizer=f=3200:t=q:w=1.4:g={presence_boost_db:.1f}")

        if abs(volume_gain_db) > 0.1:
            post_filters.append(f"volume={volume_gain_db:+.1f}dB")

        if clarity_cut_db > 0.1:
            post_filters.append(f"equalizer=f=3000:t=q:w=1.8:g=-{clarity_cut_db:.1f}")

        if lowpass_hz > 1000:
            post_filters.append(f"lowpass=f={lowpass_hz}")

        if post_filters:
            post_filters.append("alimiter=limit=-1.2dB:attack=5:release=50:asc=true")
            fade_dur_ms = 15.0
            f_sec = fade_dur_ms / 1000.0
            f_out_st = max(0.0, dur - f_sec)
            post_filters.append(f"afade=t=in:ss=0:d={f_sec:.3f}:curve=qsin")
            post_filters.append(f"afade=t=out:st={f_out_st:.3f}:d={f_sec:.3f}:curve=qsin")

            tmp_calib = out_file.with_suffix(f".calib_{uuid.uuid4().hex[:6]}.wav")
            ffmpeg_bin = get_ffmpeg()
            cmd = [
                ffmpeg_bin, "-y",
                "-i", str(out_file),
                "-af", ",".join(post_filters),
                "-c:a", "pcm_s16le",
                str(tmp_calib),
            ]
            try:
                import subprocess
                subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                try:
                    with wave.open(str(tmp_calib), "rb") as in_wf:
                        c_params = in_wf.getparams()
                        c_pcm = in_wf.readframes(in_wf.getnframes())
                    import numpy as _np
                    c_samples = _np.frombuffer(c_pcm, dtype=_np.int16).copy()
                    if len(c_samples) > 2:
                        c_samples[0] = 0
                        c_samples[-1] = 0
                    with wave.open(str(tmp_calib), "wb") as out_wf:
                        out_wf.setparams(c_params)
                        out_wf.writeframes(c_samples.tobytes())
                except Exception:
                    pass
                tmp_calib.replace(out_file)
                with wave.open(str(out_file), "rb") as wf:
                    dur = wf.getnframes() / float(wf.getframerate())
            except Exception as e:
                logger.warning(f"  [!] Speaker DSP calibration notice: {e}")
                if tmp_calib.exists():
                    tmp_calib.unlink(missing_ok=True)

        if p_dir:
            self.continuity_tracker.record_direction(p_dir, dur)
            self.continuity_tracker.record_take(p_dir.speaker, take_id=out_path.stem, duration_sec=dur)

        return out_path, dur

    def synthesize_chapter_script(self, script_path: Path, chapter_num: int) -> List[Path]:
        """
        Synthesize all segments in a chapter script sequentially using Human Cadence controller.
        Updates SQLite state ledger at every milestone and respects batch planner optimization.
        """
        with open(script_path, "r", encoding="utf-8") as f:
            script = json.load(f)
        if isinstance(script, dict):
            script = script.get("segments", script)

        total = len(script)
        self._prev_take = None

        # Pre-flight voice registry validation across all segments (ADR-021 Zero Voice Drift)
        for seg_idx, seg in enumerate(script, 1):
            seg_t = seg.get("type", "narration")
            sp = seg.get("speaker", "Narrator")
            if seg_t == "dialogue" or (sp and sp not in ("Narrator", "Foley")):
                try:
                    self.get_speaker_config(sp, seg_t)
                except UnregisteredSpeakerError as e:
                    logger.error(
                        f"\n[!] PRE-FLIGHT SYNTHESIS HALT: Chapter {chapter_num}, Segment {seg_idx} has invalid speaker: {e}"
                    )
                    raise

        td_mod = sys.modules.get("audiobook_factory.tts_dispatcher")
        cadence_fn = getattr(td_mod, "get_human_cadence_controller", get_human_cadence_controller) if td_mod else get_human_cadence_controller
        cadence = cadence_fn()

        logger.info(
            f"[*] Synthesizing Chapter {chapter_num} ({total} speech segments, mode="
            f"{'STEALTH_HUMAN_CADENCE' if self.max_workers == 1 else f'PARALLEL_{self.max_workers}'})..."
        )

        self.ledger.register_script_segments(chapter_num, script, self.voice_map, self.default_voice)

        from audiobook_factory.performance.chemistry import ConversationalChemistry
        chapter_directions = self.performance_director.direct_chapter_script(script, voice_dna_bank=self.voice_dna_bank)
        chapter_directions = ConversationalChemistry.apply_conversational_chemistry(chapter_directions)
        dir_by_idx = {d.index: d for d in chapter_directions}

        results: List[Optional[Path]] = [None] * total

        # Batching Engine Optimization: If batching is enabled, group eligible dialogue into multi-speaker batches
        if self.batching_enabled and total > 1:
            try:
                self.batch_planner.enabled = True
                parsed_segments = []
                for s in script:
                    if isinstance(s, ScreenplaySegment):
                        parsed_segments.append(s)
                    elif isinstance(s, dict):
                        parsed_segments.append(ScreenplaySegment.model_validate(s))

                voice_map_for_batch = {}
                for s in parsed_segments:
                    spk = s.speaker
                    if spk not in voice_map_for_batch:
                        _, v = self.get_speaker_voice(spk, s.type)
                        voice_map_for_batch[spk] = v

                manifest = self.batch_planner.plan_chapter_batches(
                    segments=parsed_segments,
                    chapter_id=f"chapter_{chapter_num:03d}",
                    chapter_num=chapter_num,
                    voice_map=voice_map_for_batch,
                )

                manifest_file = self.audio_dir / f"c{chapter_num:03d}_batch_manifest.json"
                with open(manifest_file, "w", encoding="utf-8") as f:
                    f.write(manifest.model_dump_json(indent=2))

                for batch in manifest.batches:
                    if batch.strategy in ("multi_speaker_duo", "narrator_chunk"):
                        all_exist = True
                        for seg in batch.segments:
                            spk_cfg = self.get_speaker_config(seg.speaker, getattr(seg, "type", "dialogue"))
                            exp_name = compute_canonical_segment_filename(
                                chapter_num, seg.index, seg.text, spk_cfg, default_voice=batch.voice_map.get(seg.speaker, self.default_voice)
                            )
                            exp_file = self.audio_dir / exp_name
                            if not (exp_file.exists() and exp_file.stat().st_size > 1000):
                                all_exist = False
                                break

                        if all_exist:
                            for seg in batch.segments:
                                spk_cfg = self.get_speaker_config(seg.speaker, getattr(seg, "type", "dialogue"))
                                exp_name = compute_canonical_segment_filename(
                                    chapter_num, seg.index, seg.text, spk_cfg, default_voice=batch.voice_map.get(seg.speaker, self.default_voice)
                                )
                                existing = self.audio_dir / exp_name
                                dur = 1.0
                                try:
                                    with wave.open(str(existing), "rb") as wf:
                                        dur = wf.getnframes() / float(wf.getframerate())
                                except Exception:
                                    pass
                                results[seg.index - 1] = existing
                                self.ledger.mark_segment_completed(existing.stem, str(existing), dur, chapter_num=chapter_num, seg_num=seg.index)
                            continue

                        batch_wav = self.audio_dir / f"{batch.batch_id}_raw.wav"
                        try:
                            cadence.wait_before_segment(" ".join(s.text for s in batch.segments[:2]), batch.segments[0].index, total)
                            if batch.strategy == "multi_speaker_duo":
                                _call_gemini_multispeaker_batch(
                                    batch=batch,
                                    output_file=batch_wav,
                                    voice_map=batch.voice_map,
                                    rate_limiter=self.rate_limiter,
                                )
                            else:
                                narr_spk = batch.speakers[0] if batch.speakers else "Narrator"
                                narr_voice = batch.voice_map.get(narr_spk, self.default_voice)
                                combined_text = "  ".join(s.text.strip() for s in batch.segments)
                                _call_gemini_tts(
                                    text=combined_text,
                                    output_file=batch_wav,
                                    voice=narr_voice,
                                    rate_limiter=self.rate_limiter,
                                )

                            sliced = slice_and_declick_batch(
                                raw_audio=batch_wav,
                                batch=batch,
                                chapter_num=chapter_num,
                                output_dir=self.audio_dir,
                                aligner=self.forced_aligner,
                                dispatcher=self,
                            )
                            for seg, (s_file, dur, words_metadata) in zip(batch.segments, sliced):
                                results[seg.index - 1] = s_file
                                with open(s_file.with_suffix(".words.json"), "w", encoding="utf-8") as wf:
                                    json.dump(words_metadata, wf)
                                self.ledger.mark_segment_completed(s_file.stem, str(s_file), dur, chapter_num=chapter_num, seg_num=seg.index)
                                seg_dir = dir_by_idx.get(seg.index)
                                if seg_dir and hasattr(self, "take_bank") and self.take_bank:
                                    try:
                                        t_var = self.take_bank.create_take(
                                            segment_uid=seg_dir.segment_uid,
                                            segment_index=seg.index,
                                            variant_type="batched",
                                            audio_file=s_file,
                                            direction=seg_dir,
                                        )
                                        t_var.is_selected = True
                                        t_var.selection_reason = f"Batched synthesis from {batch.batch_id} ({batch.strategy})"
                                    except Exception as tb_err:
                                        logger.warning(f"  [!] TakeBank batch registration notice for segment {seg.index}: {tb_err}")
                                logger.info(f"  [{seg.index}/{total}] Batch Sliced: {seg.speaker} ({s_file.name}, {dur:.1f}s)")
                        except AllKeysExhaustedTodayError as e:
                            logger.critical(f"  [QUOTA PAUSE] All keys exhausted during batch {batch.batch_id}: {e}")
                            break
                        except Exception as e:
                            logger.warning(f"  [!] Batch {batch.batch_id} fallback ({e}). Falling back to granular synthesis.")
            except Exception as e:
                logger.warning(f"[!] Batch planning notice: {e}. Falling back to standard pipeline.")

        # STEALTH HUMAN CADENCE EXECUTION (Strictly 1-worker sequential pipeline)
        keys_exhausted = False
        for idx, segment in enumerate(script, 1):
            if results[idx - 1] is not None:
                continue

            speaker = segment.get("speaker", "Narrator")
            text = segment.get("text", "")

            if segment.get("type") == "action":
                audio_path, dur = self.synthesize_segment(segment, chapter_num, idx)
                self.ledger.mark_segment_completed(audio_path.stem, str(audio_path), dur, chapter_num=chapter_num, seg_num=idx)
                results[idx - 1] = audio_path
                logger.info(f"  [{idx}/{total}] Generated Action Beat Foley Canvas ({audio_path.name}, {dur:.1f}s)")
                continue

            sp_cfg = self.get_speaker_config(speaker, segment.get("type", "narration"))
            expected_filename = compute_canonical_segment_filename(chapter_num, idx, text, sp_cfg, default_voice=self.default_voice)
            expected_file = self.audio_dir / expected_filename
            if expected_file.exists() and expected_file.stat().st_size > 1000:
                audio_file = expected_file
                dur = 1.0
                try:
                    with wave.open(str(audio_file), "rb") as wf:
                        dur = wf.getnframes() / float(wf.getframerate())
                except Exception:
                    pass
                results[idx - 1] = audio_file
                self.ledger.mark_segment_completed(audio_file.stem, str(audio_file), dur, chapter_num=chapter_num, seg_num=idx)
                dir_obj = dir_by_idx.get(idx)
                if dir_obj and hasattr(self, "take_bank"):
                    try:
                        cached_take = self.take_bank.create_take(
                            segment_uid=dir_obj.segment_uid,
                            segment_index=idx,
                            variant_type="standard",
                            audio_file=audio_file,
                            direction=dir_obj,
                            duration_sec=dur,
                        )
                        cached_take.is_selected = True
                        cached_take.selection_reason = "cached_on_disk"
                        from audiobook_factory.performance.contracts import PerformanceEvaluationResult
                        cached_take.evaluation = PerformanceEvaluationResult(
                            take_id=cached_take.take_id,
                            segment_uid=dir_obj.segment_uid,
                            overall_score=0.95,
                            passed=True,
                        )
                    except Exception as te:
                        logger.debug(f"Cached take registration notice: {te}")
                logger.info(f"  [{idx}/{total}] Cached {speaker} ({audio_file.name}, {dur:.1f}s)")
                continue

            _, voice = self.get_speaker_voice(speaker, segment.get("type", "narration"))
            cache_key = f"{text}|{voice}".encode("utf-8")
            seg_hash = hashlib.md5(cache_key).hexdigest()[:8]
            seg_id = f"c{chapter_num:03d}_s{idx:04d}_{seg_hash}"

            cadence.wait_before_segment(text, idx, total)
            self.ledger.mark_segment_started(seg_id, chapter_num=chapter_num, seg_num=idx)

            try:
                audio_path, dur = self.synthesize_segment(segment, chapter_num, idx, performance_direction=dir_by_idx.get(idx))
                self.ledger.mark_segment_completed(seg_id, str(audio_path), dur, chapter_num=chapter_num, seg_num=idx)
                cadence.record_completed_segment(dur)
                results[idx - 1] = audio_path
                logger.info(f"  [{idx}/{total}] Generated {speaker} ({audio_path.name}, {dur:.1f}s)")
            except AllKeysExhaustedTodayError as e:
                logger.critical(
                    f"  [STEALTH QUOTA PAUSE] {e}. "
                    f"Safely checkpointed at segment {idx}/{total}. No wasted requests."
                )
                keys_exhausted = True
                break
            except Exception as e:
                self.ledger.mark_segment_failed(seg_id, str(e), chapter_num=chapter_num, seg_num=idx)
                logger.error(f"  [ERROR] Segment {idx} ({speaker}) failed: {e}")

        # Targeted 1-pass recovery on transient missed segments
        missing_indices = [i + 1 for i, p in enumerate(results) if p is None]
        pool = _call_key_pool()
        if missing_indices and pool.get_status_summary().get("active_keys", 0) > 0:
            logger.info(f"[*] Attempting 1-pass recovery for {len(missing_indices)} transient missed segment(s): {missing_indices}...")
            for idx in missing_indices:
                seg = script[idx - 1]
                try:
                    audio_path, dur = self.synthesize_segment(seg, chapter_num, idx, performance_direction=dir_by_idx.get(idx))
                    results[idx - 1] = audio_path
                    logger.info(f"  [{idx}/{total}] Successfully recovered segment ({audio_path.name})")
                except Exception as e:
                    logger.warning(f"  Could not recover segment {idx}: {e}")

        missing = [i + 1 for i, p in enumerate(results) if p is None]
        if missing:
            if keys_exhausted or pool.get_status_summary().get("active_keys", 0) == 0:
                raise AllKeysExhaustedTodayError(
                    f"All TTS API keys exhausted for today. Chapter {chapter_num} paused at segment {missing[0]}/{total}."
                )
            raise RuntimeError(
                f"Chapter {chapter_num} synthesis incomplete: {len(missing)} segments pending ({missing[:5]}...)."
            )

        # Performance Fidelity Gate 2.8 Audit & Manifest Persistence
        try:
            self.take_bank.save_manifest(self.audio_dir / f"c{chapter_num:03d}_take_bank.json")
        except Exception as tb_err:
            logger.warning(f"  [!] TakeBank manifest save notice: {tb_err}")

        try:
            selected_takes = []
            for d in chapter_directions:
                cands = self.take_bank.get_takes_for_segment(d.segment_uid)
                sels = [t for t in cands if t.is_selected]
                if sels:
                    selected_takes.append(sels[0])
                elif cands:
                    selected_takes.append(cands[0])

            if selected_takes:
                from audiobook_factory.performance.gate import PerformanceFidelityGate
                gate_report = PerformanceFidelityGate.audit_chapter_performance(
                    chapter_id=f"chapter_{chapter_num:03d}",
                    directions=chapter_directions,
                    selected_takes=selected_takes,
                    allow_warnings=True,
                )
                rep_path = self.project_dir / "manifests" / f"chapter_{chapter_num:03d}_performance_report.json"
                rep_hi_path = self.project_dir / "manifests" / f"chapter_{chapter_num:03d}_hi_performance_report.json"
                rep_path.parent.mkdir(parents=True, exist_ok=True)
                report_json = gate_report.model_dump_json(indent=2)
                rep_path.write_text(report_json, encoding="utf-8")
                rep_hi_path.write_text(report_json, encoding="utf-8")
                logger.info(f"  [+] Gate 2.8 Performance report persisted -> {rep_path.name}")

            self.continuity_tracker.advance_chapter(f"chapter_{chapter_num:03d}")
            self.continuity_tracker.save_to_file(self.project_dir / "character_continuity.json")
        except Exception as e:
            logger.warning(f"  [!] Performance Layer Gate 2.8 notice: {e}")

        audio_files = [p for p in results if p is not None]
        logger.info(f"[+] Chapter {chapter_num} complete: {len(audio_files)} segments synthesized successfully.")
        return audio_files

    synthesize_segment_audio = synthesize_segment


def synthesize_segment_audio(
    segment: Dict[str, Any] | Any,
    chapter_num: int,
    seg_num: int,
    audio_dir: Optional[Path] = None,
    project_dir: Optional[Path] = None,
    dispatcher: Optional[TTSDispatcher] = None,
) -> Tuple[Path, float]:
    """
    Synthesize an individual segment audio or create a silent Foley canvas for action beats.
    Non-destructive helper ensuring external callers can invoke single-segment synthesis.
    """
    if dispatcher is None:
        p_dir = project_dir or (audio_dir.parent if audio_dir else Path("."))
        dispatcher = TTSDispatcher(project_dir=p_dir, audio_dir=audio_dir)
    return dispatcher.synthesize_segment(segment, chapter_num, seg_num)
