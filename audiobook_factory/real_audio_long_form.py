#!/usr/bin/env python3
"""
Audiobook Factory - Real Audio Long-Form Stress Tester (Phase 9 & 10).
====================================================================
Validates cumulative audio stability across an extended multi-scene sequence:
narration -> dialogue -> quiet -> emotional -> music -> action
-> whisper -> ambience -> shouting -> silence -> dialogue -> music
-> chapter transition.

Evaluates:
- Cumulative loudness drift and consistency
- Spectral centroid drift across scene transitions
- Fatigue risk index (sustained high energy / low dynamic relief)
- Repeated peak limiter interactions
- Identifies outlier scenes without hiding them behind global averages
"""

from __future__ import annotations
import math
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
import soundfile as sf

from audiobook_factory.mastering_contracts import (
    MasteringProfile,
    MasteringRequest,
    MasteringResult,
    MasteringAnalysisFacts,
)
from audiobook_factory.mastering_engine import MasteringEngineV2
from audiobook_factory.mastering_analyzer import MasteringAnalyzer
from audiobook_factory.real_audio_contracts import (
    LongFormSceneEvent,
    LongFormReport,
)


class RealAudioLongFormStressTester:
    """
    Constructs, masters, and forensically audits an extended chapter timeline
    composed of diverse realistic dramatic scenes.
    """

    def __init__(self, engine: Optional[MasteringEngineV2] = None, analyzer: Optional[MasteringAnalyzer] = None):
        self.engine = engine or MasteringEngineV2()
        self.analyzer = analyzer or MasteringAnalyzer()

    def assemble_long_form_premaster(
        self,
        fixtures_dir: Path,
        output_wav: Path,
    ) -> List[Tuple[str, str, float, float]]:
        """
        Assembles continuous sequence:
        narration -> dialogue -> quiet -> emotional -> music -> action
        -> whisper -> ambience -> shouting -> silence -> dialogue -> music
        -> chapter transition.
        Returns list of (scene_id, scene_type, start_sec, end_sec).
        """
        sequence = [
            ("sc01_narration", "narration", fixtures_dir / "real_01_narration.wav"),
            ("sc02_dialogue", "dialogue", fixtures_dir / "real_02_dialogue.wav"),
            ("sc03_quiet", "whisper", fixtures_dir / "real_03_whisper.wav"),
            ("sc04_emotional", "emotional", fixtures_dir / "real_05_emotional.wav"),
            ("sc05_music", "music_heavy", fixtures_dir / "real_07_music_heavy.wav"),
            ("sc06_action", "action", fixtures_dir / "real_10_action.wav"),
            ("sc07_whisper", "whisper", fixtures_dir / "real_03_whisper.wav"),
            ("sc08_ambience", "ambience", fixtures_dir / "real_08_ambience.wav"),
            ("sc09_shouting", "shouting", fixtures_dir / "real_04_shouting.wav"),
            ("sc10_silence", "silence", fixtures_dir / "real_11_silence.wav"),
            ("sc11_hindi_dialogue", "hindi_hinglish", fixtures_dir / "real_06_hindi_hinglish.wav"),
            ("sc12_music_finale", "music_heavy", fixtures_dir / "real_07_music_heavy.wav"),
        ]

        sr = 48000
        audio_blocks: List[np.ndarray] = []
        timeline: List[Tuple[str, str, float, float]] = []
        current_time = 0.0

        for sc_id, sc_type, sc_path in sequence:
            if not sc_path.exists():
                raise FileNotFoundError(f"Fixture missing for long-form: {sc_path}")
            data, f_sr = sf.read(str(sc_path), always_2d=True)
            dur = len(data) / f_sr
            audio_blocks.append(data.astype(np.float32))

            # Small 250ms inter-scene breathing transition
            pause = np.zeros((int(0.25 * sr), 2), dtype=np.float32)
            audio_blocks.append(pause)

            start = round(current_time, 2)
            end = round(current_time + dur, 2)
            timeline.append((sc_id, sc_type, start, end))
            current_time += dur + 0.25

        # Final chapter transition gap (1.0s room tone / silence)
        room_tone = np.zeros((int(1.0 * sr), 2), dtype=np.float32)
        audio_blocks.append(room_tone)

        concatenated = np.vstack(audio_blocks)
        output_wav.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(output_wav), concatenated, sr)

        return timeline

    def run_stress_test(
        self,
        fixtures_dir: Path,
        work_dir: Path,
        profile: Optional[MasteringProfile] = None,
    ) -> Tuple[MasteringResult, LongFormReport]:
        work_dir.mkdir(parents=True, exist_ok=True)
        premaster_path = work_dir / "long_form_premaster.wav"
        timeline = self.assemble_long_form_premaster(fixtures_dir, premaster_path)

        # Master long-form audio through MasteringEngineV2
        m_profile = profile or MasteringProfile()
        req = MasteringRequest(
            chapter_id="long_form_stress_ch01",
            premaster_path=str(premaster_path),
            profile=m_profile,
        )
        res = self.engine.master(req)

        # Post-master analysis on overall track
        overall_facts = res.analysis_after or self.analyzer.analyze(res.master_path)

        # Sliced analysis for each scene
        master_data, sr = sf.read(res.master_path, always_2d=True)
        scene_events: List[LongFormSceneEvent] = []
        scene_lufs_list: List[float] = []
        centroids_list: List[float] = []
        limiter_active_count = 0
        outliers: List[str] = []

        for sc_id, sc_type, start_sec, end_sec in timeline:
            start_idx = int(start_sec * sr)
            end_idx = min(len(master_data), int(end_sec * sr))
            slice_data = master_data[start_idx:end_idx]

            # Save temporary slice to analyze via MasteringAnalyzer
            slice_path = work_dir / f"slice_{sc_id}.wav"
            sf.write(str(slice_path), slice_data, sr)
            sc_facts = self.analyzer.analyze(slice_path)
            slice_path.unlink(missing_ok=True)

            sc_lufs = sc_facts.integrated_lufs
            sc_tp = sc_facts.true_peak_dbtp or 0.0
            sc_lra = sc_facts.loudness_range_lra or 6.0
            sc_centroid = sc_facts.spectral_centroid_hz or 1000.0

            limiter_engaged = sc_tp > -1.6
            if limiter_engaged:
                limiter_active_count += 1

            scene_lufs_list.append(sc_lufs)
            centroids_list.append(sc_centroid)

            scene_events.append(
                LongFormSceneEvent(
                    scene_id=sc_id,
                    scene_type=sc_type,
                    start_sec=start_sec,
                    end_sec=end_sec,
                    integrated_lufs=sc_lufs,
                    true_peak_dbtp=sc_tp,
                    loudness_range_lra=sc_lra,
                    spectral_centroid_hz=sc_centroid,
                    limiter_active=limiter_engaged,
                )
            )

        # Compute drift metrics
        valid_lufs = [l for l in scene_lufs_list if l > -40.0]  # Exclude intentional silence
        lufs_drift = round(max(valid_lufs) - min(valid_lufs), 2) if valid_lufs else 0.0
        centroid_drift = round(max(centroids_list) - min(centroids_list), 1) if centroids_list else 0.0

        # Outlier identification (scenes deviating > 4.5 LU from median)
        med_lufs = float(np.median(valid_lufs)) if valid_lufs else -19.0
        for ev in scene_events:
            if ev.scene_type != "silence" and abs(ev.integrated_lufs - med_lufs) > 4.5:
                outliers.append(f"{ev.scene_id} ({ev.scene_type}: {ev.integrated_lufs} LUFS vs median {round(med_lufs, 1)})")

        # Fatigue risk: sustained loudness with low LRA and high centroid
        fatigue_risk = 0.10
        if overall_facts.integrated_lufs > -17.5:
            fatigue_risk += 0.35
        if overall_facts.loudness_range_lra and overall_facts.loudness_range_lra < 4.5:
            fatigue_risk += 0.30
        if overall_facts.spectral_centroid_hz and overall_facts.spectral_centroid_hz > 2800.0:
            fatigue_risk += 0.25
        fatigue_risk = min(1.0, round(fatigue_risk, 2))

        # Overall long-form status
        notes: List[str] = []
        if overall_facts.true_peak_dbtp and overall_facts.true_peak_dbtp > -1.5:
            status = "REVIEW_REQUIRED"
            notes.append(f"Long-form peak {overall_facts.true_peak_dbtp} dBTP exceeds -1.5 dBTP margin")
        elif len(outliers) > 2 or fatigue_risk > 0.70:
            status = "REVIEW_REQUIRED"
            notes.append("High fatigue risk or multiple dynamic outliers detected across long-form run")
        else:
            status = "PASS"

        report = LongFormReport(
            total_duration_sec=round(overall_facts.duration_sec, 2),
            scene_count=len(timeline),
            overall_lufs=round(overall_facts.integrated_lufs, 2),
            overall_lra=round(overall_facts.loudness_range_lra or 0.0, 2),
            max_true_peak_dbtp=round(overall_facts.true_peak_dbtp or 0.0, 2),
            lufs_drift_max_db=lufs_drift,
            spectral_drift_hz=centroid_drift,
            repeated_limiter_occurrences=limiter_active_count,
            fatigue_risk_index=fatigue_risk,
            scene_timeline=scene_events,
            outlier_scenes=outliers,
            status=status,
            notes=notes,
        )

        return res, report
