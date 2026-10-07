---
name: audio-engineer-ffmpeg
description: >-
  Studio vocal audio engineering, 4D parametric EQ formants, and FFmpeg mastering skill.
  Covers broadcast EBU R128 (-19 LUFS vocal target, -1.5 dBTP ceiling), 4D acoustic formant DSP
  (pitch asetrate, tempo atempo, parametric EQ curves), Hann micro-fades (12ms/18ms), dialogue
  editorial concatenation, self-healing FFmpeg filter_complex graphs, and chaptered M4B packaging.
  Use when designing audio graphs, mastering audiobooks, diagnosing FFmpeg errors, or tuning vocal DSP.
---

# Audio Engineer & FFmpeg Mastering Skill (Studio Vocals Standard)

This skill governs professional broadcast audio mastering, 4D vocal formant DSP, and dialogue editorial processing adhering to Audible Studios and BBC Radio production standards.

> [!NOTE]
> On `prestable-v4.0-baseline`, the production engine is **Pure Vocals-Only**. The master pipeline focuses 100% on dialogue clarity, speech dynamics, 4D acoustic formants, and broadcast loudness.

---

## 1. Studio Vocal Mastering Standards

1. **Broadcast Loudness**: EBU R128 target `I=-19.0 LUFS` ($\pm 0.5$ LU), `TP=-1.5 dBFS`, `LRA <= 10.0 LU`.
2. **48kHz Studio Quality**: SOXR high-precision sinc resampling (`aresample=osr=48000`).
3. **Hann Micro-Fades**: 12ms pre-speech fade-in and 18ms post-speech fade-out eliminate digital clicks and DC offset transients.
4. **Dialogue Primacy**: Clear speech intelligibility with dry, crisp vocal presence and natural dynamic range.

---

## 2. 4D Acoustic Formant Filter Recipe

When multiple characters share a base voice model, FFmpeg applies 4D acoustic formant modulation:

```ffmpeg
# Example: -6% pitch downshift with tempo compensation and presence boost:
aresample=48000,asetrate=48000*0.94,aresample=48000,atempo=1.0638,equalizer=f=120:t=q:w=1.2:g=2.5,equalizer=f=3200:t=q:w=1.0:g=1.8[out]
```

### Formant Parameters:
- `pitch_delta_pct`: $\pm 4\%$ to $\pm 12\%$ shift via `asetrate` + `aresample`.
- `tempo_ratio`: Inverse tempo compensation ($1.0 / (1.0 + \Delta)$) via `atempo`.
- `parametric_eq`: Multi-band parametric equalizers targeting fundamental frequencies ($100-250$ Hz) and presence ($2.8-3.6$ kHz).

---

## 3. Broadcast Vocal Loudnorm Recipe (v5.0 Two-Pass Linear)

```ffmpeg
# Pass 1: Pre-Analysis Measurement
ffmpeg -y -i input.wav -af "highpass=f=45,loudnorm=I=-19.0:TP=-1.5:LRA=7.0:print_format=json" -f null -

# Pass 2: Linear Phase Broadcast Mastering (Zero Pause Pumping) + Post-Loudnorm Resampling
ffmpeg -y -i input.wav -af "highpass=f=45,loudnorm=I=-19.0:TP=-1.5:LRA=7.0:measured_I=MEASURED_I:measured_TP=MEASURED_TP:measured_LRA=MEASURED_LRA:measured_thresh=MEASURED_THRESH:offset=OFFSET:linear=true,aresample=osr=48000:filter_type=kaiser:dither_method=triangular" output_master.wav
```

### Critical DSP Invariants (v5.0):
1. **Zero Hardware De-Esser**: Synthetic neural voices have zero physical mic capsule sibilance. Destructive `deesser` filters are strictly banned because they attenuate authentic Hindi dental sibilants (*स, श, छ, थ, ध*).
2. **Post-Loudnorm Resampling**: Resampling (`aresample=osr=48000`) MUST be placed strictly *after* `loudnorm` to prevent FFmpeg's 192kHz internal upsampling from bloating chapter WAVs.
3. **No WSOLA `atempo` on Neural Dialogues**: WSOLA time-stretching causes robotic comb-filtering and phase cancellation on synthesized neural stems. Cadence is governed via speech tags, dramatic pauses, and LLM text formatting.

---

## 4. Dedicated Tools & MCP Servers

- **MCP Server**: `ffmpeg-audio`:
  - `ffmpeg_probe`: Probes duration, channels, codec, bit rate, and sample rate.
  - `ffmpeg_test_filter_graph`: Dry-runs filter graphs on audio to detect syntax errors before rendering.
  - `ffmpeg_render_master`: Renders audio graphs with EBU R128 broadcast mastering.
