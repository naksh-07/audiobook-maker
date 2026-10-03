"""
Sonic Model Manager & Audio Preprocessing Pipeline (Phase 2 Foundation).
Provides lazy model loading, CUDA/CPU device management, VRAM hygiene,
and micro-SFX energy-conserving windowing.
"""

from __future__ import annotations

import gc
import logging
import os
import threading
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# Suppress Hugging Face symlinks warning on Windows
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

logger = logging.getLogger("audiobook_factory.sonic_model_manager")


class AudioPreprocessor:
    """
    Standardized audio preprocessor fulfilling Phase 2 requirements for:
    1. Short audio / Micro-SFX (50ms - 200ms) with active-region centering & energy-conserving padding.
    2. Temporal slicing / sliding windows for long ambience and multi-event soundscapes.
    """

    @staticmethod
    def preprocess_short_audio(
        waveform: np.ndarray,
        sample_rate: int,
        target_duration_sec: float = 1.0,
        min_duration_sec: float = 0.5,
    ) -> Tuple[np.ndarray, str]:
        """
        Processes short audio / micro-SFX using active-region centering and smooth energy-conserving padding.
        Avoids artificial periodic repeats and unshaped zero-padding dilution.

        Returns:
            Tuple of (preprocessed_waveform, preprocessing_strategy_name)
        """
        # Ensure 1D float32
        if waveform.ndim > 1:
            waveform = np.mean(waveform, axis=0 if waveform.shape[0] < waveform.shape[1] else 1)
        waveform = waveform.astype(np.float32)

        cur_duration_sec = len(waveform) / sample_rate
        if cur_duration_sec >= target_duration_sec:
            return waveform, "direct_passthrough"

        target_len = int(target_duration_sec * sample_rate)

        # 1. Detect active energy region
        abs_wf = np.abs(waveform)
        threshold = np.max(abs_wf) * 0.1 if np.max(abs_wf) > 1e-4 else 1e-5
        active_indices = np.where(abs_wf >= threshold)[0]

        if len(active_indices) > 0:
            center_idx = int((active_indices[0] + active_indices[-1]) // 2)
        else:
            center_idx = len(waveform) // 2

        # 2. Center within target window
        padded = np.zeros(target_len, dtype=np.float32)
        target_center = target_len // 2
        start_dst = max(0, target_center - center_idx)
        end_dst = min(target_len, start_dst + len(waveform))
        src_start = max(0, center_idx - target_center)
        src_len = end_dst - start_dst
        src_end = min(len(waveform), src_start + src_len)

        actual_len = min(src_end - src_start, end_dst - start_dst)
        if actual_len > 0:
            padded[start_dst : start_dst + actual_len] = waveform[src_start : src_start + actual_len]

        # 3. Energy-conserving smooth boundaries (tapered micro-fade at window edges to prevent clicks)
        fade_len = min(int(0.01 * sample_rate), len(padded) // 10)
        if fade_len > 1:
            fade_in = np.linspace(0.0, 1.0, fade_len, dtype=np.float32)
            fade_out = np.linspace(1.0, 0.0, fade_len, dtype=np.float32)
            padded[:fade_len] *= fade_in
            padded[-fade_len:] *= fade_out

        return padded, "centered_energy_conserving_pad"

    @staticmethod
    def slice_sliding_windows(
        waveform: np.ndarray,
        sample_rate: int,
        window_sec: float = 10.0,
        hop_sec: float = 5.0,
    ) -> List[Tuple[float, float, np.ndarray]]:
        """
        Slices long audio into overlapping temporal windows for temporal sound event detection.

        Returns:
            List of (start_sec, end_sec, window_waveform)
        """
        if waveform.ndim > 1:
            waveform = np.mean(waveform, axis=0 if waveform.shape[0] < waveform.shape[1] else 1)
        waveform = waveform.astype(np.float32)

        total_samples = len(waveform)
        total_duration = total_samples / sample_rate

        if total_duration <= window_sec:
            return [(0.0, round(total_duration, 3), waveform)]

        window_samples = int(window_sec * sample_rate)
        hop_samples = int(hop_sec * sample_rate)

        windows: List[Tuple[float, float, np.ndarray]] = []
        cur_start = 0

        while cur_start < total_samples:
            cur_end = min(cur_start + window_samples, total_samples)
            chunk = waveform[cur_start:cur_end]

            start_sec = round(cur_start / sample_rate, 3)
            end_sec = round(cur_end / sample_rate, 3)
            windows.append((start_sec, end_sec, chunk))

            if cur_end >= total_samples:
                break
            cur_start += hop_samples

        return windows


class SonicModelManager:
    """
    Central model manager for Phase 2 AI Enrichment models.
    Enforces singleton pattern, lazy loading, CUDA/CPU device fallback,
    and automatic memory hygiene for consumer laptop GPUs.
    """

    _instance: Optional[SonicModelManager] = None
    _lock = threading.Lock()

    def __new__(cls) -> SonicModelManager:
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return

        self._initialized = True
        self._device: Optional[str] = None
        self._clap_model: Any = None
        self._clap_processor: Any = None
        self._ast_model: Any = None
        self._ast_extractor: Any = None
        self._model_lock = threading.Lock()

        # Determine optimal device
        self._detect_device()

    def _detect_device(self) -> None:
        """Detect best hardware accelerator (CUDA with fallback to CPU)."""
        force_cpu = (
            os.environ.get("SONIC_FORCE_CPU", "").lower() in ("1", "true", "yes")
            or os.environ.get("UNIT_TEST_MODE", "").lower() in ("1", "true", "yes")
        )
        if force_cpu:
            self._device = "cpu"
            logger.info("SonicModelManager: Using CPU (test mode / SONIC_FORCE_CPU)")
            return
        try:
            import torch
            if torch.cuda.is_available():
                self._device = "cuda"
                logger.info(f"SonicModelManager: CUDA detected ({torch.cuda.get_device_name(0)})")
            else:
                self._device = "cpu"
                logger.info("SonicModelManager: CUDA unavailable, using CPU")
        except Exception as e:
            self._device = "cpu"
            logger.warning(f"SonicModelManager: Error probing PyTorch device ({e}), fallback to CPU")

    @property
    def device(self) -> str:
        if self._device is None:
            self._detect_device()
        return self._device or "cpu"

    def get_clap(self, model_id: str = "laion/clap-htsat-unfused") -> Tuple[Any, Any]:
        """Lazy load and return (CLAP processor, CLAP model)."""
        with self._model_lock:
            if self._clap_model is None or self._clap_processor is None:
                import torch
                from transformers import ClapModel, ClapProcessor

                logger.info(f"Loading CLAP model from '{model_id}' on {self.device}...")
                self._clap_processor = ClapProcessor.from_pretrained(model_id)
                model = ClapModel.from_pretrained(model_id)

                try:
                    model = model.to(self.device)
                except Exception as e:
                    logger.warning(f"Failed to place CLAP on {self.device} ({e}), falling back to CPU")
                    self._device = "cpu"
                    model = model.to("cpu")

                model.eval()
                self._clap_model = model

            return self._clap_processor, self._clap_model

    def get_ast_classifier(
        self, model_id: str = "MIT/ast-finetuned-audioset-10-10-0.4593"
    ) -> Tuple[Any, Any]:
        """Lazy load and return (AST feature extractor, AST model)."""
        with self._model_lock:
            if self._ast_model is None or self._ast_extractor is None:
                import torch
                from transformers import AutoFeatureExtractor, AutoModelForAudioClassification

                logger.info(f"Loading AST classifier from '{model_id}' on {self.device}...")
                self._ast_extractor = AutoFeatureExtractor.from_pretrained(model_id)
                model = AutoModelForAudioClassification.from_pretrained(model_id)

                try:
                    model = model.to(self.device)
                except Exception as e:
                    logger.warning(f"Failed to place AST on {self.device} ({e}), falling back to CPU")
                    self._device = "cpu"
                    model = model.to("cpu")

                model.eval()
                self._ast_model = model

            return self._ast_extractor, self._ast_model

    def release_models(self) -> None:
        """Release loaded models and garbage collect memory."""
        with self._model_lock:
            self._clap_model = None
            self._clap_processor = None
            self._ast_model = None
            self._ast_extractor = None

            gc.collect()
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass
            logger.info("SonicModelManager: Released all models and cleared VRAM")

    def clear_vram(self) -> None:
        """Clear PyTorch CUDA cache and invoke garbage collection."""
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

    @contextmanager
    def manage_gpu_memory(self):
        """Context manager to ensure VRAM cache is freed after processing batches."""
        try:
            yield
        finally:
            self.clear_vram()
