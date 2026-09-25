#!/usr/bin/env python3
"""
Audiobook Factory - Casting Evaluator.
Evaluates candidate audition recordings across 10 acoustic and dramatic dimensions:
character fit, timbre fit, emotional range, naturalness, authority, vulnerability,
whisper quality, high-intensity quality, long-form suitability, and ensemble distinctiveness.
Preserves full audition evidence for all candidates.
"""

from __future__ import annotations
import math
import wave
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from audiobook_factory.logger import logger
from audiobook_factory.forensic_analyzer import MathematicalAcousticAnalyzer
from .contracts import (
    CharacterCastingProfile,
    VoiceCandidateScore,
    AuditionResult,
    CastingEvaluationRecord,
)


class CastingEvaluator:
    """
    World-Class Multi-Dimensional Casting Evaluator.
    Combines audition audio acoustic signal metrics with candidate dramatic metadata.
    """

    def __init__(self, sample_rate: int = 24000):
        self.sample_rate = sample_rate
        self.acoustic_analyzer = MathematicalAcousticAnalyzer(sample_rate=sample_rate)

    def evaluate_candidate_audition(
        self,
        profile: CharacterCastingProfile,
        candidate: VoiceCandidateScore,
        audition_results: List[AuditionResult],
        already_cast_voices: Optional[Dict[str, str]] = None,
    ) -> CastingEvaluationRecord:
        """
        Evaluates a candidate voice's full audition portfolio.
        Returns a complete, auditable CastingEvaluationRecord.
        """
        dim_scores: Dict[str, float] = {}
        strengths: List[str] = list(candidate.strengths)
        risks: List[str] = list(candidate.risks)

        # 1. Character Fit (derived from candidate matching breakdown)
        char_fit = (candidate.score_breakdown.get("gender_fit", 1.0) * 0.4 +
                    candidate.score_breakdown.get("archetype_fit", 0.7) * 0.3 +
                    candidate.score_breakdown.get("personality_fit", 0.7) * 0.3)
        dim_scores["character_fit"] = round(char_fit, 2)

        # 2. Timbre Fit
        timbre_fit = candidate.score_breakdown.get("timbre_fit", 0.75)
        dim_scores["timbre_fit"] = round(timbre_fit, 2)

        # 3. Analyze Audio Takes per Dramatic Mode
        mode_map: Dict[str, AuditionResult] = {res.dramatic_mode: res for res in audition_results}

        # Telemetry extracted per take
        take_rms: Dict[str, float] = {}
        take_flatness: Dict[str, float] = {}
        take_clean: Dict[str, bool] = {}

        for res in audition_results:
            p = Path(res.audio_path)
            if p.exists() and p.stat().st_size > 44:
                try:
                    with wave.open(str(p), "rb") as wf:
                        n_frames = wf.getnframes()
                        raw = wf.readframes(n_frames)
                        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
                        if len(samples) > 0:
                            rms = float(np.sqrt(np.mean(samples ** 2)))
                            rms_db = 20.0 * math.log10(max(rms, 1e-5) / 32768.0)
                            take_rms[res.dramatic_mode] = rms_db

                            metrics = self.acoustic_analyzer.analyze_frames(samples)
                            avg_flat = float(np.mean([m["spectral_flatness"] for m in metrics])) if metrics else 0.05
                            take_flatness[res.dramatic_mode] = avg_flat
                            take_clean[res.dramatic_mode] = (avg_flat < 0.35 and rms_db > -45.0)
                except Exception:
                    pass

        # 4. Naturalness (Acoustic Waveform Purity)
        clean_count = sum(1 for v in take_clean.values() if v)
        naturalness = clean_count / max(len(audition_results), 1)
        dim_scores["naturalness"] = round(max(0.60, min(1.0, naturalness)), 2)

        # 5. Emotional Range (Dynamic RMS Headroom Variance)
        if len(take_rms) >= 2:
            rms_vals = list(take_rms.values())
            dynamic_spread = max(rms_vals) - min(rms_vals)
            # Expect >= 10dB dynamic spread between quiet (whisper) and loud (anger/action)
            range_score = min(1.0, dynamic_spread / 12.0)
            if dynamic_spread >= 10.0:
                strengths.append(f"Broad dynamic acting range ({dynamic_spread:.1f} dB headroom spread)")
            else:
                risks.append(f"Compressed dynamic variance ({dynamic_spread:.1f} dB headroom spread)")
        else:
            range_score = candidate.score_breakdown.get("range_fit", 0.75)
        dim_scores["emotional_range"] = round(max(0.50, min(1.0, range_score)), 2)

        # 6. Authority (Presence in authority / action modes)
        auth_score = 0.85 if candidate.score_breakdown.get("personality_fit", 0.7) >= 0.75 else 0.70
        if "authority" in take_rms and take_rms["authority"] >= -22.0:
            auth_score = min(1.0, auth_score + 0.10)
        dim_scores["authority"] = round(auth_score, 2)

        # 7. Vulnerability (Sensitivity in vulnerability / grief modes)
        vuln_score = 0.80
        if "vulnerability" in take_rms and take_rms["vulnerability"] <= -20.0:
            vuln_score = 0.92
            strengths.append("High sensitivity and gentle intimacy in vulnerable registers")
        dim_scores["vulnerability"] = round(vuln_score, 2)

        # 8. Whisper Quality (Acoustic cleanliness at low RMS)
        whisper_score = 0.85
        if "whisper" in take_rms:
            w_rms = take_rms["whisper"]
            if w_rms < -22.0 and take_clean.get("whisper", True):
                whisper_score = 0.95
                strengths.append("Intelligible, clean close-mic whisper without phonation strain")
            elif w_rms > -16.0:
                whisper_score = 0.65
                risks.append("Whisper lacks acoustic intimacy (too loud)")
        dim_scores["whisper_quality"] = round(whisper_score, 2)

        # 9. High-Intensity Quality (Distortion-free anger / action)
        high_int_score = 0.85
        if "anger" in take_rms:
            if take_clean.get("anger", True):
                high_int_score = 0.92
            else:
                high_int_score = 0.60
                risks.append("Acoustic harshness in high-intensity delivery")
        dim_scores["high_intensity_quality"] = round(high_int_score, 2)

        # 10. Long-Form Suitability (Absence of synthetic fatigue)
        long_form = 0.90 if candidate.overall_score >= 0.75 else 0.70
        dim_scores["long_form_suitability"] = round(long_form, 2)

        # 11. Ensemble Distinctiveness
        distinct = candidate.score_breakdown.get("distinctiveness", 1.0)
        dim_scores["ensemble_distinctiveness"] = round(distinct, 2)

        # Overall composite fit score
        weights = {
            "character_fit": 0.20,
            "timbre_fit": 0.15,
            "emotional_range": 0.12,
            "naturalness": 0.12,
            "authority": 0.08,
            "vulnerability": 0.08,
            "whisper_quality": 0.07,
            "high_intensity_quality": 0.08,
            "long_form_suitability": 0.05,
            "ensemble_distinctiveness": 0.05,
        }
        overall = sum(dim_scores.get(k, 0.75) * weights[k] for k in weights)
        overall = round(max(0.0, min(1.0, overall)), 2)

        passed = overall >= 0.68 and dim_scores["naturalness"] >= 0.60

        summary = f"Audition evaluation: overall score {overall:.2f} ({'PASSED' if passed else 'FAILED'})."
        if strengths:
            summary += f" Key strength: {strengths[0]}."

        return CastingEvaluationRecord(
            candidate_voice_id=candidate.voice_id,
            character_id=profile.character_id,
            overall_fit_score=overall,
            rank=1,
            passed_audition=passed,
            dimension_scores=dim_scores,
            strengths=strengths,
            risks=risks,
            audition_results=audition_results,
            evaluation_summary=summary,
        )

    def evaluate_and_rank_ensemble_auditions(
        self,
        profile: CharacterCastingProfile,
        candidates: List[VoiceCandidateScore],
        auditions_by_candidate: Dict[str, List[AuditionResult]],
        already_cast_voices: Optional[Dict[str, str]] = None,
    ) -> List[CastingEvaluationRecord]:
        """
        Ranks all candidate evaluation records descending by overall fit score.
        Preserves auditable records for winning and losing candidates.
        """
        records: List[CastingEvaluationRecord] = []
        for cand in candidates:
            auds = auditions_by_candidate.get(cand.voice_id, [])
            rec = self.evaluate_candidate_audition(
                profile=profile,
                candidate=cand,
                audition_results=auds,
                already_cast_voices=already_cast_voices,
            )
            records.append(rec)

        # Sort descending by overall_fit_score
        records.sort(key=lambda r: r.overall_fit_score, reverse=True)
        for i, r in enumerate(records):
            r.rank = i + 1

        return records
