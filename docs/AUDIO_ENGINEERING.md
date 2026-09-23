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
| **Dialogue-to-Masking Ratio (DMR Proxy)** | $\ge +10.0\text{ dB}$ | Dialogue stem ($DX$) must overpower the combined background bed ($ME$) by at least 10 dB. |
| **Dynamic Ducking Profiles** | Standard: $-16\text{ dB}$<br/>Intimate: $-22\text{ dB}$<br/>Combat Shock: $-24\text{ dB}$ | Calibrated ducking depths across standard dialogue, ASMR bedroom intimacy, and heavy concussive impacts. |
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

---

### 9. Hollywood & AAA-Game Combat Sound Design & Action Acoustics (ADR-017)
In AAA video games (God of War, The Witcher 3) and Hollywood action films, combat audio is never an unstructured din of loud sound effects playing simultaneously over shouting characters. Such an approach causes severe acoustic masking (DMR < +12 dB) and mono phase collapse ($r < 0.85$).

Audiobook Maker implements a five-pillar action acoustic architecture:

#### A. The 3-Layer Combat Sandwich
Every major physical impact (blade deflection, shield bash, bone crush, warhammer strike) is assembled across 3 discrete frequency layers:
1. **Layer 1: Transient Bite ($2.0\text{ kHz} - 7.5\text{ kHz}$):** High-frequency metallic scrape, blade ring, arrow release, or armor scrape. Delivers perceptual clarity and spatial pinpointing.
2. **Layer 2: Anatomical Body ($180\text{ Hz} - 1.4\text{ kHz}$):** Mid-frequency organic weight—flesh tearing, rib fracture, leather compression, or heavy body thud.
3. **Layer 3: LFE Sub-Thump ($45\text{ Hz} - 85\text{ Hz}$):** Tuned 52Hz sine or sub-harmonic burst, delivering solar plexus visceral impact on subwoofers and headphones.

#### B. Strict Mono Sub-Bass Anchor (< 90Hz)
- All low-frequency effects (`is_lfe_sub_drop=True`), sub-drops, and ground smashes are strictly centered at azimuth $pan = 0.0$ and summed to mono.
- This invariant guarantees that high-excursion bass energy does not suffer out-of-phase stereo cancellation when played on mono mobile devices or smart speakers ($r \ge 0.85$).

#### C. Temporal Action-Beat Splitting
- Lethal strikes, shield bashes, and skull-crushing blows **never play directly over vocal lines**.
- The screenplay director automatically splits combat action into dedicated $800\text{ ms} - 1500\text{ ms}$ speech-free intervals (`speaker: "Foley"`, `text: "[ACTION]"`). This provides an unmasked acoustic canvas for the 3-layer combat sandwich.

#### D. Dual-Perspective Spatial Staging
- Combat staging employs dual-perspective azimuth coordinates across the stereo panorama:
  - **Attacker Strikes & Shouts:** Panned Left ($-0.6$).
  - **Defender Parries & Grunts:** Panned Right ($+0.6$).
  - **Lethal Impacts & Weapon Clashes:** Anchored Dead Center ($0.0$).
- This provides deep acoustic spatial orientation, allowing the listener to perceive combat geometry clearly without single-ear fatigue.

#### E. Dynamic Combat Ducking & "The Smother Cut"
- **`PROFILE_COMBAT_SHOCK`**: Concussive blasts, flashbangs, or near-fatal strikes trigger deep $-24\text{ dB}$ attenuation with a prolonged $4000\text{ ms}$ release curve, accompanied by high-frequency tinnitus ringing beds.
- **The Smother Cut**: Screenplay direction injects $150\text{ ms} - 250\text{ ms}$ of hard digital silence immediately before a fatal strike lands, magnifying the explosive perceived impact of the subsequent strike.

---

### 10. Harry Potter / Pottermore Grade 4-Stem Decoupled Scene Acoustics (ADR-018)
To achieve the spatial immersion of BBC Radio 4 and Pottermore audio dramas, Audiobook Maker decouples environmental ambience into 4 independent stems per scene:

```text
Scene Ambience Manifest (SceneSoundscapeManifest)
├── Stem 1: Base Room Tone / Acoustic Hull (-34 to -36 LUFS) ────► Stereo Width: 1.35
├── Stem 2: Weather & Macro Elements (-30 to -32 LUFS) ──────────► Barrier Occlusion Lowpass (< 18kHz)
├── Stem 3: Social & Life Wallah (-28 to -30 LUFS) ──────────────► Stereo Width: 1.30
└── Stem 4: Stochastic Spot Transients (-22 to -26 dBFS) ────────► Dialogue Pause Gaps (>= 600ms)
```

