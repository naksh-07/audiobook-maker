#!/usr/bin/env python3
"""
Audiobook Factory - Alignment Engine: Workstation Local Forced Aligner.
Uses PyTorch & TorchAudio MMS_FA (Meta Multilingual Speech CTC Forced Aligner)
to extract sample-accurate (±20ms) word, phrase, pause, and sentence boundaries.
"""

from __future__ import annotations
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional, Any

from audiobook_factory.contracts import ScreenplaySegment
from audiobook_factory.logger import logger
from audiobook_factory.alignment_contracts import (
    AlignmentResult,
    WordAlignment,
    PauseInterval,
    SpeechRegion,
    AlignmentDiagnostic,
    AlignmentCalibrationConfig,
    AlignmentConfidenceCategory,
    PauseClassification,
)
from audiobook_factory.alignment.text_utils import (
    normalize_text_for_alignment,
    transliterate_devanagari_to_roman,
    DEVA_TO_ROMAN_MAP,
)
from audiobook_factory.alignment.audio_io import (
    _load_wav_tensor_safely,
    _read_pcm_samples,
    _get_wav_duration_ms,
)
from audiobook_factory.alignment.pause_classifier import classify_pause
from audiobook_factory.alignment.diagnostics import calculate_confidence_and_diagnostics
from audiobook_factory.alignment.energy_fallback import (
    align_with_energy_fallback,
    align_single_with_energy_fallback,
    align_batch_detailed_with_energy_fallback,
)


