"""
Dedicated Audio Event & Classifier Adapters (Phase 2).
Enforces clean adapter interface, preservation of raw model outputs,
no arbitrary universal thresholding, and temporal event interval detection.
"""

from __future__ import annotations

import abc
import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import scipy.signal

from audiobook_factory.contracts import (
    AudioEventRecord,
    ClassifierInferences,
    ClassifierPrediction,
    ProvenanceRecord,
)
from audiobook_factory.sonic_model_manager import AudioPreprocessor, SonicModelManager

logger = logging.getLogger("audiobook_factory.audio_classifier_adapters")

# Clean, conservative normalization from AudioSet 527 classes to studio taxonomy
AUDIOSET_TO_STUDIO_ONTOLOGY: Dict[str, str] = {
    "Door": "architectural.door",
    "Sliding door": "architectural.door.sliding",
    "Knock": "architectural.door.knock",
    "Cupboard open or close": "architectural.furniture.cupboard",
    "Drawer open or close": "architectural.furniture.drawer",
    "Footsteps": "human.footsteps",
    "Walk, footsteps": "human.footsteps.walk",
    "Running": "human.footsteps.run",
    "Rain": "weather.rain",
    "Raindrop": "weather.raindrop",
    "Thunder": "weather.thunder",
    "Thunderstorm": "weather.thunderstorm",
    "Wind": "weather.wind",
    "Howl": "nature.creature.howl",
    "Water": "fluid.water",
    "Pour": "fluid.pour",
    "Drip": "fluid.drip",
    "Splash, splatter": "fluid.splash",
    "Glass": "material.glass",
    "Shatter": "material.glass.break",
    "Wood": "material.wood",
    "Crack": "material.break.crack",
    "Explosion": "combat.explosion",
    "Burst, pop": "transient.pop",
    "Gunshot, gunfire": "combat.gunshot",
    "Screaming": "human.vocal.scream",
    "Laughter": "human.vocal.laugh",
    "Crying, sobbing": "human.vocal.cry",
    "Whispering": "human.vocal.whisper",
    "Gasp": "human.vocal.gasp",
    "Sigh": "human.vocal.sigh",
    "Sine wave": "tone.sine",
    "Chirp tone": "tone.chirp",
    "Bell": "metal.bell",
    "Bicycle bell": "metal.bell.bicycle",
    "Chime": "metal.chime",
    "Fire": "ambient.fire",
    "Crackling": "ambient.fire.crackling",
    "Bird": "nature.bird",
    "Bird vocalization, bird call, bird song": "nature.bird.song",
    "Insect": "nature.insect",
    "Cricket": "nature.cricket",
    # Music & Instruments
    "Music": "music.instrumental",
    "Musical instrument": "music.instrument",
    "Scary music": "music.mood.scary",
    "Timpani": "music.instrument.timpani",
    "Zither": "music.instrument.zither",
    # Human Voice & Crowd
    "Speech": "vocal.speech",
    "Singing": "vocal.singing",
    "Crowd": "human.crowd",
    "Hubbub, speech noise, speech": "human.crowd.walla",
    "Babble": "human.crowd.babble",
    # Metal Impacts & Tableware
    "Clang": "metal.impact.clang",
    "Ding": "metal.impact.ding",
    "Ping": "metal.impact.ping",
    "Dishes, pots, and pans": "foley.tableware.dishes",
    "Chink, clink": "foley.tableware.clink",
}