#### A. Acoustic Barrier Occlusion
- When a scene takes place indoors (stone hall, tavern, bedroom, crypt), exterior macro elements (thunderstorms, howling wind, torrential rain) are filtered through a dynamic low-pass barrier occlusion filter ($1200\text{ Hz} - 1500\text{ Hz}$).
- When an action beat opens a window or door, the occlusion filter sweeps smoothly to $18\text{ kHz}$, delivering natural spatial realism.

#### B. Zero-Token Local Stochastic Transient Generator
- Continuous ambient loops feel repetitive and artificial over 20-minute chapters.
- The `generate_stochastic_cues` algorithm analyzes the `TimelineLedger` to identify pause slots between dialogue lines ($\ge 600\text{ ms}$).
- It scatters subtle Layer 4 micro-events (distant owls, candle sparks, floor creaks, ticking clocks, water drops) strictly during dialogue pauses.
- **Anti-Bloat Invariant**: Operates 100% locally with zero LLM token consumption.

#### C. Voice Limiter & Priority Stealing
- To prevent transient buildup and acoustic clutter when multiple Foley events collide, `filter_concurrency_window` enforces a $200\text{ ms}$ sliding window with a maximum concurrency of 3 simultaneous cues. Lower-priority cues are gracefully dropped.

#### D. Dialogue-to-Masking Ratio (DMR) Validation
- In `CinemaAudioEngine`, every chapter render computes the Dialogue-to-Masking Ratio proxy:
  $$\text{DMR} = \text{LUFS}_{\text{DX}} - \text{LUFS}_{\text{ME}} \ge +10.0\text{ dB}$$
- If the combined Music, Foley, and Ambience bed ($ME$) encroaches within 10 dB of the vocal dialogue track ($DX$), the render reports a DMR violation in `chapter_XXX_stem_ledger.json`.

#### E. Pre-Baked Multi-Phase Composite Asset Baker
- Multi-phase sound effects (e.g. Harry Potter magic spells: Phase A Gesture Pre-roll $0-100\text{ ms}$ $\rightarrow$ Phase B Arcane Exciter $100-300\text{ ms}$ $\rightarrow$ Phase C Sub-Bass Dissipation $40-60\text{ Hz}$) are pre-rendered offline using [`scripts/bake_foley_composites.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/scripts/bake_foley_composites.py).
- Pre-baked assets (`magic_lumos_light.wav`, `magic_expelliarmus_kinetic.wav`, `tactile_parchment_quill_scratch.wav`) are indexed directly into the SQLite FTS5 Sound Bank, ensuring zero runtime FFmpeg filter graph bloat.

---

### 11. Production DSP Reliability & Windows Graph Scaling (ADR-020)

#### A. Dynamic Filter Complex Script Piping (>6000 Chars)
In complex 4-stem scene acoustics where a chapter contains dozens of weather crossfades, crowd wallah loops, and Layer 4 stochastic spots, the resulting FFmpeg `-filter_complex` string can easily exceed 6,000 characters.
- **The Windows 8191-Character Boundary:** The Windows shell command interpreter (`cmd.exe` / `CreateProcessW`) imposes a strict 8,191-character limit on the entire command line. Passing an oversized filter string inline results in silent process termination or exit code 1.
- **Dynamic Script Execution:** In [`CinemaAudioEngine.render_discrete_stems`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/cinema_audio_engine.py), the engine measures `len(filter_str)`. If the filter complex exceeds 6,000 characters, it writes the graph to `{chapter_id}_amb_filter.txt` and supplies it to FFmpeg via `-filter_complex_script [path]`, ensuring indefinite scalability regardless of scene complexity. The script file is automatically unlinked upon completion.

#### B. Atomic Speech Audio Generation & In-Memory SNR Audit
To protect final chapters from acoustic defects (clipping distortion, faint low-RMS output, DC offset corruption, or mid-sentence stutters):
- Raw speech chunks from Gemini Flash Cloud TTS are written to a temporary destination (`.tmp.wav`).
- A 6-point forensic audit inspects the temporary file:
  - Peak amplitude ($\le 32700$, headroom against 0 dBFS clipping)
  - RMS floor ($\ge 30$, prevents faint/silent dropouts)
  - DC offset mean ($< 500$, eliminates transducer pop)
  - Inter-word silence ceiling
- If any defect is detected, the temporary file is unlinked immediately (`tmp_file.unlink(missing_ok=True)`) and retry logic is invoked. Only audio that passes 100% of checks is promoted atomically via `.replace(output_file)`, guaranteeing that defective WAVs never enter the multitrack mix.

