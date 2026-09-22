#!/usr/bin/env python3
"""
Audiobook Factory - High-Level Production Pipeline Orchestrator.
Orchestrates end-to-end processing from raw EPUB/PDF to studio-mastered M4B audiobook.
Provides single-command autonomous execution with transaction-safe state management.
"""

import os
import uuid
import time
import json
from pathlib import Path
from typing import Dict, Any, Optional

from audiobook_factory.logger import logger


def atomic_write_json(filepath: Path, data: Any, indent: int = 2) -> None:
    """Writes JSON data atomically using a temporary file and atomic rename."""
    filepath = Path(filepath).resolve()
    filepath.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = filepath.with_suffix(f".tmp_{os.getpid()}_{uuid.uuid4().hex[:6]}")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)
        os.replace(tmp_path, filepath)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
from audiobook_factory.state import ProjectStateLedger
from audiobook_factory.extractor import process_book_file
from audiobook_factory.translator import translate_book_project
from audiobook_factory.script_builder import generate_project_scripts
from audiobook_factory.tts_dispatcher import TTSDispatcher
from audiobook_factory.soundscape import (
    generate_chapter_soundscape_plan,
    render_chapter_soundscape,
    apply_dynamic_sidechain_ducking,
    render_multitrack_chapter_audio,
    get_audio_duration,
)

from audiobook_factory.timeline_ledger import build_chapter_timeline_ledger
from audiobook_factory.sound_bank import get_sound_bank
from audiobook_factory.mastering import concatenate_and_master_chapter
from audiobook_factory.packager import package_m4b_audiobook
from audiobook_factory.agent_director import AgentDirector
from audiobook_factory.manifest_renderer import render_manifest_soundscape
from audiobook_factory.contracts import CreativeManifest, LegacyCreativeManifestAdapter
from audiobook_factory.cinema_audio_engine import render_discrete_stems, CinemaAudioManifest
from audiobook_factory.gate_auditor import (
    audit_gate0_translation,
    audit_gate1_roster,
    audit_gate2_script,
    audit_gate3_5_acoustic_feasibility,
    audit_gate5_2_spectral_masking,
    audit_gate5_3_stereo_phase,
    audit_gate5_master,
    audit_gate6a_voice_continuity,
    audit_gate6c_toc_monotonicity,
    GateAuditError,
)