class BaseAudioClassifier(abc.ABC):
    """Abstract adapter interface for dedicated audio classification models."""

    @property
    @abc.abstractmethod
    def model_id(self) -> str:
        """Unique model identifier (e.g. HuggingFace repo or checkpoint ID)."""
        pass

    @property
    @abc.abstractmethod
    def model_version(self) -> str:
        """Version string of the classifier model."""
        pass

    @property
    @abc.abstractmethod
    def ontology_id(self) -> str:
        """Ontology or taxonomy identifier (e.g. 'audioset_527')."""
        pass

    @abc.abstractmethod
    def classify(
        self,
        waveform: np.ndarray,
        sample_rate: int,
        duration_sec: float,
        top_k: int = 15,
    ) -> ClassifierInferences:
        """Runs audio classification and returns multi-label inferences preserving raw evidence."""
        pass

    @abc.abstractmethod
    def detect_temporal_events(
        self,
        waveform: np.ndarray,
        sample_rate: int,
        duration_sec: float,
        score_threshold: float = 0.20,
    ) -> List[AudioEventRecord]:
        """Detects temporally localized sound events across time intervals."""
        pass


class ASTClassifierAdapter(BaseAudioClassifier):
    """
    Audio Spectrogram Transformer (AST) Classifier Adapter.
    Trained on AudioSet (527 classes).
    State-of-the-art mAP, native Hugging Face safetensors, robust on PyTorch 2.6 CUDA and CPU.
    """

    def __init__(
        self,
        model_id: str = "MIT/ast-finetuned-audioset-10-10-0.4593",
        model_version: str = "1.0.0",
        ontology_id: str = "audioset_527",
    ) -> None:
        self._model_id = model_id
        self._model_version = model_version
        self._ontology_id = ontology_id
        self._model_manager = SonicModelManager()

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def model_version(self) -> str:
        return self._model_version

    @property
    def ontology_id(self) -> str:
        return self._ontology_id

    def _resample_if_needed(self, waveform: np.ndarray, orig_sr: int, target_sr: int = 16000) -> np.ndarray:
        """Resample waveform to 16,000 Hz required by AST."""
        if orig_sr == target_sr:
            return waveform
        num_target_samples = int(round(len(waveform) * target_sr / orig_sr))
        return scipy.signal.resample(waveform, num_target_samples).astype(np.float32)

    def classify(
        self,
        waveform: np.ndarray,
        sample_rate: int,
        duration_sec: float,
        top_k: int = 15,
    ) -> ClassifierInferences:
        """
        Classifies audio clip and returns full multi-label inferences.
        Preserves raw unthresholded sigmoid scores, model provenance, and negative evidence.
        """
        import torch

        # Handle micro-SFX / short audio (< 1.0 sec)
        prep_strategy = "direct"
        if duration_sec < 1.0 or len(waveform) < sample_rate:
            waveform, prep_strategy = AudioPreprocessor.preprocess_short_audio(
                waveform, sample_rate, target_duration_sec=1.0
            )

        # AST requires 16kHz
        wav_16k = self._resample_if_needed(waveform, sample_rate, target_sr=16000)

        extractor, model = self._model_manager.get_ast_classifier(self.model_id)
        device = self._model_manager.device

        inputs = extractor(wav_16k, sampling_rate=16000, return_tensors="pt")
        inputs = {k: v.to(device) for k, v in inputs.items()}

        with torch.no_grad():
            with self._model_manager.manage_gpu_memory():
                logits = model(**inputs).logits
                # Compute raw sigmoid probabilities without discarding raw values
                probs = torch.sigmoid(logits).squeeze().cpu().numpy()

        id2label = model.config.id2label
        num_classes = len(probs)

        # Sort descending
        sorted_indices = np.argsort(probs)[::-1]

        predictions: List[ClassifierPrediction] = []
        top_labels: List[str] = []

        for rank, idx in enumerate(sorted_indices[:top_k], start=1):
            raw_lbl = str(id2label[int(idx)])
            raw_score = float(probs[idx])
            norm_lbl = AUDIOSET_TO_STUDIO_ONTOLOGY.get(raw_lbl, None)

            pred = ClassifierPrediction(
                raw_label=raw_lbl,
                normalized_label=norm_lbl,
                raw_score=round(raw_score, 5),
                calibrated_score=None,  # Section 6: No invented calibration
                rank=rank,
                ontology_id=self.ontology_id,
                start_sec=0.0,
                end_sec=round(duration_sec, 3),
            )
            predictions.append(pred)
            top_labels.append(norm_lbl or raw_lbl)

        # Negative evidence: classes with lowest predicted likelihood (< 0.005)
        neg_indices = sorted_indices[-10:]
        negative_evidence = [str(id2label[int(idx)]) for idx in neg_indices if probs[idx] < 0.005]

        provenance = ProvenanceRecord(
            source_method="classifier",
            analyzer_id=f"ast_classifier_{self.model_version}",
            analyzer_version=self.model_version,
            ontology_version=self.ontology_id,
            confidence=round(float(predictions[0].raw_score), 4) if predictions else None,
            notes=f"device={device}, prep_strategy={prep_strategy}, top_k={top_k}",
        )

        return ClassifierInferences(
            model_id=self.model_id,
            model_version=self.model_version,
            ontology_id=self.ontology_id,
            predictions=predictions,
            top_labels=top_labels,
            negative_evidence=negative_evidence,
            provenance=provenance,
        )

    def detect_temporal_events(
        self,
        waveform: np.ndarray,
        sample_rate: int,
        duration_sec: float,
        score_threshold: float = 0.20,
    ) -> List[AudioEventRecord]:
        """
        Detects temporally localized events.
        For longer audio (> 10s), slices into overlapping 10s windows with 5s hop.
        For short audio (<= 10s), preserves single interval.
        """
        import torch

        events: List[AudioEventRecord] = []

        # If audio is short, run single interval detection
        if duration_sec <= 10.0:
            inferences = self.classify(waveform, sample_rate, duration_sec, top_k=5)
            for p in inferences.predictions:
                if p.raw_score >= score_threshold:
                    events.append(
                        AudioEventRecord(
                            event_type="classifier_observation_window",
                            start_sec=0.0,
                            end_sec=round(duration_sec, 3),
                            confidence=p.raw_score,
                            source_method="classifier",
                            detector_id=self.model_id,
                            metadata={
                                "raw_label": p.raw_label,
                                "normalized_label": p.normalized_label,
                                "ontology_id": self.ontology_id,
                                "rank": p.rank,
                                "window_type": "full_file_observation_window",
                            },
                        )
                    )
            return events

        # Slicing for long audio/ambience (observation windows, not discrete acoustic events)
        windows = AudioPreprocessor.slice_sliding_windows(
            waveform, sample_rate, window_sec=10.0, hop_sec=5.0
        )
        extractor, model = self._model_manager.get_ast_classifier(self.model_id)
        device = self._model_manager.device
        id2label = model.config.id2label

        for start_sec, end_sec, chunk in windows:
            dur = end_sec - start_sec
            if dur < 0.5:
                continue

            chunk_16k = self._resample_if_needed(chunk, sample_rate, target_sr=16000)
            inputs = extractor(chunk_16k, sampling_rate=16000, return_tensors="pt")
            inputs = {k: v.to(device) for k, v in inputs.items()}

            with torch.no_grad():
                with self._model_manager.manage_gpu_memory():
                    logits = model(**inputs).logits
                    probs = torch.sigmoid(logits).squeeze().cpu().numpy()

            top_indices = np.argsort(probs)[-3:][::-1]
            for idx in top_indices:
                score = float(probs[idx])
                if score >= score_threshold:
                    raw_lbl = str(id2label[int(idx)])
                    norm_lbl = AUDIOSET_TO_STUDIO_ONTOLOGY.get(raw_lbl, None)
                    events.append(
                        AudioEventRecord(
                            event_type="classifier_observation_window",
                            start_sec=start_sec,
                            end_sec=end_sec,
                            confidence=round(score, 4),
                            source_method="classifier",
                            detector_id=self.model_id,
                            metadata={
                                "raw_label": raw_lbl,
                                "normalized_label": norm_lbl,
                                "ontology_id": self.ontology_id,
                                "window_type": "sliding_10s_hop_5s",
                            },
                        )
                    )

        return events
