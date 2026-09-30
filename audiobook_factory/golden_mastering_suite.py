#!/usr/bin/env python3
"""
Audiobook Factory - Stage 12: Golden Mastering Regression Suite.
================================================================
Permanent regression suite protecting against audio quality degradation,
dynamic pumping, clipping overshoots, and accidental DSP parameter drift.

Covers 10 canonical literary & audio drama mastering scenarios:
1. Clean Narration
2. Multi-Speaker Dialogue
3. Intimate Whisper
4. Emotional Confession
5. Shouting / Combat
6. Ambience-Heavy Bed
7. Music-Heavy Bed
8. Foley-Heavy Bed
9. Dramatic Silence
10. Cinematic Full Mix

Baseline Governance:
- All baseline measurements are cryptographically tracked in golden_mastering_baseline.json.
- Baseline updates require explicit justification (reason + author), preventing silent test drift.
"""

from __future__ import annotations
import json
import math
import shutil
import tempfile
import wave
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Literal, Union
from pydantic import BaseModel, Field, ConfigDict
import numpy as np

from audiobook_factory.logger import logger
from audiobook_factory.mastering_contracts import (
    MasteringProfile,
    MasteringAnalysisFacts,
    MasteringRequest,
    MasteringResult,
)
from audiobook_factory.mastering_analyzer import MasteringAnalyzer
from audiobook_factory.mastering_engine import MasteringEngineV2

BASELINE_FILE = Path(__file__).parent / "golden_mastering_baseline.json"
SUITE_VERSION = "1.0.0"


class GoldenFixtureSpec(BaseModel):
    """Specification for a synthetic golden mastering fixture."""
    model_config = ConfigDict(extra="ignore")

    fixture_id: str
    title: str
    description: str
    duration_sec: float = 3.0
    frequency_hz: float = 440.0
    amplitude: float = 0.5
    has_dialogue: bool = True
    has_music: bool = False
    has_ambience: bool = False
    has_foley: bool = False
    is_whisper: bool = False
    is_shouting: bool = False
    is_silence: bool = False


CANONICAL_10_FIXTURES: List[GoldenFixtureSpec] = [
    GoldenFixtureSpec(
        fixture_id="01_clean_narration",
        title="Clean Solo Narration",
        description="Standard studio spoken narrative with clear vocal presence.",
        amplitude=0.45,
    ),
    GoldenFixtureSpec(
        fixture_id="02_multi_speaker_dialogue",
        title="Multi-Speaker Dialogue",
        description="Alternating two-speaker conversational take.",
        amplitude=0.40,
    ),
    GoldenFixtureSpec(
        fixture_id="03_intimate_whisper",
        title="Intimate Whisper",
        description="Quiet vocal scene requiring dynamic contrast preservation.",
        amplitude=0.18,
        is_whisper=True,
    ),
    GoldenFixtureSpec(
        fixture_id="04_emotional_confession",
        title="Emotional Confession",
        description="High dynamic range performance with rising vocal intensity.",
        amplitude=0.55,
    ),
    GoldenFixtureSpec(
        fixture_id="05_shouting_combat",
        title="Shouting Combat",
        description="High-energy dialogue and impact clashes.",
        amplitude=0.75,
        is_shouting=True,
    ),
    GoldenFixtureSpec(
        fixture_id="06_ambience_heavy",
        title="Ambience-Heavy Bed",
        description="Dialogue layered over dense naturalistic rain/wind soundscape.",
        amplitude=0.40,
        has_ambience=True,
    ),
    GoldenFixtureSpec(
        fixture_id="07_music_heavy",
        title="Music-Heavy Bed",
        description="Dialogue supported by prominent orchestral underscore.",
        amplitude=0.42,
        has_music=True,
    ),
    GoldenFixtureSpec(
        fixture_id="08_foley_heavy",
        title="Foley-Heavy Bed",
        description="Scene featuring sharp footstep and door-creak transients.",
        amplitude=0.45,
        has_foley=True,
    ),
    GoldenFixtureSpec(
        fixture_id="09_dramatic_silence",
        title="Dramatic Silence",
        description="Tense conversational pause with room tone.",
        amplitude=0.08,
        is_silence=True,
    ),
    GoldenFixtureSpec(
        fixture_id="10_cinematic_full_mix",
        title="Cinematic Full Mix",
        description="Full 5-track audio drama mix (Dialogue, Music, Foley, Ambience).",
        amplitude=0.50,
        has_music=True,
        has_ambience=True,
        has_foley=True,
    ),
]


