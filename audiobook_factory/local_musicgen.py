#!/usr/bin/env python3
"""
Audiobook Factory - Pillar 3.6: Local GPU MusicGen Engine (Meta MusicGen-Small).
Runs natively on NVIDIA CUDA GPUs (e.g. RTX 4050 with ~1.3 GB peak VRAM footprint).
100% Free, zero external API tokens, zero rate limits.
"""

import os
import torch
from pathlib import Path
from typing import Optional

_processor = None
_model = None


def _get_musicgen_pipeline():
    """Lazy load MusicGen-small model into CUDA memory on demand."""
    global _processor, _model
    if _model is None:
        from transformers import MusicgenForConditionalGeneration, AutoProcessor

        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if device == "cuda" else torch.float32

        print(f"[*] Loading facebook/musicgen-small onto {device} ({dtype})...")
        _processor = AutoProcessor.from_pretrained("facebook/musicgen-small")
        _model = MusicgenForConditionalGeneration.from_pretrained(
            "facebook/musicgen-small",
            torch_dtype=dtype,
        ).to(device)
        print(f"[+] MusicGen model ready! VRAM allocated: {torch.cuda.memory_allocated() / (1024**2):.1f} MB")

    return _processor, _model


def generate_musicgen_audio(
    prompt: str,
    output_file: Path,
    duration_sec: float = 15.0,
) -> Path:
    """
    Generate instrumental atmospheric background score using local RTX GPU.
    Outputs 32kHz broadcast WAV audio file.
    """
    import scipy.io.wavfile

    output_file = Path(output_file).resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)

    processor, model = _get_musicgen_pipeline()
    device = model.device

    inputs = processor(
        text=[prompt],
        padding=True,
        return_tensors="pt",
    ).to(device)

    # 50 tokens ~= 1 second of audio
    tokens_to_gen = int(min(duration_sec, 30.0) * 50)
    print(f"[*] Generating {tokens_to_gen // 50}s audio on {device} for prompt: '{prompt}'...")

    with torch.inference_mode():
        audio_values = model.generate(**inputs, max_new_tokens=tokens_to_gen)

    sampling_rate = model.config.audio_encoder.sampling_rate
    audio_data = audio_values[0, 0].cpu().float().numpy()

    scipy.io.wavfile.write(str(output_file), rate=sampling_rate, data=audio_data)
    print(f"[+] MusicGen score saved ({output_file.stat().st_size} bytes) -> {output_file.name}")
    return output_file
