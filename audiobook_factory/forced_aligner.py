#!/usr/bin/env python3
"""
Audiobook Factory - Pillar 4: Workstation Superpower Local Forced Aligner.
Uses NVIDIA GeForce RTX 4050 Laptop GPU with PyTorch & TorchAudio MMS_FA
(Meta Multilingual Speech CTC Forced Aligner) to extract sample-accurate
(±20ms) sentence and word boundaries from multi-speaker batched audio.
Includes automatic energy-valley / silence detection fallback.
"""

from __future__ import annotations
import os
import re
import wave
import subprocess
from pathlib import Path
from typing import List, Tuple, Optional

from audiobook_factory.contracts import ScreenplaySegment
from audiobook_factory.logger import logger

# Devanagari to Roman transliteration table for MMS_FA acoustic alignment
DEVA_TO_ROMAN_MAP = {
    'अ': 'a', 'आ': 'aa', 'इ': 'i', 'ई': 'ee', 'उ': 'u', 'ऊ': 'oo', 'ऋ': 'ri',
    'ए': 'e', 'ऐ': 'ai', 'ओ': 'o', 'औ': 'au', 'अं': 'am', 'अः': 'ah', 'ँ': 'n',
    'क': 'k', 'ख': 'kh', 'ग': 'g', 'घ': 'gh', 'ङ': 'ng',
    'च': 'ch', 'छ': 'chh', 'ज': 'j', 'झ': 'jh', 'ञ': 'ny',
    'ट': 't', 'ठ': 'th', 'ड': 'd', 'ढ': 'dh', 'ण': 'n',
    'त': 't', 'थ': 'th', 'द': 'd', 'ध': 'dh', 'न': 'n',
    'प': 'p', 'फ': 'ph', 'ब': 'b', 'भ': 'bh', 'म': 'm',
    'य': 'y', 'र': 'r', 'ल': 'l', 'व': 'v', 'श': 'sh', 'ष': 'sh', 'स': 's', 'ह': 'h',
    'क़': 'q', 'ख़': 'kh', 'ग़': 'gh', 'ज़': 'z', 'ड़': 'd', 'ढ़': 'dh', 'फ़': 'f',
    'ा': 'a', 'ि': 'i', 'ी': 'ee', 'ु': 'u', 'ू': 'oo', 'ृ': 'ri',
    'े': 'e', 'ै': 'ai', 'ो': 'o', 'ौ': 'au', 'ं': 'n', '्': '',
    '़': '', '।': ' ', '॥': ' ', '’': "'", '‘': "'"
}


def transliterate_devanagari_to_roman(text: str) -> str:
    """Converts Devanagari and Latin dialogue into clean romanized tokens for MMS_FA."""
    # Strip bracketed acting tags like [whispers] or [gasp]
    clean = re.sub(r"\[[^\]]+\]", " ", text)
    res = []
    for char in clean:
        res.append(DEVA_TO_ROMAN_MAP.get(char, char))
    roman = "".join(res)
    # Strip non-alphanumeric except spaces and apostrophes
    roman = re.sub(r"[^a-zA-Z'\s]", " ", roman).lower()
    return " ".join(roman.split())


def _load_wav_tensor_safely(audio_path: Path):
    """
    Loads 16-bit PCM WAV into a normalized PyTorch tensor directly via standard library wave,
    bypassing torchaudio C++ backend dependencies (soundfile/sox) that fail on Windows.
    """
    import torch
    with wave.open(str(audio_path), "rb") as wf:
        sample_rate = wf.getframerate()
        n_channels = wf.getnchannels()
        frames = wf.readframes(wf.getnframes())
        raw_tensor = torch.frombuffer(bytearray(frames), dtype=torch.int16).to(torch.float32) / 32768.0
        waveform = raw_tensor.view(-1, n_channels).t()
        if n_channels > 1:
            waveform = torch.mean(waveform, dim=0, keepdim=True)
        return waveform, sample_rate