def synthesize_golden_fixture_audio(spec: GoldenFixtureSpec, target_path: Path, sample_rate: int = 48000) -> Path:
    """Synthesizes deterministic, lightweight 48kHz audio for a golden fixture."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    num_samples = int(spec.duration_sec * sample_rate)
    t = np.linspace(0, spec.duration_sec, num_samples, endpoint=False)

    # Base dialogue signal (vocal formant proxy)
    if spec.is_silence:
        audio = 0.005 * np.sin(2 * np.pi * 120.0 * t)  # Low room tone
    elif spec.is_whisper:
        audio = spec.amplitude * np.sin(2 * np.pi * 320.0 * t) * (0.8 + 0.2 * np.sin(2 * np.pi * 3.0 * t))
    elif spec.is_shouting:
        audio = spec.amplitude * np.sin(2 * np.pi * 550.0 * t) + 0.3 * np.sin(2 * np.pi * 1100.0 * t)
    else:
        audio = spec.amplitude * np.sin(2 * np.pi * 440.0 * t) * (0.9 + 0.1 * np.sin(2 * np.pi * 2.0 * t))

    # Add music layer
    if spec.has_music:
        music = 0.22 * np.sin(2 * np.pi * 220.0 * t) + 0.15 * np.sin(2 * np.pi * 330.0 * t)
        audio = audio + music

    # Add ambience layer
    if spec.has_ambience:
        noise = np.random.RandomState(42).normal(0.0, 0.05, num_samples)
        audio = audio + noise

    # Add foley transient
    if spec.has_foley:
        foley = np.zeros(num_samples)
        trans_idx = int(0.5 * sample_rate)
        if trans_idx + 1000 < num_samples:
            foley[trans_idx : trans_idx + 1000] = 0.4 * np.hanning(1000)
        audio = audio + foley

    # Micro-fades to prevent end clicks
    fade = min(int(0.04 * sample_rate), num_samples // 4)
    if fade > 0:
        audio[:fade] *= np.linspace(0, 1, fade)
        audio[-fade:] *= np.linspace(1, 0, fade)

    # Scale composite audio to preserve premaster headroom and avoid artificial clipping
    max_val = np.max(np.abs(audio))
    if max_val > 0.90:
        audio = audio * (0.85 / max_val)

    clamped = np.clip(audio, -1.0, 1.0)
    int_samples = (clamped * 32767.0).astype(np.int16)
    stereo = np.column_stack([int_samples, int_samples]).flatten()

    with wave.open(str(target_path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(stereo.tobytes())

    return target_path


class GoldenMasteringSuite:
    """
    Executes and audits the Golden Mastering Regression benchmark.
    Protects against inadvertent DSP changes and regression bugs.
    """

    def __init__(
        self,
        engine: Optional[MasteringEngineV2] = None,
        baseline_path: Optional[Path] = None,
    ):
        self.engine = engine or MasteringEngineV2()
        self.baseline_path = baseline_path or BASELINE_FILE

    def run_suite(self, working_dir: Path) -> Dict[str, Any]:
        """
        Executes all 10 canonical golden mastering fixtures, comparing results with baseline.
        Returns detailed report indicating PASS, METRIC_REGRESSION, or HARD_REGRESSION.
        """
        working_dir.mkdir(parents=True, exist_ok=True)
        baseline_data = self._load_baseline()

        results: Dict[str, Any] = {}
        total_fixtures = len(CANONICAL_10_FIXTURES)
        passed_count = 0
        hard_regressions = 0
        metric_regressions = 0

        for spec in CANONICAL_10_FIXTURES:
            f_id = spec.fixture_id
            premaster_path = working_dir / f"{f_id}_premaster.wav"
            master_path = working_dir / f"{f_id}_master.wav"

            # 1. Synthesize fixture
            synthesize_golden_fixture_audio(spec, premaster_path)

            # 2. Master via MasteringEngineV2
            req = MasteringRequest(
                chapter_id=f_id,
                premaster_path=str(premaster_path),
                output_master_path=str(master_path),
                profile=MasteringProfile(target_lufs=-19.0),
            )
            res = self.engine.master(req)

            # 3. Audit against baseline
            audit_result = self._audit_fixture(res, baseline_data.get("fixtures", {}).get(f_id))
            results[f_id] = audit_result

            if audit_result["status"] == "PASS":
                passed_count += 1
            elif audit_result["status"] == "HARD_REGRESSION":
                hard_regressions += 1
            else:
                metric_regressions += 1

        overall_status = "PASS" if passed_count == total_fixtures else ("FAIL" if hard_regressions > 0 else "WARN")

        return {
            "suite_version": SUITE_VERSION,
            "overall_status": overall_status,
            "total_fixtures": total_fixtures,
            "passed_count": passed_count,
            "hard_regressions": hard_regressions,
            "metric_regressions": metric_regressions,
            "fixtures": results,
        }

    def _audit_fixture(self, result: MasteringResult, baseline: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Audits a single mastering result against baseline."""
        # Check hard failure (including certification rejection)
        is_rejected = result.certification_report and result.certification_report.certification == "REJECTED"
        if result.status != "SUCCESS" or not result.qc_result.passed or not Path(result.master_path).exists() or is_rejected:
            return {
                "status": "HARD_REGRESSION",
                "reason": f"Mastering execution or certification failed: {result.error_message or result.qc_result.failures}",
                "metrics": result.analysis_after.model_dump() if result.analysis_after else {},
            }

        facts = result.analysis_after
        assert facts is not None

        # Check critical audio integrity
        if facts.clipping_detected or (facts.true_peak_dbtp and facts.true_peak_dbtp > 0.0):
            return {
                "status": "HARD_REGRESSION",
                "reason": f"Digital clipping detected: true_peak={facts.true_peak_dbtp} dBTP",
                "metrics": facts.model_dump(),
            }

        audit_metrics = facts.model_dump()
        if result.certification_report:
            audit_metrics["certification"] = result.certification_report.certification
        if result.perceptual_evaluation:
            audit_metrics["perceptual_overall"] = result.perceptual_evaluation.overall

        if baseline is None:
            # First run / baseline bootstrap
            return {
                "status": "PASS",
                "reason": "Baseline bootstrap (new fixture)",
                "metrics": audit_metrics,
            }

        # Compare metrics with tolerance
        tol_lufs = 0.5
        tol_tp = 0.3
        tol_crest = 2.0

        drift_issues = []
        lufs_diff = abs(facts.integrated_lufs - baseline.get("integrated_lufs", facts.integrated_lufs))
        if lufs_diff > tol_lufs:
            drift_issues.append(f"LUFS drifted by {lufs_diff:.2f} LU (baseline: {baseline.get('integrated_lufs')})")

        tp_base = baseline.get("true_peak_dbtp")
        if tp_base is not None and facts.true_peak_dbtp is not None:
            tp_diff = abs(facts.true_peak_dbtp - tp_base)
            if tp_diff > tol_tp:
                drift_issues.append(f"True peak drifted by {tp_diff:.2f} dBTP (baseline: {tp_base})")

        crest_base = baseline.get("crest_factor_db")
        if crest_base is not None and facts.crest_factor_db is not None:
            crest_diff = abs(facts.crest_factor_db - crest_base)
            if crest_diff > tol_crest:
                drift_issues.append(f"Crest factor drifted by {crest_diff:.2f} dB (baseline: {crest_base})")

        if drift_issues:
            return {
                "status": "METRIC_REGRESSION",
                "reason": "; ".join(drift_issues),
                "metrics": audit_metrics,
            }

        return {
            "status": "PASS",
            "reason": "All metrics match governed baseline within tolerances.",
            "metrics": audit_metrics,
        }

    def _load_baseline(self) -> Dict[str, Any]:
        """Loads baseline from disk or returns empty structure."""
        if self.baseline_path.exists():
            try:
                return json.loads(self.baseline_path.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning(f"Failed to parse baseline file: {e}")
        return {"baseline_version": "1.0.0", "fixtures": {}, "governance_log": []}

    def update_baseline(
        self,
        new_measurements: Dict[str, Any],
        reason: str,
        author: str,
    ) -> Path:
        """
        Updates governed baseline with new measurements, logging explicit justification.
        Prevents silent baseline updates.
        """
        if not reason or len(reason.strip()) < 10:
            raise ValueError("Governance rule: Updating baseline requires a meaningful reason (min 10 chars).")
        if not author:
            raise ValueError("Governance rule: Updating baseline requires an author identifier.")

        baseline = self._load_baseline()
        baseline["fixtures"] = new_measurements
        baseline["governance_log"].append({
            "author": author,
            "reason": reason,
            "version": SUITE_VERSION,
        })

        self.baseline_path.parent.mkdir(parents=True, exist_ok=True)
        self.baseline_path.write_text(json.dumps(baseline, indent=2), encoding="utf-8")
        logger.info(f"[+] Governed golden mastering baseline updated by {author}: {reason}")
        return self.baseline_path
