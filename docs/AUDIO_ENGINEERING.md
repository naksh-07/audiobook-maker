# 🎛️ Audio Engineering & DSP Mastering Manual

## Executive Summary

Audio drama mixing requires a delicate acoustic balance between **dialogue intelligibility**, **dynamic emotional music**, and **immersive environmental ambience**.

In legacy audiobook production, music often drowns out whispers, abrupt volume spikes clip playback on smartphone speakers, and non-standard sample rates cause distortion on Android DACs.

**Audiobook Maker v4.0** enforces Hollywood film mixing and international broadcast standards (EBU R128, ITU-R BS.1770-4) using automated, self-healing FFmpeg filter graphs.

---

## 📻 Broadcast Specifications & Target Metrics

| Parameter | Standard Value | Rationale |
|---|:---:|---|
| **Sample Rate** | `48,000 Hz` | Standard for film, television, and Android hardware DACs (`AudioFlinger`). |
| **Bit Depth** | `16-bit PCM` (lossless) / `AAC-LC` 192 kbps | Uncompressed dynamic range during processing; clean high-fidelity delivery. |
| **Integrated Loudness** | `-19.0 LUFS` ($\pm 1.0$ LU) | Broadcast audiobook standard (Audible / Apple Books / BBC Radio 4; standardized Gate 5 & Gate 6B). |
| **True Peak Ceiling** | `-1.5 dBTP` (Normal)<br/>`-2.0 dBTP` (Explosive scenes) | Guarantees zero inter-sample peak distortion during lossy MP3/AAC encoding. |
| **Loudness Range (LRA)** | `7.0 LU` (Standard)<br/>`6.0 LU` (Whisper scenes) | Balances dramatic dynamic range with intelligibility in noisy environments (cars, commutes). |
| **Acoustic Silence Mandate** | $\ge 60.0\%$ | Prevents listener fatigue by ensuring music is surgical, not a constant wall of sound. |
| **Dialogue-to-Music Ratio (DMR)** | $\ge +12.0\text{ dB}$ | Dialogue must always overpower music in the vocal corridor ($300\text{ Hz} - 3.5\text{ kHz}$). |
| **Stereo Phase Correlation** | $r \ge +0.85$ (Dialogue)<br/>$r \ge +0.20$ (Full mix) | Prevents acoustic cancellation when stereo audio is collapsed to mono smart speakers. |

---

## 🎚️ The 5-Track Audio Drama Hierarchy

```text
[0:a] DIALOGUE BUS (DX)  ───► Split ──┬─► Direct Vocal (Dry) ──────────────────────────┐
                                     ├─► Sidechain Detector ──┐                       │
                                     └─► Reverb Send (Aux)    │                       │
                                                              ▼                       │
[1:a] MUSIC BUS (MX)     ───► 2.2kHz Notch EQ ──► Fast Sidechain Ducking (-16dB) ─────┼─► AMIX
                                                                                      │  (Master Sum)
[2:a] AMBIENCE BED (AMB) ───► Decoupled Level (-32 LUFS Bed, Clean Unnotched) ────────┼─►
                                                                                      │
[3:a] FOLEY BUS (FX)     ───► Direct Foley (Dry, Transient Crisp, Whisper Attenuated) ┤
                         └──► Reverb Send (Aux)                                       │
                                   │                                                  │
                 Shared Reverb Send Mix ──────► Dynamic Impulse Response (Wet Tail) ──┘
                                                              │
                                                              ▼
                                                   EBU R128 Master Bus
                                              (aresample + loudnorm + alimiter)
```

---

## 🔬 Core DSP Mechanisms

### 1. Whisper-Safe Dynamic Sidechain Ducking
- **Problem**: When a character whispers, conventional voice detectors (threshold $\ge -20\text{ dBFS}$) fail to detect speech, allowing loud background music to obliterate the dialogue.
- **Solution**: The sidechain compressor threshold is calibrated to **`0.018` linear ($-34.9\text{ dBFS}$)** with a fast attack ($15\text{ ms}$) and natural musical release ($350\text{ ms}$):
  ```text
  sidechaincompress=threshold=0.018:ratio=4.0:attack=15:release=350:knee=2.0
  ```
- **Result**: Even trailing whispers, soft breath intakes, and muttered incantations trigger immediate, smooth ducking of the underscore.

---

### 2. Music-Only 2.2kHz Vocal Spectral Notch Filter
- **Problem**: Broad frequency ducking can make music sound like it is "pumping" uncomfortably whenever dialogue begins. Furthermore, applying EQ to the entire master mix or composite bus severely degrades the high-frequency transient attack of swords, footsteps, and environmental air.
- **Solution**: The notch filter is isolated **strictly to the Music Bus `[0:a]`** before mixing with Foley and Ambience:
  ```text
  [0:a]equalizer=f=2200:t=q:w=1.5:g=-5.5[mx_notched];
  [mx_notched][1:a][2:a]amix=inputs=3:duration=first:normalize=0,aresample=48000[meout]
  ```
- **Result**: Carves an acoustic frequency corridor specifically for human vocal formant energy ($1.5\text{ kHz} - 3.5\text{ kHz}$) within the musical score only. Foley sound effects retain their razor-sharp high-frequency transients and the Ambience bed preserves its expansive stereo presence without vocal masking.

---