class WorkstationForcedAligner:
    """
    Local CTC Forced Aligner executing on workstation GPU / CPU.
    Extracts millisecond-accurate start and end timestamps for dialogue segments.
    """

    def __init__(self, use_cuda: bool = True):
        self._bundle = None
        self._model = None
        self._tokenizer = None
        self._aligner = None
        self._device = None
        self.use_cuda = use_cuda
        self._init_done = False

    def _lazy_init(self) -> bool:
        """Initializes TorchAudio MMS_FA model on GPU."""
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

    def align_batch(
        self,
        audio_path: Path,
        segments: List[ScreenplaySegment],
    ) -> List[Tuple[int, int]]:
        """
        Aligns a merged multi-speaker WAV file against constituent screenplay segments.
        Returns a list of (start_ms, end_ms) for each segment.
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

    def _align_with_mms_fa(
        self,
        audio_path: Path,
        segments: List[ScreenplaySegment],
    ) -> Optional[List[Tuple[int, int]]]:
        """Performs true phoneme-level CTC alignment on GPU."""
        import torch
        import torchaudio

        # 1. Load and resample audio to 16kHz mono (MMS_FA requirement) using wave loader
        waveform, sample_rate = _load_wav_tensor_safely(audio_path)
        if sample_rate != self._bundle.sample_rate:
            resampler = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=self._bundle.sample_rate)
            waveform = resampler(waveform)

        waveform = waveform.to(self._device)

        # 2. Extract romanized words and track segment word boundaries
        all_words: List[str] = []
        seg_word_counts: List[int] = []

        for seg in segments:
            rom_text = transliterate_devanagari_to_roman(seg.text)
            words = [w for w in rom_text.split() if w]
            if not words:
                words = ["aa"]  # Dummy anchor if segment only had punctuation/cues
            all_words.extend(words)
            seg_word_counts.append(len(words))

        if not all_words:
            return None

        # 3. Tokenize words
        tokens = self._tokenizer(all_words)

        # 4. Generate frame emissions
        with torch.inference_mode():
            emission, _ = self._model(waveform)

        # 5. Compute word alignment spans
        spans = self._aligner(emission[0], tokens)
        if not spans or len(spans) != len(all_words):
            return None

        # Calculate time ratio per frame
        num_frames = emission.size(1)
        audio_duration_sec = waveform.size(1) / float(self._bundle.sample_rate)
        sec_per_frame = audio_duration_sec / float(num_frames)

        # 6. Map word spans back into segment (start_ms, end_ms)
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

            # Ensure valid non-zero duration
            if end_ms <= start_ms:
                end_ms = start_ms + 400

            boundaries.append((start_ms, end_ms))
            word_idx += count

        # Smooth contiguous boundaries so no dead air or overlap exists
        smoothed = []
        for idx, (s, e) in enumerate(boundaries):
            if idx == 0:
                s_smooth = 0
            else:
                s_smooth = smoothed[-1][1]

            if idx == len(boundaries) - 1:
                e_smooth = total_audio_ms
            else:
                # Midpoint between this end and next start
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
        """
        Calculates segment boundaries using true acoustic energy valley / silence detection
        around proportional word-duration boundary anchors.
        """
        import struct
        import math

        total_ms = self._get_wav_duration_ms(audio_path)
        word_counts = [max(1, len(s.text.split())) for s in segments]
        total_words = sum(word_counts)

        # Read audio samples for RMS energy valley scanning
        samples = []
        sample_rate = 24000
        try:
            with wave.open(str(audio_path), "rb") as wf:
                sample_rate = wf.getframerate()
                n_frames = wf.getnframes()
                raw = wf.readframes(n_frames)
                n_samples = len(raw) // 2
                if n_samples > 0:
                    samples = struct.unpack(f"<{n_samples}h", raw)
        except Exception as e:
            logger.warning(f"  [!] Could not parse audio samples for energy fallback: {e}")

        boundaries: List[Tuple[int, int]] = []
        current_ms = 0

        for idx, count in enumerate(word_counts):
            if idx == len(word_counts) - 1:
                seg_end = total_ms
            else:
                ratio = count / float(total_words)
                est_dur = int(total_ms * ratio)
                est_boundary = current_ms + est_dur

                # Find silence valley in window [est_boundary - 600ms, est_boundary + 600ms]
                seg_end = est_boundary
                if samples and sample_rate > 0:
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
                        if chunk:
                            rms = math.sqrt(sum(s * s for s in chunk) / float(len(chunk)))
                            if rms < min_rms:
                                min_rms = rms
                                best_ms = t_ms + (frame_ms // 2)

                    seg_end = best_ms

            seg_end = max(current_ms + 200, min(total_ms, seg_end))
            boundaries.append((current_ms, seg_end))
            current_ms = seg_end

        logger.info(f"[*] WorkstationForcedAligner: Aligned {len(segments)} segments via Acoustic Energy Valley Silence Detection")
        return boundaries

    @staticmethod
    def _get_wav_duration_ms(audio_path: Path) -> int:
        """Reads exact duration of a WAV file in milliseconds."""
        try:
            with wave.open(str(audio_path), "rb") as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                return int((frames / float(rate)) * 1000)
        except Exception:
            # Fallback to file size estimate for 24kHz 16-bit mono
            size = audio_path.stat().st_size
            return max(500, int((size / 48000.0) * 1000))
