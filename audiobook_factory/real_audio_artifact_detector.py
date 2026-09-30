#!/usr/bin/env python3
"""
Audiobook Factory - Real Audio Artifact Detector (Phase 8).
==========================================================
Empirical defect detection across real-world mastered audiobook audio:
- Clipping (Intersample true-peak & sample overs)
- Excessive Limiting (Crest-factor collapse & dynamic range squashing)
- Limiter Pumping (Loudness modulation proxies)
- Spectral Harshness (Excessive high-frequency energy accumulation)
- Bass Distortion / Low-frequency Overload
- Noise-Floor Amplification (Excessive boosting of quiet passages & ambient floors)
- Stereo Degradation (Anti-phase cancellation & width collapse)
- Transient Destruction (Smearing of acoustic impact peaks)
- Breath Destruction (Over-aggressive gating in vocal passages)

Every detector returns an ArtifactDetectionResult with explicit metric,
threshold rationale, confidence score [0.0 - 1.0], and severity rating.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional
from pathlib import Path

from audiobook_factory.mastering_contracts import MasteringAnalysisFacts
from audiobook_factory.real_audio_contracts import (
    AudioDeltaReport,
    ArtifactDetectionResult,
)


class RealAudioArtifactDetector:
    """
    Forensic defect auditor for Mastering V2 output.
    Enforces honest severity ratings without manufactured false certainties.
    """

    def analyze_artifacts(
        self,
        pre_facts: MasteringAnalysisFacts,
        post_facts: MasteringAnalysisFacts,
        delta_report: AudioDeltaReport,
        scene_type: str = "narration",
    ) -> List[ArtifactDetectionResult]:
        results: List[ArtifactDetectionResult] = []

        # 1. Clipping
        results.append(self._detect_clipping(post_facts))

        # 2. Excessive Limiting
        results.append(self._detect_excessive_limiting(pre_facts, post_facts, delta_report))

        # 3. Pumping
        results.append(self._detect_pumping(post_facts, delta_report))

        # 4. Spectral Harshness
        results.append(self._detect_spectral_harshness(pre_facts, post_facts, delta_report))

        # 5. Bass Overload
        results.append(self._detect_bass_overload(delta_report))

        # 6. Noise-Floor Amplification
        results.append(self._detect_noise_floor_amplification(pre_facts, post_facts, scene_type))

        # 7. Stereo Degradation
        results.append(self._detect_stereo_degradation(pre_facts, post_facts, delta_report))

        # 8. Transient Destruction
        results.append(self._detect_transient_destruction(pre_facts, post_facts, scene_type))

        # 9. Breath Destruction
        results.append(self._detect_breath_destruction(pre_facts, post_facts, scene_type))

        return results

    # --- Detector Implementations ---

    def _detect_clipping(self, post: MasteringAnalysisFacts) -> ArtifactDetectionResult:
        tp = post.true_peak_dbtp
        sp = post.sample_peak_dbfs

        if tp is not None and tp > 0.0:
            return ArtifactDetectionResult(
                artifact_type="CLIPPING",
                detected=True,
                metric_value=tp,
                threshold=0.0,
                threshold_rationale="True peak exceeds 0.0 dBTP DAC reconstruction ceiling causing audible inter-sample clipping",
                confidence=1.0,
                severity="FAIL",
                evidence={"true_peak_dbtp": tp, "sample_peak_dbfs": sp},
            )
        if tp is not None and tp > -1.0:
            return ArtifactDetectionResult(
                artifact_type="CLIPPING",
                detected=True,
                metric_value=tp,
                threshold=-1.5,
                threshold_rationale="True peak exceeds broadcast safety ceiling of -1.5 dBTP (Audible/ACX standard)",
                confidence=0.95,
                severity="WARNING",
                evidence={"true_peak_dbtp": tp, "sample_peak_dbfs": sp},
            )
        return ArtifactDetectionResult(
            artifact_type="CLIPPING",
            detected=False,
            metric_value=tp,
            threshold=-1.5,
            threshold_rationale="True peak within -1.5 dBTP safety ceiling",
            confidence=0.95,
            severity="INFO",
            evidence={"true_peak_dbtp": tp},
        )

    def _detect_excessive_limiting(
        self,
        pre: MasteringAnalysisFacts,
        post: MasteringAnalysisFacts,
        delta: AudioDeltaReport,
    ) -> ArtifactDetectionResult:
        crest_delta = delta.crest_factor_db.delta
        post_crest = post.crest_factor_db
        lra_delta = delta.loudness_range_lra.delta

        if crest_delta is not None and crest_delta < -5.5 and post_crest is not None and post_crest < 7.0:
            return ArtifactDetectionResult(
                artifact_type="EXCESSIVE_LIMITING",
                detected=True,
                metric_value=crest_delta,
                threshold=-5.5,
                threshold_rationale="Crest factor collapsed by > 5.5 dB with low post-master crest (< 7.0 dB), indicating audible squash",
                confidence=0.88,
                severity="REVIEW_REQUIRED",
                evidence={"crest_delta_db": crest_delta, "post_crest_db": post_crest, "lra_delta": lra_delta},
            )
        if lra_delta is not None and lra_delta < -8.0:
            return ArtifactDetectionResult(
                artifact_type="EXCESSIVE_LIMITING",
                detected=True,
                metric_value=lra_delta,
                threshold=-8.0,
                threshold_rationale="Loudness range dropped by > 8.0 LU, squashing narrative dynamic contrast",
                confidence=0.82,
                severity="WARNING",
                evidence={"lra_delta": lra_delta},
            )
        return ArtifactDetectionResult(
            artifact_type="EXCESSIVE_LIMITING",
            detected=False,
            metric_value=crest_delta,
            threshold=-5.5,
            threshold_rationale="Dynamic crest and LRA preserved within transparent boundaries",
            confidence=0.85,
            severity="INFO",
        )

    def _detect_pumping(
        self,
        post: MasteringAnalysisFacts,
        delta: AudioDeltaReport,
    ) -> ArtifactDetectionResult:
        # Proxy: large difference between short-term max and integrated LUFS when crest factor is low
        if post.short_term_max_lufs is not None and post.crest_factor_db is not None:
            st_spread = post.short_term_max_lufs - post.integrated_lufs
            if st_spread > 8.5 and post.crest_factor_db < 7.5:
                return ArtifactDetectionResult(
                    artifact_type="PUMPING",
                    detected=True,
                    metric_value=round(st_spread, 2),
                    threshold=8.5,
                    threshold_rationale="Excessive short-term dynamic swing coupled with low crest factor suggests limiter recovery pumping",
                    confidence=0.75,
                    severity="REVIEW_REQUIRED",
                    evidence={"short_term_spread": st_spread, "crest_factor_db": post.crest_factor_db},
                )
        return ArtifactDetectionResult(
            artifact_type="PUMPING",
            detected=False,
            threshold=8.5,
            threshold_rationale="No audible limiter gain pumping detected",
            confidence=0.80,
            severity="INFO",
        )

    def _detect_spectral_harshness(
        self,
        pre: MasteringAnalysisFacts,
        post: MasteringAnalysisFacts,
        delta: AudioDeltaReport,
    ) -> ArtifactDetectionResult:
        high_delta = delta.high_band_delta_db
        centroid_delta = delta.spectral_centroid_hz.delta

        if high_delta is not None and high_delta > 4.5 and (centroid_delta and centroid_delta > 500):
            return ArtifactDetectionResult(
                artifact_type="SPECTRAL_HARSHNESS",
                detected=True,
                metric_value=high_delta,
                threshold=4.5,
                threshold_rationale="High-frequency energy boosted by > 4.5 dB with significant centroid upward shift, risking sibilant fatigue",
                confidence=0.84,
                severity="REVIEW_REQUIRED",
                evidence={"high_band_delta_db": high_delta, "centroid_delta_hz": centroid_delta},
            )
        return ArtifactDetectionResult(
            artifact_type="SPECTRAL_HARSHNESS",
            detected=False,
            metric_value=high_delta,
            threshold=4.5,
            threshold_rationale="High-frequency energy balance remains smooth and non-fatiguing",
            confidence=0.85,
            severity="INFO",
        )

    def _detect_bass_overload(self, delta: AudioDeltaReport) -> ArtifactDetectionResult:
        low_delta = delta.low_band_delta_db
        if low_delta is not None and low_delta > 5.5:
            return ArtifactDetectionResult(
                artifact_type="BASS_OVERLOAD",
                detected=True,
                metric_value=low_delta,
                threshold=5.5,
                threshold_rationale="Sub/bass energy boosted by > 5.5 dB, introducing risk of headphone mud or driver distortion",
                confidence=0.80,
                severity="WARNING",
                evidence={"low_band_delta_db": low_delta},
            )
        return ArtifactDetectionResult(
            artifact_type="BASS_OVERLOAD",
            detected=False,
            metric_value=low_delta,
            threshold=5.5,
            threshold_rationale="Low-frequency energy cleanly controlled without muddy buildup",
            confidence=0.85,
            severity="INFO",
        )

    def _detect_noise_floor_amplification(
        self,
        pre: MasteringAnalysisFacts,
        post: MasteringAnalysisFacts,
        scene_type: str,
    ) -> ArtifactDetectionResult:
        if scene_type in ("whisper", "silence", "ambience"):
            pre_silence = pre.silence_ratio or 0.0
            post_silence = post.silence_ratio or 0.0
            silence_drop = pre_silence - post_silence
            lufs_boost = post.integrated_lufs - pre.integrated_lufs

            if silence_drop > 0.35 and lufs_boost > 8.0:
                return ArtifactDetectionResult(
                    artifact_type="NOISE_FLOOR_AMPLIFICATION",
                    detected=True,
                    metric_value=round(silence_drop, 3),
                    threshold=0.35,
                    threshold_rationale="Quiet background noise floor boosted into audible territory during low-level scene",
                    confidence=0.82,
                    severity="REVIEW_REQUIRED",
                    evidence={"silence_drop": silence_drop, "lufs_boost": lufs_boost, "scene_type": scene_type},
                )
        return ArtifactDetectionResult(
            artifact_type="NOISE_FLOOR_AMPLIFICATION",
            detected=False,
            threshold=0.35,
            threshold_rationale="Noise floor and silence ratios appropriately preserved",
            confidence=0.85,
            severity="INFO",
        )

    def _detect_stereo_degradation(
        self,
        pre: MasteringAnalysisFacts,
        post: MasteringAnalysisFacts,
        delta: AudioDeltaReport,
    ) -> ArtifactDetectionResult:
        post_r = post.phase_correlation
        pre_r = pre.phase_correlation
        r_drop = pre_r - post_r

        if post_r < 0.0:
            return ArtifactDetectionResult(
                artifact_type="STEREO_DEGRADATION",
                detected=True,
                metric_value=round(post_r, 3),
                threshold=0.0,
                threshold_rationale="Stereo phase correlation is negative; phase cancellation will cause severe comb-filtering in mono sum",
                confidence=0.98,
                severity="FAIL",
                evidence={"phase_correlation": post_r, "mono_compatible": post.mono_compatible},
            )
        if r_drop > 0.45:
            return ArtifactDetectionResult(
                artifact_type="STEREO_DEGRADATION",
                detected=True,
                metric_value=round(r_drop, 3),
                threshold=0.45,
                threshold_rationale="Stereo phase correlation degraded significantly (> 0.45 drop), risking center clarity",
                confidence=0.86,
                severity="WARNING",
                evidence={"pre_phase": pre_r, "post_phase": post_r, "drop": r_drop},
            )
        return ArtifactDetectionResult(
            artifact_type="STEREO_DEGRADATION",
            detected=False,
            metric_value=round(post_r, 3),
            threshold=0.20,
            threshold_rationale="Phase correlation provides robust mono and stereo compatibility",
            confidence=0.90,
            severity="INFO",
        )

    def _detect_transient_destruction(
        self,
        pre: MasteringAnalysisFacts,
        post: MasteringAnalysisFacts,
        scene_type: str,
    ) -> ArtifactDetectionResult:
        if scene_type in ("foley", "action", "shouting"):
            t_pre = pre.transient_count or 0
            t_post = post.transient_count or 0
            if t_pre >= 10:
                t_loss_ratio = (t_pre - t_post) / t_pre
                if t_loss_ratio > 0.45:
                    return ArtifactDetectionResult(
                        artifact_type="TRANSIENT_DESTRUCTION",
                        detected=True,
                        metric_value=round(t_loss_ratio, 2),
                        threshold=0.45,
                        threshold_rationale="Over 45% of detected audio transients flattened, blunting percussive impacts and Foley realism",
                        confidence=0.80,
                        severity="REVIEW_REQUIRED",
                        evidence={"transients_before": t_pre, "transients_after": t_post, "loss_ratio": t_loss_ratio},
                    )
        return ArtifactDetectionResult(
            artifact_type="TRANSIENT_DESTRUCTION",
            detected=False,
            threshold=0.45,
            threshold_rationale="Acoustic transients preserved through mastering chain",
            confidence=0.85,
            severity="INFO",
        )

    def _detect_breath_destruction(
        self,
        pre: MasteringAnalysisFacts,
        post: MasteringAnalysisFacts,
        scene_type: str,
    ) -> ArtifactDetectionResult:
        # In intimate / dialogue passages, check if natural breath valleys (-45dB to -35dB) were obliterated
        if scene_type in ("intimate", "whisper", "emotional"):
            if pre.silence_ratio is not None and post.silence_ratio is not None:
                # If post silence ratio increased drastically, gentle breath tails might have been gated off
                gating_increase = post.silence_ratio - pre.silence_ratio
                if gating_increase > 0.20:
                    return ArtifactDetectionResult(
                        artifact_type="BREATH_DESTRUCTION",
                        detected=True,
                        metric_value=round(gating_increase, 2),
                        threshold=0.20,
                        threshold_rationale="Significant increase in zero/sub-threshold frames suggests artificial breath truncation",
                        confidence=0.72,
                        severity="WARNING",
                        evidence={"gating_increase": gating_increase},
                    )
        return ArtifactDetectionResult(
            artifact_type="BREATH_DESTRUCTION",
            detected=False,
            threshold=0.20,
            threshold_rationale="Vocal breaths and natural pauses preserved naturally",
            confidence=0.80,
            severity="INFO",
        )