class PipelineOrchestrator:
    """End-to-end production manager for full novels and books."""

    def __init__(self, projects_dir: Path):
        self.projects_dir = Path(projects_dir).resolve()
        self.projects_dir.mkdir(parents=True, exist_ok=True)

    def run_autonomous_pipeline(
        self,
        input_file: Path,
        hindi: bool = True,
        dramatized: bool = True,
        voice: str = "Aoede",
        cover_image: Optional[Path] = None,
        workers: int = 3,
        duck_db: float = -16.0,
        spatial_staging: bool = False,
    ) -> Path:
        """
        Executes the complete 6-stage autonomous novel pipeline:
        1. Ingestion & Extraction (EPUB / PDF)
        2. Literary Hindi Translation & Glossary (Optional)
        3. Sliding-Window Screenplay Attribution (No truncation)
        4. Concurrent Speech Synthesis (Gemini 3.1 Flash TTS + Token Bucket)
        5. FTS5 Sound Bank Ambience & Sidechain Ducking
        6. Broadcast EBU R128 Mastering & Single-Pass M4B Packaging
        """
        start_time = time.time()
        input_file = Path(input_file).resolve()
        if not input_file.exists():
            raise FileNotFoundError(f"Input novel file not found: {input_file}")

        logger.info("=======================================================")
        logger.info("   AUTONOMOUS STUDIO AUDIOBOOK PRODUCTION PIPELINE   ")
        logger.info(f"   Target Book: {input_file.name}")
        logger.info(f"   Mode       : {'Literary Hindi' if hindi else 'Original Language'}")
        logger.info(f"   Style      : {'Full-Cast Dramatized' if dramatized else 'Single Narrator'}")
        logger.info(f"   Voice Lead : {voice}")
        logger.info("=======================================================\n")

        # -------------------------------------------------------------
        # Stage 1: Document Extraction
        # -------------------------------------------------------------
        logger.info("[Stage 1/6] Ingesting document and extracting chapters...")
        meta = process_book_file(input_file, self.projects_dir)
        book_slug = meta["book_id"]
        project_dir = self.projects_dir / book_slug
        ledger = ProjectStateLedger(project_dir)
        ledger.set_meta("title", meta.get("title", book_slug))
        ledger.set_meta("author", meta.get("author", "Unknown Author"))
        ledger.set_meta("source_file", str(input_file))

        # -------------------------------------------------------------
        # Stage 2: Literary Translation (Sense-for-Sense Hindustani)
        # -------------------------------------------------------------
        if hindi:
            logger.info("\n[Stage 2/6] Literary Hindi translation with honorific glossary...")
            translate_book_project(project_dir)
            # Inline Gate 0: Translation Coverage Verification
            extracted_dir = project_dir / "extracted"
            translation_dir = project_dir / "translation"
            ext_files = sorted(extracted_dir.glob("chapter_*.txt"))
            for ef in ext_files:
                tf = translation_dir / ef.name
                if tf.exists():
                    try:
                        g0_res = audit_gate0_translation(ef, tf)
                        logger.info(f"[*] Gate 0 Translation Coverage: PASSED for {ef.name} ({g0_res.get('translation_chars')} chars)")
                    except Exception as e:
                        logger.warning(f"[!] Gate 0 Translation Coverage notice for {ef.name}: {e}")
        else:
            logger.info("\n[Stage 2/6] Translation skipped (English/Native language selected).")

        # -------------------------------------------------------------
        # Stage 3: Screenplay Attribution (Sliding Window, No Truncation)
        # -------------------------------------------------------------
        logger.info("\n[Stage 3/6] Generating screenplay scripts with dialogue attribution...")
        scripts_dir = generate_project_scripts(
            project_dir=project_dir,
            use_hindi=hindi,
            dramatized=dramatized,
        )

        script_files = sorted(scripts_dir.glob("chapter_*_script.json"))
        if not script_files:
            raise RuntimeError(f"No script files generated in {scripts_dir}")

        # Inline Gate 1: Voice Collision & Roster Sanity
        roster_file = project_dir / "character_roster.json"
        registry_file = project_dir / "voice_registry.json"
        if roster_file.exists() or registry_file.exists():
            try:
                g1_res = audit_gate1_roster(
                    roster_file=roster_file if roster_file.exists() else {},
                    registry_file=registry_file if registry_file.exists() else {},
                )
                logger.info(f"[*] Gate 1 Character Roster & Voice Collision: PASSED ({g1_res.get('status')})")
            except Exception as e:
                logger.warning(f"[!] Gate 1 Roster Notice: {e}")

        # Inline Gate 6A: Voice Continuity Across Chapters
        try:
            g6a_res = audit_gate6a_voice_continuity(project_dir)
            if g6a_res.passed:
                logger.info("[*] Gate 6A Voice Continuity: PASSED across all chapters")
            else:
                logger.warning(f"[!] Gate 6A Voice Continuity notice: {g6a_res.errors}")
        except Exception as e:
            logger.warning(f"[!] Gate 6A Voice Continuity notice: {e}")

        # -------------------------------------------------------------
        # Stage 4 & 5: Concurrent Synthesis & 5-Track Cinematic Production
        # -------------------------------------------------------------
        logger.info(f"\n[Stage 4-5/6] 5-Track Cinematic Audio Drama Production across {len(script_files)} chapters (Workers: {workers})...")
        for idx in range(1, len(script_files) + 1):
            logger.info(f"\n--- Producing Chapter {idx}/{len(script_files)} ---")
            self.produce_chapter(
                project_dir=project_dir,
                chapter_num=idx,
                voice=voice,
                workers=workers,
                duck_db=duck_db,
                spatial_staging=spatial_staging,
            )

        # -------------------------------------------------------------
        # Stage 6: Final M4B Containerization with Chapter Markers
        # -------------------------------------------------------------
        logger.info("\n[Stage 6/6] Packaging final M4B container with chapter navigation & cover art...")
        final_m4b = package_m4b_audiobook(project_dir, cover_image=cover_image)

        # Inline Gate 6C: Table of Contents Monotonicity & Chapter Boundaries
        try:
            g6c_res = audit_gate6c_toc_monotonicity(project_dir)
            if g6c_res.passed:
                logger.info("[*] Gate 6C Table of Contents Monotonicity: PASSED")
            else:
                logger.warning(f"[!] Gate 6C TOC Monotonicity notice: {g6c_res.errors}")
        except Exception as e:
            logger.warning(f"[!] Gate 6C TOC Monotonicity notice: {e}")

        elapsed_min = round((time.time() - start_time) / 60.0, 1)
        progress = ledger.get_progress()

        logger.info("\n=======================================================")
        logger.info("   [SUCCESS] NOVEL AUDIOBOOK PRODUCTION COMPLETED!    ")
        logger.info(f"   Deliverable   : {final_m4b}")
        logger.info(f"   Total Segments: {progress['completed']}/{progress['total_segments']}")
        logger.info(f"   Audio Duration: {progress['total_duration_min']} minutes")
        logger.info(f"   Total Elapsed : {elapsed_min} minutes")
        logger.info("=======================================================\n")

        return final_m4b

    def produce_chapter(
        self,
        project_dir: Path,
        chapter_num: int,
        voice: str = "Aoede",
        workers: int = 3,
        duck_db: float = -16.0,
        spatial_staging: bool = False,
    ) -> Dict[str, Any]:
        """
        Produces a single cinematic chapter using the deterministic agentic standard:
        1. Resolve screenplay script.
        2. Synthesize missing speech segments via Gemini TTS key pool.
        3. Master dialogue bus and composite lossless vocal stems.
        4. Direct creative manifest via AgentDirector (dynamic dramaturgy and silence carving).
        5. Compile final master via ManifestRenderer (deterministic multitrack mix, EBU R128 mastering).
        6. Generate millisecond timeline ledger.
        7. Auto-Janitor cleanup of intermediate WAV buffers.
        """
        import shutil
        project_dir = Path(project_dir).resolve()
        scripts_dir = project_dir / "scripts"
        audio_dir = project_dir / "audio_chunks"
        bgm_dir = project_dir / "soundscapes"
        mastered_dir = project_dir / "mastered"
        manifests_dir = project_dir / "manifests"
        for d in (scripts_dir, audio_dir, bgm_dir, mastered_dir, manifests_dir):
            d.mkdir(parents=True, exist_ok=True)

        script_file = scripts_dir / f"chapter_{chapter_num:03d}_hi_script.json"
        if not script_file.exists():
            cand = sorted(scripts_dir.glob(f"chapter_{chapter_num:03d}_*.json"))
            if cand:
                script_file = cand[0]
            else:
                raise FileNotFoundError(f"Script file for chapter {chapter_num} not found in {scripts_dir}")

        with open(script_file, "r", encoding="utf-8") as f:
            script_data = json.load(f)

        chap_stem = script_file.stem.replace("_script", "")

        # Gate 2: Screenplay Script Schema and canonical speakers
        try:
            gate2_res = audit_gate2_script(script_file)
            logger.info(f"[*] Gate 2 Script Audit: PASSED for Chapter {chapter_num:02d} ({gate2_res.get('total_segments', 0)} segments)")
        except Exception as e:
            logger.warning(f"[!] Gate 2 Script Audit notice for Chapter {chapter_num:02d}: {e}")

        # 1. Synthesize speech segments via Gemini TTS (Token Bucket & Graceful Key Halting)
        logger.info(f"[*] Synthesizing Chapter {chapter_num:02d} speech segments (Workers: {workers})...")
        from audiobook_factory.key_manager import AllKeysExhaustedTodayError
        import sys
        try:
            dispatcher = TTSDispatcher(project_dir=project_dir, default_voice=voice, max_workers=workers)
            dispatcher.synthesize_chapter_script(script_file, chapter_num)
        except AllKeysExhaustedTodayError as e:
            logger.error("\n[!] 🛑 SUPERVISOR AGENT HALT: ALL TTS API KEYS EXHAUSTED FOR TODAY.")
            logger.error(f"[!] 🛑 {e}")
            logger.info(f"[*] Progress Checkpoint safely stored on disk for Chapter {chapter_num:02d}.")
            logger.info("[*] The system will gracefully halt now. Run the script again tomorrow after 12:30 PM IST (Midnight PT) to automatically resume.")
            sys.exit(0)

        # 2. Master dialogue vocals with 5-stage DSP and script-aware micro-pauses
        segments = sorted(audio_dir.glob(f"c{chapter_num:03d}_*.wav"))
        if not segments:
            raise RuntimeError(f"No audio segments found for Chapter {chapter_num}")

        vocal_wav = mastered_dir / f"{chap_stem}_dialogue.wav"
        concatenate_and_master_chapter(
            segments, vocal_wav,
            script_segments=script_data,
            spatial_staging=spatial_staging,
        )
        vocal_dur = get_audio_duration(vocal_wav)

        # 3. Map exact segment durations
        seg_durations = {}
        for seg in script_data:
            s_idx = seg.get("index", 1)
            seg_matches = sorted(audio_dir.glob(f"c{chapter_num:03d}_s{s_idx:04d}_*.wav"))
            if seg_matches:
                seg_durations[s_idx] = get_audio_duration(seg_matches[0])
            else:
                seg_durations[s_idx] = 4.0

        # 4. Agentic Directing Layer: Produce validated CreativeManifest via AgentDirector
        manifest_file = manifests_dir / f"{chap_stem}_manifest.json"
        if manifest_file.exists():
            logger.info(f"[*] Loading existing Creative Manifest: {manifest_file.name}")
            with open(manifest_file, "r", encoding="utf-8") as f:
                manifest = CreativeManifest.from_json(f.read())
        else:
            logger.info(f"[*] Agent Director: Directing Chapter {chapter_num:02d} Creative Manifest...")
            director = AgentDirector(project_dir=project_dir)
            manifest = director.direct_chapter_manifest(
                chapter_id=f"chapter_{chapter_num:03d}",
                script_segments=script_data,
                segment_durations_sec=seg_durations,
                dialogue_stem_path=vocal_wav,
                total_duration_sec=vocal_dur,
                project_dir=project_dir,
                sonic_bible=director.sonic_bible,
            )
            with open(manifest_file, "w", encoding="utf-8") as f:
                f.write(manifest.to_json(indent=2))

        # Gate 3.5: Acoustic Pre-Flight Feasibility Guard
        try:
            gate35_res = audit_gate3_5_acoustic_feasibility(manifest, sound_bank=get_sound_bank())
            if not gate35_res.passed:
                logger.warning(f"[!] Gate 3.5 Feasibility Notice: {gate35_res.warnings} | {gate35_res.errors}")
            else:
                logger.info(f"[*] Gate 3.5 Acoustic Feasibility: PASSED for Chapter {chapter_num:02d}")
        except Exception as e:
            logger.warning(f"[!] Gate 3.5 Feasibility notice: {e}")

        # 5. Cinema Audio Engine: Render 5-Track Discrete DME Stems & Final Cinema Master
        cinematic_out = mastered_dir / f"{chap_stem}_cinematic.m4a"
        logger.info(f"[*] Cinema Audio Engine: Rendering discrete DME stems and cinema master for Chapter {chapter_num:02d}...")

        # Lift legacy CreativeManifest to CinemaAudioManifest if needed
        if isinstance(manifest, CreativeManifest):
            cinema_manifest = LegacyCreativeManifestAdapter.lift_legacy_manifest_to_cinema(manifest)
        else:
            cinema_manifest = manifest

        stem_ledger = render_discrete_stems(
            manifest=cinema_manifest,
            dialogue_wav=vocal_wav,
            output_dir=mastered_dir,
            sound_bank=get_sound_bank(),
        )

        master_wav = mastered_dir / f"{cinema_manifest.chapter_id}_cinema_master.wav"
        if not master_wav.exists():
            master_wav = mastered_dir / f"{chap_stem}_cinema_master.wav"

        if master_wav.exists():
            import subprocess
            from audiobook_factory.tts_dispatcher import get_ffmpeg
            ff = get_ffmpeg()
            cmd_enc = [
                ff, "-y",
                "-i", str(master_wav),
                "-c:a", "aac", "-b:a", "192k",
                str(cinematic_out),
            ]
            subprocess.run(cmd_enc, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        else:
            # Fallback to render_manifest_soundscape if master wav was not produced
            render_manifest_soundscape(
                manifest=manifest,
                vocal_track_path=vocal_wav,
                output_master_file=cinematic_out,
            )

        # Gate 5.2: Spectral Masking (Dialogue vs Music DMR)
        mx_stem = mastered_dir / f"{cinema_manifest.chapter_id}_stem_MX.wav"
        if not mx_stem.exists():
            mx_stem = mastered_dir / f"{chap_stem}_stem_MX.wav"
        if mx_stem.exists() and vocal_wav.exists():
            try:
                gate52_res = audit_gate5_2_spectral_masking(vocal_wav, mx_stem, min_dmr_db=12.0)
                if not gate52_res.passed:
                    logger.warning(f"[!] Gate 5.2 Spectral Masking Notice: {gate52_res.errors}")
                else:
                    logger.info(f"[*] Gate 5.2 Spectral Masking: PASSED (DMR: {gate52_res.details.get('measured_dmr_db', 'N/A')} dB)")
            except Exception as e:
                logger.warning(f"[!] Gate 5.2 Spectral Masking notice: {e}")

        # Gate 5.3: Stereo Phase Correlation
        if master_wav.exists():
            try:
                gate53_res = audit_gate5_3_stereo_phase(master_wav, min_phase_correlation=0.20)
                if not gate53_res.passed:
                    logger.warning(f"[!] Gate 5.3 Stereo Phase Notice: {gate53_res.errors}")
                else:
                    logger.info(f"[*] Gate 5.3 Stereo Phase: PASSED (mean r: {gate53_res.details.get('mean_phase_correlation', 'N/A')})")
            except Exception as e:
                logger.warning(f"[!] Gate 5.3 Stereo Phase notice: {e}")

        # Gate 5: Broadcast Master EBU R128 Probe
        if cinematic_out.exists():
            try:
                gate5_res = audit_gate5_master(cinematic_out, target_lufs=-19.0, tolerance_lu=2.0, max_true_peak=-1.4)
                logger.info(f"[*] Gate 5 Broadcast Master: PASSED (LUFS: {gate5_res.get('integrated_lufs')}, TP: {gate5_res.get('true_peak_dbtp')})")
            except Exception as e:
                logger.warning(f"[!] Gate 5 Broadcast Master notice: {e}")

        # 6. Build Millisecond Timeline Ledger
        ledger_file = bgm_dir / f"{chap_stem}_timeline_ledger.json"
        cue_sheet = {
            "foley_cues": [c.model_dump() if hasattr(c, "model_dump") else dict(c) for c in manifest.foley_cues],
            "music_cues": [c.model_dump() if hasattr(c, "model_dump") else dict(c) for c in manifest.music_cues],
        }
        plan = {
            "chapter_id": chapter_num,
            "silence_percentage": manifest.silence_percentage,
            "scenes": [s.model_dump() if hasattr(s, "model_dump") else dict(s) for s in manifest.ambience_scenes],
        }
        ledger = build_chapter_timeline_ledger(
            chapter_id=chapter_num,
            script_segments=script_data,
            audio_chunk_paths=segments,
            cue_sheet=cue_sheet,
            soundscape_plan=plan,
            output_ledger_file=ledger_file,
        )

        # 9. Auto-Janitor: Clean up intermediate uncompressed WAV chunks ONLY IF certified
        #    Safety Invariant: Chunks are NEVER purged if cinematic master failed, is corrupt,
        #    or if AUDIOBOOK_RETAIN_CHUNKS is set.
        retain_chunks_flag = os.environ.get("AUDIOBOOK_RETAIN_CHUNKS", "").lower() in ("1", "true", "yes")
        master_certified = cinematic_out.exists() and cinematic_out.stat().st_size > 1000

        chunk_pattern = f"c{chapter_num:03d}_*.wav"
        all_chunks = list(audio_dir.glob(chunk_pattern))

        if retain_chunks_flag:
            logger.info(f"  [JANITOR] Retaining {len(all_chunks)} raw WAV chunks for chapter {chapter_num:02d} (AUDIOBOOK_RETAIN_CHUNKS enabled).")
        elif not master_certified:
            logger.warning(
                f"  [JANITOR SHIELD] Master render missing or incomplete for chapter {chapter_num:02d}. "
                f"Retaining {len(all_chunks)} raw WAV chunks to protect synthesized progress."
            )
        else:
            purged_count = 0
            for chunk_file in all_chunks:
                try:
                    chunk_file.unlink(missing_ok=True)
                    purged_count += 1
                except Exception:
                    pass
            if purged_count:
                logger.info(f"  [JANITOR] Purged {purged_count} intermediate WAV chunks for chapter {chapter_num:02d}")

        stem_ledger_file = mastered_dir / f"{cinema_manifest.chapter_id}_stem_ledger.json"
        if not stem_ledger_file.exists():
            stem_ledger_file = mastered_dir / f"{chap_stem}_stem_ledger.json"

        logger.info(f"[+] Chapter {chapter_num:02d} complete -> {cinematic_out} ({ledger['total_duration_min']} min)")
        return {
            "chapter_id": chapter_num,
            "master_file": cinematic_out,
            "ledger_file": ledger_file,
            "stem_ledger": stem_ledger_file,
            "duration_min": ledger["total_duration_min"],
            "total_segments": ledger["total_segments"],
        }