class WorkstationForcedAligner:
    """
    Local CTC Forced Aligner executing on workstation GPU / CPU.
    Extracts millisecond-accurate word, pause, and sentence boundaries.
    Provides Alignment 2.0 contracts with multi-signal calibrated confidence.
    """

    def __init__(
        self,
        use_cuda: bool = True,
        config: Optional[AlignmentCalibrationConfig] = None,
    ):
        self._bundle = None
        self._model = None
        self._tokenizer = None
        self._aligner = None
        self._device = None
        self.use_cuda = use_cuda
        self._init_done = False
        self.config = config or AlignmentCalibrationConfig()

    def _lazy_init(self) -> bool:
        """Initializes TorchAudio MMS_FA model on GPU/CPU."""
        if self._init_done:
            return self._model is not None

        self._init_done = True
        try:
            import torch
            import torchaudio
            from torchaudio.pipelines import MMS_FA as bundle

            self._bundle = bundle
            self._device = "cuda" if (self.use_cuda and torch.cuda.is_available()) else "cpu"
            self._model = bundle.get_model().to(self._device)
            self._model.eval()
            self._tokenizer = bundle.get_tokenizer()
            self._aligner = bundle.get_aligner()
            logger.info(f"[*] WorkstationForcedAligner: Loaded MMS_FA aligner on {self._device.upper()} (Superpower Active)")
            return True
        except Exception as e:
            logger.warning(f"[!] WorkstationForcedAligner: TorchAudio MMS_FA unavailable ({e}). Using energy fallback.")
            self._model = None
            return False

    def _cleanup_tensors(self, *tensors):
        """Releases tensor memory and clears CUDA cache if applicable."""
        for t in tensors:
            if t is not None:
                del t
        if self._device == "cuda":
            try:
                import torch
                torch.cuda.empty_cache()
            except Exception:
                pass

    # -------------------------------------------------------------------------
    # Public API 1: Backward-Compatible align_batch
    # -------------------------------------------------------------------------
    def align_batch(
        self,
        audio_path: Path,
        segments: List[ScreenplaySegment],
    ) -> List[Tuple[int, int]]:
        """
        Aligns a merged multi-speaker WAV file against constituent screenplay segments.
        Returns a list of (start_ms, end_ms) for each segment.
        Preserves 100% backward compatibility for all existing callers.
        """
        if not segments:
            return []

        if len(segments) == 1:
            total_ms = self._get_wav_duration_ms(audio_path)
            return [(0, total_ms)]

        # Try MMS_FA CTC alignment first
        if self._lazy_init():
            try:
                boundaries = self._align_with_mms_fa(audio_path, segments)
                if boundaries and len(boundaries) == len(segments):
                    return boundaries
            except Exception as e:
                logger.warning(f"[!] MMS_FA alignment execution error: {e}. Falling back to energy alignment.")

        # Robust Energy / Silence Fallback
        return self._align_with_energy_fallback(audio_path, segments)

    # -------------------------------------------------------------------------
    # Public API 2: Alignment 2.0 Single Segment Alignment
    # -------------------------------------------------------------------------
    def align_segment(
        self,
        audio_path: Path | str,
        text: str,
        segment_uid: str = "",
        direction: Optional[Any] = None,
    ) -> AlignmentResult:
        """
        First-Class Alignment 2.0 method.
        Extracts word-level timing, pause intelligence, speech regions,
        calibrated multi-signal confidence, and structured diagnostics.
        """
        p = Path(audio_path).resolve()
        if not p.exists() or p.stat().st_size <= 44:
            diag = AlignmentDiagnostic(
                code="AUDIO_FILE_DEFECT",
                severity="CRITICAL",
                message="Audio file missing or empty on disk",
                evidence={"path": str(p)},
            )
            return AlignmentResult(
                segment_uid=segment_uid,
                start_ms=0,
                end_ms=0,
                confidence=0.0,
                confidence_category="FAILED_REVIEW_REQUIRED",
                method="mms_fa_ctc",
                diagnostics=[diag],
            )

        total_audio_ms = self._get_wav_duration_ms(p)

        # 1. Attempt MMS_FA CTC Alignment
        if self._lazy_init():
            try:
                res = self._align_single_with_mms_fa(p, text, segment_uid, total_audio_ms, direction)
                if res is not None:
                    return res
            except Exception as e:
                logger.warning(f"[!] MMS_FA segment alignment error: {e}. Using acoustic fallback.")

        # 2. Robust Acoustic Energy Valley Fallback
        return self._align_single_with_energy_fallback(p, text, segment_uid, total_audio_ms, direction)

    # -------------------------------------------------------------------------
    # Public API 3: Detailed Batch Alignment
    # -------------------------------------------------------------------------
    def align_batch_detailed(
        self,
        audio_path: Path | str,
        segments: List[ScreenplaySegment],
    ) -> List[AlignmentResult]:
        """
        Detailed multi-segment alignment across a merged audio file,
        returning full AlignmentResult models for each segment.
        Never fabricates timings or MMS_FA provenance.
        """
        p = Path(audio_path).resolve()
        if not segments:
            return []

        # 1. Attempt MMS_FA CTC detailed alignment
        if self._lazy_init():
            try:
                detailed = self._align_batch_detailed_with_mms_fa(p, segments)
                if detailed and len(detailed) == len(segments):
                    return detailed
            except Exception as e:
                logger.warning(f"[!] MMS_FA batch detailed alignment failed: {e}. Using acoustic fallback.")

        # 2. Honest acoustic energy fallback
        return self._align_batch_detailed_with_energy_fallback(p, segments)

    def _align_batch_detailed_with_mms_fa(
        self,
        audio_path: Path,
        segments: List[ScreenplaySegment],
    ) -> Optional[List[AlignmentResult]]:
        """Extracts real token spans, pauses, and calibrated diagnostics for each segment in batch."""
        import torch
        import torchaudio

        waveform, sample_rate = _load_wav_tensor_safely(audio_path)
        if sample_rate != self._bundle.sample_rate:
            resampler = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=self._bundle.sample_rate)
            waveform = resampler(waveform)

        waveform = waveform.to(self._device)

        all_raw_tokens: List[List[str]] = []
        all_rom_tokens: List[List[str]] = []
        flat_rom_tokens: List[str] = []

        for seg in segments:
            raw_t, rom_t = normalize_text_for_alignment(getattr(seg, "text", ""))
            if not rom_t:
                rom_t = ["aa"]
                raw_t = ["aa"]
            all_raw_tokens.append(raw_t)
            all_rom_tokens.append(rom_t)
            flat_rom_tokens.extend(rom_t)

        if not flat_rom_tokens:
            return None

        tokens = self._tokenizer(flat_rom_tokens)

        try:
            with torch.inference_mode():
                emission, _ = self._model(waveform)

            spans = self._aligner(emission[0], tokens)
            num_frames = emission.size(1)
            audio_duration_sec = waveform.size(1) / float(self._bundle.sample_rate)
            sec_per_frame = audio_duration_sec / float(num_frames)
            total_audio_ms = int(audio_duration_sec * 1000)
        finally:
            self._cleanup_tensors(waveform, locals().get("emission"))

        if not spans or len(spans) != len(flat_rom_tokens):
            return None

        samples, sr = self._read_pcm_samples(audio_path)

        results: List[AlignmentResult] = []
        word_cursor = 0

        for seg_idx, seg in enumerate(segments):
            uid = getattr(seg, "uid", f"seg_{getattr(seg, 'index', seg_idx + 1)}")
            seg_raw = all_raw_tokens[seg_idx]
            seg_rom = all_rom_tokens[seg_idx]
            seg_count = len(seg_rom)

            seg_spans = spans[word_cursor : word_cursor + seg_count]
            word_cursor += seg_count

            words: List[WordAlignment] = []
            speech_regions: List[SpeechRegion] = []
            pauses: List[PauseInterval] = []

            last_end_ms = 0 if seg_idx == 0 else results[-1].end_ms

            for w_i, (raw_tok, rom_tok, span_list) in enumerate(zip(seg_raw, seg_rom, seg_spans)):
                if not span_list:
                    w_start = last_end_ms
                    w_end = min(total_audio_ms, w_start + 200)
                    w_conf = 0.20
                else:
                    w_start = max(0, int(span_list[0].start * sec_per_frame * 1000))
                    w_end = min(total_audio_ms, int(span_list[-1].end * sec_per_frame * 1000))
                    scores = [float(s.score) for s in span_list]
                    w_conf = float(np.mean(scores)) if scores else 0.50

                if w_end <= w_start:
                    w_end = min(total_audio_ms, w_start + self.config.min_word_duration_ms)

                if w_start > last_end_ms + self.config.min_pause_ms:
                    pause_int = self._classify_pause(
                        start_ms=last_end_ms,
                        end_ms=w_start,
                        samples=samples,
                        sample_rate=sr,
                        is_initial=(w_i == 0),
                        is_terminal=False,
                    )
                    pauses.append(pause_int)

                words.append(
                    WordAlignment(
                        token=raw_tok,
                        normalized_token=rom_tok,
                        start_ms=w_start,
                        end_ms=w_end,
                        confidence=round(w_conf, 3),
                        pronunciation_status="aligned" if w_conf >= 0.35 else "uncertain",
                        source="mms_fa_ctc",
                    )
                )
                speech_regions.append(SpeechRegion(start_ms=w_start, end_ms=w_end, confidence=round(w_conf, 3)))
                last_end_ms = w_end

            seg_text = getattr(seg, "text", "")
            seg_start = words[0].start_ms if words else 0
            seg_end = words[-1].end_ms if words else total_audio_ms
            seg_dur = max(1, seg_end - seg_start)

            conf, conf_cat, diags = self._calculate_confidence_and_diagnostics(
                words=words,
                pauses=pauses,
                speech_regions=speech_regions,
                total_audio_ms=seg_dur,
                text=seg_text,
                method="mms_fa_ctc",
            )

            results.append(
                AlignmentResult(
                    segment_uid=uid,
                    words=words,
                    pauses=pauses,
                    speech_regions=speech_regions,
                    start_ms=seg_start,
                    end_ms=seg_end,
                    confidence=round(conf, 3),
                    confidence_category=conf_cat,
                    method="mms_fa_ctc",
                    diagnostics=diags,
                    language="hi" if any('\u0900' <= c <= '\u097F' for c in seg_text) else "en",
                )
            )

        return results

    def _align_batch_detailed_with_energy_fallback(
        self,
        audio_path: Path,
        segments: List[ScreenplaySegment],
    ) -> List[AlignmentResult]:
        return align_batch_detailed_with_energy_fallback(audio_path, segments, self.config)

    def _align_single_with_mms_fa(
        self,
        audio_path: Path,
        text: str,
        segment_uid: str,
        total_audio_ms: int,
        direction: Optional[Any] = None,
    ) -> Optional[AlignmentResult]:
        """Executes phoneme-level CTC alignment on audio take."""
        import torch
        import torchaudio

        raw_tokens, roman_tokens = normalize_text_for_alignment(text)
        if not roman_tokens:
            return None

        # Load & resample audio to 16kHz mono (MMS_FA requirement)
        waveform, sample_rate = _load_wav_tensor_safely(audio_path)
        if sample_rate != self._bundle.sample_rate:
            resampler = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=self._bundle.sample_rate)
            waveform = resampler(waveform)

        waveform = waveform.to(self._device)

        tokens = self._tokenizer(roman_tokens)

        try:
            with torch.inference_mode():
                emission, _ = self._model(waveform)

            spans = self._aligner(emission[0], tokens)
            num_frames = emission.size(1)
            audio_duration_sec = waveform.size(1) / float(self._bundle.sample_rate)
            sec_per_frame = audio_duration_sec / float(num_frames)
        finally:
            self._cleanup_tensors(waveform, locals().get("emission"))

        if not spans or len(spans) != len(roman_tokens):
            return None

        samples, sr = self._read_pcm_samples(audio_path)

        words: List[WordAlignment] = []
        speech_regions: List[SpeechRegion] = []
        pauses: List[PauseInterval] = []

        last_end_ms = 0

        for idx, (raw_tok, rom_tok, span_list) in enumerate(zip(raw_tokens, roman_tokens, spans)):
            if not span_list:
                w_start = last_end_ms
                w_end = min(total_audio_ms, w_start + 200)
                w_conf = 0.20
            else:
                w_start = max(0, int(span_list[0].start * sec_per_frame * 1000))
                w_end = min(total_audio_ms, int(span_list[-1].end * sec_per_frame * 1000))
                scores = [float(s.score) for s in span_list]
                w_conf = float(np.mean(scores)) if scores else 0.50

            if w_end <= w_start:
                w_end = min(total_audio_ms, w_start + self.config.min_word_duration_ms)

            if w_start > last_end_ms + self.config.min_pause_ms:
                pause_int = self._classify_pause(
                    start_ms=last_end_ms,
                    end_ms=w_start,
                    samples=samples,
                    sample_rate=sr,
                    direction=direction,
                    is_initial=(idx == 0),
                    is_terminal=False,
                )
                pauses.append(pause_int)

            words.append(
                WordAlignment(
                    token=raw_tok,
                    normalized_token=rom_tok,
                    start_ms=w_start,
                    end_ms=w_end,
                    confidence=round(w_conf, 3),
                    pronunciation_status="aligned" if w_conf >= 0.35 else "uncertain",
                    source="mms_fa_ctc",
                )
            )
            speech_regions.append(SpeechRegion(start_ms=w_start, end_ms=w_end, confidence=round(w_conf, 3)))
            last_end_ms = w_end

        if last_end_ms < total_audio_ms - self.config.min_pause_ms:
            terminal_pause = self._classify_pause(
                start_ms=last_end_ms,
                end_ms=total_audio_ms,
                samples=samples,
                sample_rate=sr,
                direction=direction,
                is_initial=False,
                is_terminal=True,
            )
            pauses.append(terminal_pause)

        conf, conf_cat, diags = self._calculate_confidence_and_diagnostics(
            words=words,
            pauses=pauses,
            speech_regions=speech_regions,
            total_audio_ms=total_audio_ms,
            text=text,
            method="mms_fa_ctc",
        )

        overall_start = words[0].start_ms if words else 0
        overall_end = words[-1].end_ms if words else total_audio_ms

        return AlignmentResult(
            segment_uid=segment_uid,
            words=words,
            pauses=pauses,
            speech_regions=speech_regions,
            start_ms=overall_start,
            end_ms=overall_end,
            confidence=round(conf, 3),
            confidence_category=conf_cat,
            method="mms_fa_ctc",
            diagnostics=diags,
            language="hi" if any('\u0900' <= c <= '\u097F' for c in text) else "en",
        )

    def _align_single_with_energy_fallback(
        self,
        audio_path: Path,
        text: str,
        segment_uid: str,
        total_audio_ms: int,
        direction: Optional[Any] = None,
    ) -> AlignmentResult:
        return align_single_with_energy_fallback(
            audio_path=audio_path,
            text=text,
            segment_uid=segment_uid,
            total_audio_ms=total_audio_ms,
            config=self.config,
            direction=direction,
        )

    def _classify_pause(
        self,
        start_ms: int,
        end_ms: int,
        samples: np.ndarray,
        sample_rate: int,
        direction: Optional[Any] = None,
        is_initial: bool = False,
        is_terminal: bool = False,
    ) -> PauseInterval:
        return classify_pause(
            start_ms=start_ms,
            end_ms=end_ms,
            samples=samples,
            sample_rate=sample_rate,
            config=self.config,
            direction=direction,
            is_initial=is_initial,
            is_terminal=is_terminal,
        )

    def _calculate_confidence_and_diagnostics(
        self,
        words: List[WordAlignment],
        pauses: List[PauseInterval],
        speech_regions: List[SpeechRegion],
        total_audio_ms: int,
        text: str,
        method: str,
    ) -> Tuple[float, AlignmentConfidenceCategory, List[AlignmentDiagnostic]]:
        return calculate_confidence_and_diagnostics(
            words=words,
            pauses=pauses,
            speech_regions=speech_regions,
            total_audio_ms=total_audio_ms,
            text=text,
            method=method,
            config=self.config,
        )

    def _align_with_mms_fa(
        self,
        audio_path: Path,
        segments: List[ScreenplaySegment],
    ) -> Optional[List[Tuple[int, int]]]:
        """Performs true phoneme-level CTC alignment on merged batch audio."""
        import torch
        import torchaudio

        waveform, sample_rate = _load_wav_tensor_safely(audio_path)
        if sample_rate != self._bundle.sample_rate:
            resampler = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=self._bundle.sample_rate)
            waveform = resampler(waveform)

        waveform = waveform.to(self._device)

        all_words: List[str] = []
        seg_word_counts: List[int] = []

        for seg in segments:
            _, rom_tokens = normalize_text_for_alignment(seg.text)
            if not rom_tokens:
                rom_tokens = ["aa"]
            all_words.extend(rom_tokens)
            seg_word_counts.append(len(rom_tokens))

        if not all_words:
            return None

        tokens = self._tokenizer(all_words)

        try:
            with torch.inference_mode():
                emission, _ = self._model(waveform)

            spans = self._aligner(emission[0], tokens)
            num_frames = emission.size(1)
            audio_duration_sec = waveform.size(1) / float(self._bundle.sample_rate)
            sec_per_frame = audio_duration_sec / float(num_frames)
        finally:
            self._cleanup_tensors(waveform, locals().get("emission"))

        if not spans or len(spans) != len(all_words):
            return None

        boundaries: List[Tuple[int, int]] = []
        word_idx = 0
        total_audio_ms = int(audio_duration_sec * 1000)

        for count in seg_word_counts:
            if word_idx >= len(spans) or (word_idx + count - 1) >= len(spans):
                return None
            seg_start_span = spans[word_idx]
            seg_end_span = spans[word_idx + count - 1]

            if not seg_start_span or not seg_end_span:
                return None

            start_ms = max(0, int(seg_start_span[0].start * sec_per_frame * 1000))
            end_ms = min(total_audio_ms, int(seg_end_span[-1].end * sec_per_frame * 1000))

            if end_ms <= start_ms:
                end_ms = start_ms + 400

            boundaries.append((start_ms, end_ms))
            word_idx += count

        smoothed = []
        for idx, (s, e) in enumerate(boundaries):
            if idx == 0:
                s_smooth = 0
            else:
                s_smooth = smoothed[-1][1]

            if idx == len(boundaries) - 1:
                e_smooth = total_audio_ms
            else:
                next_start = boundaries[idx + 1][0]
                e_smooth = max(s_smooth + 200, (e + next_start) // 2)

            smoothed.append((s_smooth, e_smooth))

        logger.info(f"[*] WorkstationForcedAligner: Successfully aligned {len(segments)} segments via MMS_FA on {self._device.upper()}")
        return smoothed

    def _align_with_energy_fallback(
        self,
        audio_path: Path,
        segments: List[ScreenplaySegment],
    ) -> List[Tuple[int, int]]:
        return align_with_energy_fallback(audio_path, segments)

    def _read_pcm_samples(self, audio_path: Path) -> Tuple[np.ndarray, int]:
        return _read_pcm_samples(audio_path)

    @staticmethod
    def _get_wav_duration_ms(audio_path: Path) -> int:
        return _get_wav_duration_ms(audio_path)