### 3. Dynamic Impulse Response Reverb Presets
Rather than applying a static, artificial echo to every scene, the engine dynamically selects reverberation parameters based on the scene's acoustic environment:

```python
# audiobook_factory/manifest_renderer.py
def get_reverb_filter_string(preset: str = "room") -> Tuple[str, float]:
    p = str(preset).lower()
    if any(k in p for k in ("cathedral", "crypt", "temple", "cavern", "large_hall")):
        # Large acoustic space with lingering reflections
        return "aecho=0.8:0.8:100|180|260:0.55|0.40|0.25", 0.32
    elif any(k in p for k in ("open_road", "exterior", "forest", "field", "outdoor")):
        # Subtle exterior presence; very tight reflections
        return "aecho=0.8:0.7:20|40:0.08|0.04", 0.05
    elif any(k in p for k in ("bedroom", "intimate", "cabin", "small_room", "study")):
        # Tight, intimate domestic room
        return "aecho=0.8:0.8:30|60|90:0.20|0.15|0.08", 0.18
    else:  # stone_hall, tavern, castle, default
        return "aecho=0.8:0.8:50|80|120:0.35|0.25|0.15", 0.25
```

---

### 4. Constant-Power Dialogue Spatial Soundstage
- **Stereo Placement**:
  - **Narrator**: Always anchored dead-center ($pan = 0.0$) with equal energy in left and right channels.
  - **Cast Characters**: Assigned spatial azimuth coordinates from screenplay directives ($pan \in [-1.0, +1.0]$, typically subtle separation between $-0.15$ and $+0.15$).
- **Acoustic Mathematics**: Constant-power circular panning rule:
  $$\theta = \frac{\pi}{4}(1 + pan)$$
  $$gain_L = \cos(\theta), \quad gain_R = \sin(\theta)$$
- **Mono Compatibility Invariant**:
  Because both channels derive from the same mono vocal chunk with amplitude scaling, the stereo phase correlation is mathematically:
  $$\text{Pearson } r = 1.0$$
  This guarantees **zero phase cancellation** when listened to on mono speakers.

---

### 5. Dynamic Headroom & True Peak Limiting
- **Explosive Battle Scenes**:
  - When screenplay segments have `intensity_level in ("high", "explosive")`:
    - Limiter threshold tightens to `0.82` (attack `2ms`).
    - True peak ceiling drops to `-2.0 dBTP`.
    - Protects the DAC from sudden screams, spells, and battle roars.
- **Whisper & Intimate Scenes**:
  - When screenplay segments have `intensity_level in ("low", "whisper")`:
    - Dynamic Loudness Range tightens to `LRA = 6.0 LU`.
    - Lifts soft vocal passages gently above the ambient background bed.
- **Master Limiter Chain**:
  ```text
  aresample=osr=48000,highpass=f=60,afftdn=nr=8:nf=-35,deesser=i=0.35:m=0.5:f=0.14,lowpass=f=14000,
  loudnorm=I=-19.0:TP=-1.5:LRA=7.0,alimiter=limit=0.89:attack=5:release=50:level=false
  ```

---

### 6. Whisper Collision Attenuation (`attenuate_foley_whisper_collisions`)
- **Problem**: When a dialogue segment contains delicate whispers or quiet introspection, triggering a standard Foley cue at nominal level (e.g. $-15.0\text{ dBFS}$) completely obliterates the vocal nuance and startles the listener.
- **Solution**: The `AgentDirector` invokes `attenuate_foley_whisper_collisions(foley_cues, script_segments, attenuation_db=-6.0)`.
- **Heuristic**: Detects any Foley cue scheduled during a dialogue segment marked with `intensity_level in ("low", "whisper")` or delivery style containing whispered indicators.
- **Result**: Automatically attenuates colliding Foley cues by $-6.0\text{ dBFS}$, ensuring intimate whispers maintain uncompromised acoustic intelligibility without sacrificing Foley presence.

---

### 7. M4B AAC Container Safety & Transcoding
- **Problem**: Passing uncompressed PCM WAV stems (`pcm_s16le`) or mixed codecs directly into an MP4/M4B muxer with `-c:a copy` causes instant FFmpeg container multiplexer crashes.
- **Solution**: The packager runs strict pre-flight codec validation:
  ```python
  is_all_aac = all(f.suffix.lower() in (".m4a", ".aac") for f in chapter_audio_files)
  audio_codec_args = ["-c:a", "copy"] if is_all_aac else ["-c:a", "aac", "-b:a", "192k"]
  ```
- **Result**: Automatically transcodes uncompressed 48kHz WAV masters to pristine 192 kbps AAC-LC with `+faststart` metadata header placement, guaranteeing 100% crash-free packaging across Audible, Apple Books, and Smart AudioBook Player.

---

### 8. Strict Agent Creative Mandate in Audio Engineering
- **Architectural Law**: Lower-tier DSP execution runtimes (`CinemaAudioEngine`, `ManifestRenderer`, `ffmpeg_mastering`) must never make creative sound design decisions or override agent directives.
- **Separation of Concerns**:
  - **Creative Intelligence**: Autonomous AI agents (`AgentDirector`) decide *what* plays, *when* it plays, *how loud* it is, and *where* it sits in the soundstage via the `CreativeManifest`.
  - **Deterministic Execution**: The DSP layer deterministically compiles and renders the manifest instructions into sample-accurate, phase-aligned, broadcast-compliant audio.
