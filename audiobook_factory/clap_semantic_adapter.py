"""
CLAP Semantic Adapter (Phase 2).
Provides open-vocabulary semantic representations via LAION-CLAP (HTS-AT 512-d).
Supports dual AUDIO and TEXT embedding spaces, micro-SFX centering,
and batch text queries for compound query planning.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import scipy.signal

from audiobook_factory.contracts import ProvenanceRecord, SemanticEmbeddingFacts
from audiobook_factory.sonic_model_manager import AudioPreprocessor, SonicModelManager

logger = logging.getLogger("audiobook_factory.clap_semantic_adapter")


class CLAPSemanticAdapter:
    """
    Adapter for LAION-CLAP semantic embeddings (audio and text).
    Produces versioned, L2-normalized 512-dimensional vectors.
    """

    def __init__(
        self,
        model_id: str = "laion/clap-htsat-unfused",
        model_version: str = "2023_v1",
        preprocessing_version: str = "v1_centered_energy_conserving_pad",
    ) -> None:
        self.model_id = model_id
        self.model_version = model_version
        self.preprocessing_version = preprocessing_version
        self.embedding_dim = 512
        self._model_manager = SonicModelManager()

    def _resample_if_needed(self, waveform: np.ndarray, orig_sr: int, target_sr: int = 48000) -> np.ndarray:
        """Resample waveform to 48,000 Hz required by LAION-CLAP using ultra-fast torchaudio."""
        if orig_sr == target_sr:
            return waveform
        try:
            import torch
            import torchaudio.transforms as T
            wf_t = torch.from_numpy(waveform).unsqueeze(0)
            resampler = T.Resample(orig_sr, target_sr)
            return resampler(wf_t).squeeze(0).numpy().astype(np.float32)
        except Exception:
            num_target_samples = int(round(len(waveform) * target_sr / orig_sr))
            return scipy.signal.resample(waveform, num_target_samples).astype(np.float32)

    def embed_audio(
        self,
        waveform: np.ndarray,
        sample_rate: int,
        duration_sec: float,
    ) -> Tuple[np.ndarray, SemanticEmbeddingFacts]:
        """
        Generates 512-dimensional L2-normalized semantic embedding for an audio waveform.
        Handles micro-SFX using active-region centering and energy-conserving padding.
        """
        import torch

        # Ensure 1D mono waveform (convert stereo/multi-channel)
        if waveform.ndim > 1:
            waveform = np.mean(waveform, axis=0 if waveform.shape[0] < waveform.shape[1] else 1)
        waveform = waveform.astype(np.float32)

        # Short audio / micro-SFX handling (Section 8)
        prep_strategy = "direct"
        if duration_sec < 1.0 or len(waveform) < sample_rate:
            waveform, prep_strategy = AudioPreprocessor.preprocess_short_audio(
                waveform, sample_rate, target_duration_sec=1.0
            )

        processor, model = self._model_manager.get_clap(self.model_id)
        device = self._model_manager.device

        # Multi-window energy-weighted pooling for long ambience (> 15.0s)
        if duration_sec > 15.0:
            prep_strategy = "multi_window_energy_weighted"
            window_len = int(7.0 * sample_rate)
            total_samples = len(waveform)
            # Sample up to 3 non-overlapping windows: early, mid, late
            offsets = [
                min(int(1.0 * sample_rate), max(0, total_samples - window_len)),
                max(0, (total_samples - window_len) // 2),
                max(0, total_samples - window_len),
            ]
            # Deduplicate offsets
            unique_offsets = sorted(list(set(offsets)))
            window_vectors = []
            weights = []

            for off in unique_offsets:
                chunk = waveform[off : off + window_len]
                if len(chunk) < window_len:
                    chunk, _ = AudioPreprocessor.preprocess_short_audio(chunk, sample_rate, target_duration_sec=7.0)
                chunk_48k = self._resample_if_needed(chunk, sample_rate, target_sr=48000)
                rms = float(np.sqrt(np.mean(chunk ** 2) + 1e-12))
                inputs = processor(audio=chunk_48k, sampling_rate=48000, return_tensors="pt")
                inputs = {k: v.to(device) for k, v in inputs.items()}

                with torch.inference_mode():
                    with self._model_manager.manage_gpu_memory():
                        out = model.get_audio_features(**inputs)
                        if hasattr(out, "pooler_output"):
                            embed = out.pooler_output
                        elif hasattr(out, "last_hidden_state"):
                            embed = out.last_hidden_state[:, 0, :]
                        else:
                            embed = out
                        embed = embed / embed.norm(dim=-1, keepdim=True)
                        vec = embed.squeeze(0).cpu().numpy().astype(np.float32)
                        window_vectors.append(vec)
                        weights.append(max(rms, 1e-4))

            # Energy-weighted average and L2 normalize
            total_weight = sum(weights)
            weighted_vec = sum(v * (w / total_weight) for v, w in zip(window_vectors, weights))
            norm = np.linalg.norm(weighted_vec)
            vector = (weighted_vec / norm).astype(np.float32) if norm > 1e-12 else window_vectors[0]
        else:
            wav_48k = self._resample_if_needed(waveform, sample_rate, target_sr=48000)
            inputs = processor(audio=wav_48k, sampling_rate=48000, return_tensors="pt")
            inputs = {k: v.to(device) for k, v in inputs.items()}

            with torch.inference_mode():
                with self._model_manager.manage_gpu_memory():
                    out = model.get_audio_features(**inputs)
                    if hasattr(out, "pooler_output"):
                        embed = out.pooler_output
                    elif hasattr(out, "last_hidden_state"):
                        embed = out.last_hidden_state[:, 0, :]
                    else:
                        embed = out
                    embed = embed / embed.norm(dim=-1, keepdim=True)
                    vector = embed.squeeze(0).cpu().numpy().astype(np.float32)

        provenance = ProvenanceRecord(
            source_method="semantic_model",
            analyzer_id=f"clap_audio_{self.model_version}",
            analyzer_version=self.model_version,
            ontology_version="clap_512d",
            processing_version=self.preprocessing_version,
            notes=f"device={device}, prep_strategy={prep_strategy}",
        )

        facts = SemanticEmbeddingFacts(
            model_id=self.model_id,
            model_version=self.model_version,
            embedding_dim=self.embedding_dim,
            preprocessing_version=self.preprocessing_version,
            vector=vector.tolist(),
            provenance=provenance,
        )

        return vector, facts

    def embed_audio_batch(
        self,
        items: List[Tuple[np.ndarray, int, float]],
        batch_size: int = 32,
    ) -> List[Tuple[np.ndarray, SemanticEmbeddingFacts]]:
        """
        High-throughput batched semantic embeddings on CUDA GPU.
        Batches audio waveforms into tensor chunks of size batch_size without
        per-sample VRAM flushing stalls.
        """
        import torch

        if not items:
            return []

        processor, model = self._model_manager.get_clap(self.model_id)
        device = self._model_manager.device

        # 1. Preprocess & standardize audio waveforms to 48kHz
        processed_chunks: List[np.ndarray] = []
        for wf, sr, dur in items:
            if wf.ndim > 1:
                wf = np.mean(wf, axis=0 if wf.shape[0] < wf.shape[1] else 1)
            wf = wf.astype(np.float32)

            # Center/pad short audio (< 1s)
            if dur < 1.0 or len(wf) < sr:
                wf, _ = AudioPreprocessor.preprocess_short_audio(wf, sr, target_duration_sec=1.0)
            # Limit maximum length to 10 seconds for uniform batching (standard for CLAP)
            elif len(wf) > sr * 10:
                wf = wf[: int(sr * 10)]

            # Resample to 48kHz
            wf_48k = self._resample_if_needed(wf, sr, target_sr=48000)
            processed_chunks.append(wf_48k)

        all_vectors: List[np.ndarray] = []

        # 2. Process in mini-batches on GPU
        for i in range(0, len(processed_chunks), batch_size):
            chunk = processed_chunks[i : i + batch_size]
            try:
                inputs = processor(audio=chunk, sampling_rate=48000, return_tensors="pt", padding=True)
                inputs = {k: v.to(device) for k, v in inputs.items()}
                with torch.inference_mode():
                    with self._model_manager.manage_gpu_memory():
                        out = model.get_audio_features(**inputs)
                        if hasattr(out, "pooler_output"):
                            embed = out.pooler_output
                        elif hasattr(out, "last_hidden_state"):
                            embed = out.last_hidden_state[:, 0, :]
                        else:
                            embed = out
                        embed = embed / embed.norm(dim=-1, keepdim=True)
                        vecs = embed.cpu().numpy().astype(np.float32)
                        for v in vecs:
                            all_vectors.append(v)
            except Exception as e:
                logger.warning(f"Batch embedding failed for chunk {i}:{i+batch_size} ({e}), falling back to single-item")
                # Fallback to single-item processing for this chunk
                for wf_single in chunk:
                    try:
                        inp_s = processor(audio=wf_single, sampling_rate=48000, return_tensors="pt")
                        inp_s = {k: v.to(device) for k, v in inp_s.items()}
                        with torch.inference_mode():
                            with self._model_manager.manage_gpu_memory():
                                o = model.get_audio_features(**inp_s)
                                e = o.pooler_output if hasattr(o, "pooler_output") else o
                                e = e / e.norm(dim=-1, keepdim=True)
                    except Exception as err:
                        logger.warning(f"GPU processing failed for single audio item ({err}), attempting CPU fallback")
                        try:
                            self._model_manager.clear_vram()
                            inp_cpu = processor(audio=wf_single, sampling_rate=48000, return_tensors="pt")
                            model_cpu = model.to("cpu")
                            with torch.inference_mode():
                                o = model_cpu.get_audio_features(**inp_cpu)
                                e = o.pooler_output if hasattr(o, "pooler_output") else o
                                e = e / e.norm(dim=-1, keepdim=True)
                                all_vectors.append(e.squeeze(0).cpu().numpy().astype(np.float32))
                            if str(device) != "cpu":
                                model.to(device)
                        except Exception as cpu_err:
                            logger.error(f"CPU fallback also failed ({cpu_err}), using zero vector placeholder")
                            all_vectors.append(np.zeros(self.embedding_dim, dtype=np.float32))

        # Clean VRAM once after the entire batch finishes
        self._model_manager.clear_vram()

        results: List[Tuple[np.ndarray, SemanticEmbeddingFacts]] = []
        for vec in all_vectors:
            prov = ProvenanceRecord(
                source_method="semantic_model",
                analyzer_id=f"clap_audio_batch_{self.model_version}",
                analyzer_version=self.model_version,
                ontology_version="clap_512d",
                processing_version=self.preprocessing_version,
                notes=f"device={device}, batch_inference=True",
            )
            facts = SemanticEmbeddingFacts(
                model_id=self.model_id,
                model_version=self.model_version,
                embedding_dim=self.embedding_dim,
                preprocessing_version=self.preprocessing_version,
                vector=vec.tolist(),
                provenance=prov,
            )
            results.append((vec, facts))

        return results

    def embed_text(self, text: str) -> Tuple[np.ndarray, ProvenanceRecord]:
        """
        Generates 512-dimensional L2-normalized semantic embedding for a natural-language text description.
        Supports single atomic concepts or compound queries.
        """
        import torch

        processor, model = self._model_manager.get_clap(self.model_id)
        device = self._model_manager.device

        cleaned_text = text.strip()
        inputs = processor(text=[cleaned_text], return_tensors="pt", padding=True)
        inputs = {k: v.to(device) for k, v in inputs.items()}

        with torch.no_grad():
            with self._model_manager.manage_gpu_memory():
                out = model.get_text_features(**inputs)
                if hasattr(out, "pooler_output"):
                    embed = out.pooler_output
                elif hasattr(out, "last_hidden_state"):
                    embed = out.last_hidden_state[:, 0, :]
                else:
                    embed = out
                embed = embed / embed.norm(dim=-1, keepdim=True)
                vector = embed.squeeze(0).cpu().numpy().astype(np.float32)

        provenance = ProvenanceRecord(
            source_method="semantic_model",
            analyzer_id=f"clap_text_{self.model_version}",
            analyzer_version=self.model_version,
            ontology_version="clap_512d",
            notes=f"device={device}, text='{cleaned_text[:50]}'",
        )

        return vector, provenance

    def embed_text_batch(self, texts: List[str]) -> Tuple[np.ndarray, ProvenanceRecord]:
        """
        Generates batch of 512-dimensional text embeddings.
        Supports atomic query decomposition for future Phase 3 query planning.
        """
        import torch

        if not texts:
            return np.empty((0, self.embedding_dim), dtype=np.float32), ProvenanceRecord(
                source_method="semantic_model",
                analyzer_id=f"clap_text_batch_{self.model_version}",
            )

        processor, model = self._model_manager.get_clap(self.model_id)
        device = self._model_manager.device

        clean_texts = [t.strip() for t in texts if t.strip()]
        inputs = processor(text=clean_texts, return_tensors="pt", padding=True)
        inputs = {k: v.to(device) for k, v in inputs.items()}

        with torch.no_grad():
            with self._model_manager.manage_gpu_memory():
                out = model.get_text_features(**inputs)
                if hasattr(out, "pooler_output"):
                    embed = out.pooler_output
                elif hasattr(out, "last_hidden_state"):
                    embed = out.last_hidden_state[:, 0, :]
                else:
                    embed = out
                embed = embed / embed.norm(dim=-1, keepdim=True)
                matrix = embed.cpu().numpy().astype(np.float32)

        provenance = ProvenanceRecord(
            source_method="semantic_model",
            analyzer_id=f"clap_text_batch_{self.model_version}",
            analyzer_version=self.model_version,
            ontology_version="clap_512d",
            notes=f"batch_size={len(clean_texts)}",
        )

        return matrix, provenance

    @staticmethod
    def compute_similarity(vector_a: np.ndarray, vector_b: np.ndarray) -> float:
        """Computes cosine similarity between two L2-normalized 512-d embeddings."""
        return float(np.dot(vector_a, vector_b))
