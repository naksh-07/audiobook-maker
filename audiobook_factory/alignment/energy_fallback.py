#!/usr/bin/env python3
"""
Audiobook Factory - Alignment Engine: Acoustic Energy Valley Fallback Alignment.
Calculates word and segment boundaries via acoustic energy valley silence detection
when MMS_FA CTC alignment is unavailable or fails.
"""

from __future__ import annotations
import math
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional, Any

from audiobook_factory.contracts import ScreenplaySegment
from audiobook_factory.logger import logger
from audiobook_factory.alignment_contracts import (
    AlignmentResult,
    WordAlignment,
    SpeechRegion,
    PauseInterval,
    AlignmentDiagnostic,
    AlignmentCalibrationConfig,
)
from audiobook_factory.alignment.text_utils import normalize_text_for_alignment
from audiobook_factory.alignment.audio_io import _read_pcm_samples, _get_wav_duration_ms


def align_with_energy_fallback(
    audio_path: Path,
    segments: List[ScreenplaySegment],
) -> List[Tuple[int, int]]:
    """Calculates segment boundaries via acoustic energy valley silence detection."""
    total_ms = _get_wav_duration_ms(audio_path)
    word_counts = [max(1, len(s.text.split())) for s in segments]
    total_words = sum(word_counts)

    samples, sample_rate = _read_pcm_samples(audio_path)
    boundaries: List[Tuple[int, int]] = []
    current_ms = 0

    for idx, count in enumerate(word_counts):
        if idx == len(word_counts) - 1:
            seg_end = total_ms
        else:
            ratio = count / float(total_words)
            est_dur = int(total_ms * ratio)
            est_boundary = current_ms + est_dur

            seg_end = est_boundary
            if len(samples) > 0 and sample_rate > 0:
                search_start = max(current_ms + 200, est_boundary - 600)
                search_end = min(total_ms - 200, est_boundary + 600)
                frame_ms = 50
                step_ms = 10
                frame_samples = (sample_rate * frame_ms) // 1000

                min_rms = float("inf")
                best_ms = est_boundary

                for t_ms in range(search_start, search_end - frame_ms, step_ms):
                    start_idx = (t_ms * sample_rate) // 1000
                    chunk = samples[start_idx:start_idx + frame_samples]
                    if len(chunk) > 0:
                        rms = math.sqrt(sum(float(s * s) for s in chunk) / float(len(chunk)))
                        if rms < min_rms:
                            min_rms = rms
                            best_ms = t_ms + (frame_ms // 2)

                seg_end = best_ms

        seg_end = max(current_ms + 200, min(total_ms, seg_end))
        boundaries.append((current_ms, seg_end))
        current_ms = seg_end

    logger.info(f"[*] WorkstationForcedAligner: Aligned {len(segments)} segments via Acoustic Energy Valley Silence Detection")
    return boundaries


def align_single_with_energy_fallback(
    audio_path: Path,
    text: str,
    segment_uid: str,
    total_audio_ms: int,
    config: AlignmentCalibrationConfig,
    direction: Optional[Any] = None,
) -> AlignmentResult:
    """Calculates word boundaries via acoustic energy valleys when CTC is unavailable."""
    raw_tokens, roman_tokens = normalize_text_for_alignment(text)
    n_words = len(roman_tokens)
    samples, sr = _read_pcm_samples(audio_path)

    avg_word_ms = total_audio_ms // max(1, n_words)
    words: List[WordAlignment] = []
    speech_regions: List[SpeechRegion] = []
    pauses: List[PauseInterval] = []

    curr_ms = 0
    for idx, (rt, nt) in enumerate(zip(raw_tokens, roman_tokens)):
        nxt_ms = total_audio_ms if idx == n_words - 1 else curr_ms + avg_word_ms
        words.append(
            WordAlignment(
                token=rt,
                normalized_token=nt,
                start_ms=curr_ms,
                end_ms=nxt_ms,
                confidence=0.45,
                pronunciation_status="fallback",
                source="energy_proportional",
            )
        )
        speech_regions.append(SpeechRegion(start_ms=curr_ms, end_ms=nxt_ms, confidence=0.45))
        curr_ms = nxt_ms

    # Detect silence pause intervals from acoustic samples
    if len(samples) > 0 and sr > 0:
        from audiobook_factory.alignment.pause_classifier import classify_pause
        frame_ms = 40
        frame_samples = (sr * frame_ms) // 1000
        silence_thresh = 500  # PCM int16 threshold
        
        in_silence = False
        silence_start = 0
        for f_idx in range(0, len(samples) - frame_samples, frame_samples):
            chunk = samples[f_idx:f_idx + frame_samples]
            rms = math.sqrt(sum(float(s * s) for s in chunk) / float(len(chunk)))
            cur_t = (f_idx * 1000) // sr
            if rms < silence_thresh:
                if not in_silence:
                    in_silence = True
                    silence_start = cur_t
            else:
                if in_silence:
                    in_silence = False
                    sil_dur = cur_t - silence_start
                    if sil_dur >= config.min_pause_ms:
                        p_int = classify_pause(
                            start_ms=silence_start,
                            end_ms=cur_t,
                            samples=samples,
                            sample_rate=sr,
                            config=config,
                            direction=direction,
                            is_initial=(silence_start == 0),
                            is_terminal=False,
                        )
                        pauses.append(p_int)
        if in_silence:
            cur_t = total_audio_ms
            sil_dur = cur_t - silence_start
            if sil_dur >= config.min_pause_ms:
                p_int = classify_pause(
                    start_ms=silence_start,
                    end_ms=cur_t,
                    samples=samples,
                    sample_rate=sr,
                    config=config,
                    direction=direction,
                    is_initial=(silence_start == 0),
                    is_terminal=True,
                )
                pauses.append(p_int)

    diags = [
        AlignmentDiagnostic(
            code="FALLBACK_ALIGNMENT",
            severity="WARNING",
            message="MMS_FA CTC alignment unavailable or failed; acoustic energy fallback used.",
            evidence={"method": "energy_proportional", "total_audio_ms": total_audio_ms},
        )
    ]

    for p in pauses:
        if p.classification == "dead_air":
            diags.append(
                AlignmentDiagnostic(
                    code="UNEXPECTED_LONG_SILENCE",
                    severity="WARNING",
                    message=f"Detected suspicious trailing dead air of {p.duration_ms}ms",
                    evidence={"start_ms": p.start_ms, "end_ms": p.end_ms, "duration_ms": p.duration_ms},
                )
            )

    conf = min(0.50, config.fallback_confidence_penalty)
    return AlignmentResult(
        segment_uid=segment_uid,
        words=words,
        pauses=pauses,
        speech_regions=speech_regions,
        start_ms=0,
        end_ms=total_audio_ms,
        confidence=conf,
        confidence_category="LOW",
        method="energy_fallback",
        diagnostics=diags,
        language="hi" if any('\u0900' <= c <= '\u097F' for c in text) else "en",
    )


def align_batch_detailed_with_energy_fallback(
    audio_path: Path,
    segments: List[ScreenplaySegment],
    config: AlignmentCalibrationConfig,
) -> List[AlignmentResult]:
    """Calculates segment boundaries and explicit fallback AlignmentResults when MMS_FA is unavailable."""
    boundaries = align_with_energy_fallback(audio_path, segments)
    results: List[AlignmentResult] = []
    conf = min(0.50, config.fallback_confidence_penalty)

    for seg, (s_ms, e_ms) in zip(segments, boundaries):
        uid = getattr(seg, "uid", f"seg_{getattr(seg, 'index', len(results) + 1)}")
        text = getattr(seg, "text", "")
        raw_tokens, rom_tokens = normalize_text_for_alignment(text)
        n_words = len(rom_tokens)
        dur = max(100, e_ms - s_ms)
        word_dur = dur // max(1, n_words)

        words: List[WordAlignment] = []
        curr = s_ms
        for idx, (rt, nt) in enumerate(zip(raw_tokens, rom_tokens)):
            nxt = e_ms if idx == n_words - 1 else curr + word_dur
            words.append(
                WordAlignment(
                    token=rt,
                    normalized_token=nt,
                    start_ms=curr,
                    end_ms=nxt,
                    confidence=conf,
                    pronunciation_status="fallback",
                    source="energy_proportional",
                )
            )
            curr = nxt

        speech_reg = [SpeechRegion(start_ms=s_ms, end_ms=e_ms, confidence=conf)]
        diags = [
            AlignmentDiagnostic(
                code="FALLBACK_ALIGNMENT",
                severity="WARNING",
                message="MMS_FA CTC alignment unavailable or failed for batch segment; acoustic energy fallback used.",
                evidence={"start_ms": s_ms, "end_ms": e_ms, "method": "energy_proportional"},
            )
        ]

        results.append(
            AlignmentResult(
                segment_uid=uid,
                words=words,
                pauses=[],
                speech_regions=speech_reg,
                start_ms=s_ms,
                end_ms=e_ms,
                confidence=conf,
                confidence_category="LOW",
                method="energy_fallback",
                diagnostics=diags,
                language="hi" if any('\u0900' <= c <= '\u097F' for c in text) else "en",
            )
        )

    return results
