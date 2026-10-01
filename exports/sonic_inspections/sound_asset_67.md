# Sonic Intelligence Canonical Inspection Report: Asset #67

**File Name**: `rain_thunder.ogg`  
**Title**: Rain Thunder  
**Category**: `AMB` / `Ambience`  
**License / Source**: Curated_Ambience (Public Domain / CC0)  
**Local Disk Status**: `LOCAL_DOWNLOADED`  

---

## 1. Agent Sound Card v3.0 (Active Production View)

### 🎵 Sound Card [ID: 67] Rain Thunder
- **File / Status [SOURCE_METADATA]**: `rain_thunder.ogg` | LOCAL (Cached) | **Duration [MEASURED]**: 18.90s
- **Source [SOURCE_METADATA]**: Curated_Ambience (Public Domain / CC0)
- **Taxonomy [SOURCE METADATA]**:
  - Category [SOURCE_METADATA]: `AMB` / `Ambience`
  - Physical [SOURCE_METADATA]: Exciter: `unspecified` | Resonator: `unspecified` | Action: `unspecified` | Surface: `unspecified`
  - Source Pack Mood [SOURCE_METADATA]: `unspecified`
- **Acoustics [MEASURED DSP]**:
  - Loudness [MEASURED]: -24.8 LUFS | True Peak [MEASURED]: -0.3 dBTP
  - Spectral [MEASURED]: Centroid 332 Hz (warm) | Dynamics [MEASURED]: `medium` (transient)
  - Speech Corridor Density (1kHz–4kHz) [MEASURED]: 0.25
- **Classifier Inferences [CLASSIFIER]**:
  - AudioSet [CLASSIFIER]: `weather.thunderstorm` (conf: 0.75, rank #1), `weather.thunder` (conf: 0.60, rank #2), `weather.rain` (conf: 0.57, rank #3)
  - Vocal Speech Probability [CLASSIFIER]: 0.00
  - Classifier Mood Evidence [CLASSIFIER]: None
- **Semantic Embedding [CLAP]**:
  - Query Similarity [CLASSIFIER]: None
- **Directorial Decisions & Mix Safety [AGENT_INTERPRETATION]**:
  - Dramatic Role [AGENT_INTERPRETATION]: `UNASSIGNED [AWAITING_AGENT_EVALUATION]`
  - Scene Purpose [AGENT_INTERPRETATION]: `UNASSIGNED [AGENT_INTERPRETATION: Awaiting SoundDirector]`
  - Emotional Suitability [AGENT_INTERPRETATION]: `UNINTERPRETED [AWAITING_AGENT_EVALUATION]`
  - Voice-Masking Judgment [AGENT_INTERPRETATION]: `UNASSESSED (Speech Density: 0.25 [MEASURED], Vocal Presence: 0.00 [CLASSIFIER]) [AWAITING MIX AGENT]` (Whisper Compatibility: `NOT_CALIBRATED`)
  - Dialogue Ducking Amount [AGENT_INTERPRETATION]: `SCENE_DEPENDENT (Deferred to Track 11 Mix Director)`
  - Placement / Recommended Usage [AGENT_INTERPRETATION]: `UNASSIGNED [AGENT_INTERPRETATION: Awaiting SoundDirector]`
  - Final Taxonomy [AGENT_INTERPRETATION]: `UNASSIGNED [AGENT_INTERPRETATION: Awaiting creative interpretation]`
- **Temporal Structure**: Active Region: 0.02s - 18.82s (Duration: 18.90s) [MEASURED DSP] | Window [0.00s - 10.00s] [OBSERVATION WINDOW]: weather.thunderstorm (0.74), weather.thunder (0.58) [CLASSIFIER INFERENCE] | Window [5.00s - 15.00s] [OBSERVATION WINDOW]: weather.thunderstorm (0.73), weather.rain (0.71) [CLASSIFIER INFERENCE] | ... and 1 more classifier observation windows | 5 transient onsets detected [MEASURED DSP]
- **Music & Tonal [MEASURED / SOURCE METADATA]**:
  - Tonal [MEASURED]: True (Pitch: 1520.7 Hz) [MEASURED DSP, autocorrelation peak > 0.55] | BPM [SOURCE_METADATA / MEASURED]: unavailable (unmeasured) | Key [SOURCE_METADATA]: unavailable (unmeasured) | Time Signature [SOURCE_METADATA]: unavailable (unmeasured)

- **Agent Creative Interpretation**: None [AGENT_INTERPRETATION: Asset unassigned in catalog; dramatic role, scene purpose, emotional suitability, and dialogue ducking evaluated per scene by SoundDirector / Mix Director]
- **Provenance & Quality**:
  - Metadata Completeness: 80% | Status: `full_phase2`
  - Provenance: DSP=`1.0.0`, AST=`AudioSet-527`, CLAP=`HTS-AT`
- **Retrieval Evidence**:
  - Direct asset lookup

---

## 2. Technical Audio Format & File Metadata

| Property | Value | Evidence / Method |
|---|---|---|
| **Duration** | `18.904s` | [MEASURED] Container Header Probing |
| **Container & Codec** | `ogg` / `vorbis` | [MEASURED] Audio Stream Probing |
| **Sample Rate** | `44100 Hz` | [MEASURED] Exact Sample Clock |
| **Channels** | `1 ch` (Mono) | [MEASURED] Channel Map |
| **Bit Depth** | `N/A (Lossy Codec)` | [MEASURED] Bit Resolution |
| **Bitrate** | `96043 bps` | [MEASURED] Stream Average |
| **File Size** | `226945 bytes` | [MEASURED] Disk File Size |

---

## 3. Measured DSP & Acoustic Facts (Sonic Genome Layer 1)

### Loudness & Dynamic Profiles [MEASURED DSP]
- **Integrated Loudness**: `-24.8 LUFS` (EBU R128)
- **True Peak**: `-0.3 dBTP`
- **Loudness Range (LRA)**: `14.5 LU`
- **RMS Level**: `-24.0 dBFS`
- **Peak Level**: `-0.38 dBFS`
- **Dynamic Range**: `23.62 dB`

### Spectral & Acoustic Fingerprint [MEASURED DSP]
- **Spectral Centroid**: `331.5 Hz` (**Brightness**: `warm`)
- **Spectral Bandwidth**: `920.9 Hz`
- **Spectral Rolloff (85%)**: `387.6 Hz`
- **Spectral Flatness**: `0.004`
- **Zero Crossing Rate**: `0.053`
- **Speech Corridor Density (1kHz - 4kHz)**: `0.25`
- **Vocal Clash Risk**: `LOW`

---

## 4. Temporal Structure & SED Active Intervals

- **Active Sound Region**: `0.02s - 18.82s (Duration: 18.90s) [MEASURED DSP]`
- **Silence Ratio**: `0.005 [MEASURED DSP]`
- **Transient Pulse Count**: `10 detected peaks [MEASURED DSP]`
- **Energy Envelope Character**: `sustained [DERIVED DSP]`
- **Major Transient Onsets**: `[0.02, 1.24, 3.64, 5.78, 6.4, 11.34, 11.6, 14.02, 14.36, 15.8]`

### Detected Temporal Intervals & Active Windows (15 total)
- `[0.02s - 18.82s]` **Active Audio Region** [MEASURED DSP, Detector: `frame_energy_gate_v1`]
- `[0.00s - 10.00s]` **Classifier Observation Window**: `weather.thunderstorm` (0.74), `weather.thunder` (0.58), `weather.rain` (0.56) [CLASSIFIER INFERENCE]
- `[5.00s - 15.00s]` **Classifier Observation Window**: `weather.thunderstorm` (0.73), `weather.rain` (0.71), `weather.thunder` (0.59) [CLASSIFIER INFERENCE]
- `[10.00s - 18.90s]` **Classifier Observation Window**: `weather.rain` (0.55), `Rain on surface` (0.48), `weather.raindrop` (0.41) [CLASSIFIER INFERENCE]
- **Transient Onsets [MEASURED DSP]**: [`0.02s`, `1.24s`, `3.64s`, `5.78s`, `6.40s`]

---

## 5. Music & Tonal Intelligence [MEASURED / SOURCE METADATA]

- **Is Tonal**: True (Pitch: 1520.7 Hz) [MEASURED DSP, autocorrelation peak > 0.55]
- **BPM / Tempo**: unavailable (unmeasured)
- **Key / Tonality**: unavailable (unmeasured)
- **Time Signature**: unavailable (unmeasured)

---

## 6. AI Classifier Predictions (AST AudioSet 527) [CLASSIFIER INFERENCE]

| Rank | Normalized Label | Raw AudioSet Label | Confidence | Time Window |
|:---:|---|---|:---:|:---:|
| #1 | `weather.thunderstorm` | Thunderstorm | **0.752** | 0.0s - 18.9s |
| #2 | `weather.thunder` | Thunder | **0.600** | 0.0s - 18.9s |
| #3 | `weather.rain` | Rain | **0.568** | 0.0s - 18.9s |
| #4 | `—` | Rain on surface | **0.172** | 0.0s - 18.9s |
| #5 | `weather.raindrop` | Raindrop | **0.137** | 0.0s - 18.9s |
| #6 | `—` | Cutlery, silverware | **0.053** | 0.0s - 18.9s |
| #7 | `—` | Frying (food) | **0.051** | 0.0s - 18.9s |
| #8 | `foley.tableware.dishes` | Dishes, pots, and pans | **0.051** | 0.0s - 18.9s |
| #9 | `—` | Sizzle | **0.036** | 0.0s - 18.9s |
| #10 | `—` | Stir | **0.022** | 0.0s - 18.9s |

---

## 7. CLAP Semantic Vector Embedding (512-d Open-Vocabulary) [EMBEDDING]

- **Model**: `laion/clap-htsat-unfused` (Version: `2023_v1`)
- **Vector Dimensions**: 512-d (2048 bytes IEEE-754)
- **L2 Norm**: 1.0 (Unit norm verified: `True`)
- **Vector Sample (Head)**: `[0.04882, -0.08616, 0.01179, -0.04848, 0.03483]`

---

## 8. Psychoacoustics, Mix Evidence & Agent Directorial Guidelines

### Measurable Mix Evidence [MEASURED DSP & CLASSIFIER]
- **Speech Corridor Density (1kHz–4kHz)**: `0.25` [MEASURED DSP]
- **Classifier Vocal / Speech Presence**: `0.0042` [CLASSIFIER INFERENCE]

### Contextual Directorial Status [AGENT_INTERPRETATION]
- **Dramatic Role**: `UNASSIGNED` [AWAITING_AGENT_EVALUATION]
- **Scene Purpose**: `UNASSIGNED` [AGENT_INTERPRETATION: Awaiting SoundDirector]
- **Emotional Suitability**: `UNINTERPRETED` [AWAITING_AGENT_EVALUATION]
- **Voice Masking Judgment**: **`UNASSESSED`** [UNASSESSED: Requires Mix Agent evaluation based on measured speech corridor density]
- **Whisper Compatibility**: `NOT_CALIBRATED` [NOT_CALIBRATED]
- **Recommended Dialogue Ducking**: **`SCENE_DEPENDENT`** [SCENE_DEPENDENT / DEFERRED_TO_MIX_AGENT]
- **Placement & Usage**: `UNASSIGNED` [AGENT_INTERPRETATION: Awaiting SoundDirector]
- **Final Taxonomy**: `UNASSIGNED` [AGENT_INTERPRETATION: Awaiting creative interpretation]

### Physical Taxonomy & Acoustic Environment [SOURCE_METADATA]
- **Physical Taxonomy**: Action=`unspecified`, Exciter=`unspecified`, Resonator=`unspecified`, Surface=`unspecified`
- **Acoustic Environment**: `unspecified` (Reverb: `unspecified`)

---

## 9. Provenance, Audit Trails & Analysis Runs (12 runs)

- **phase2_ai_orchestrator** (`v1.0.0`) | Stage: `PHASE2_AI_ENRICHMENT` | Status: `SUCCESS` | Date: `2026-09-26 18:30:58`
- **phase2_ai_orchestrator** (`v1.0.0`) | Stage: `PHASE2_AI_ENRICHMENT` | Status: `SUCCESS` | Date: `2026-09-26 18:37:47`
- **deterministic_dsp_engine** (`v1.0.0`) | Stage: `MEASURED_AUDIO_FACTS` | Status: `SUCCESS` | Date: `2026-09-26 20:18:51`
- **phase2_ai_orchestrator** (`v1.0.0`) | Stage: `PHASE2_AI_ENRICHMENT` | Status: `SUCCESS` | Date: `2026-09-26 20:18:52`
- **deterministic_dsp_engine** (`v1.0.0`) | Stage: `MEASURED_AUDIO_FACTS` | Status: `SUCCESS` | Date: `2026-09-26 20:24:33`
- **phase2_ai_orchestrator** (`v1.0.0`) | Stage: `PHASE2_AI_ENRICHMENT` | Status: `SUCCESS` | Date: `2026-09-26 20:24:34`
- **deterministic_dsp_engine** (`v1.0.0`) | Stage: `MEASURED_AUDIO_FACTS` | Status: `SUCCESS` | Date: `2026-09-26 20:27:14`
- **phase2_ai_orchestrator** (`v1.0.0`) | Stage: `PHASE2_AI_ENRICHMENT` | Status: `SUCCESS` | Date: `2026-09-26 20:27:14`
- **deterministic_dsp_engine** (`v1.0.0`) | Stage: `MEASURED_AUDIO_FACTS` | Status: `SUCCESS` | Date: `2026-09-26 21:23:54`
- **phase2_ai_orchestrator** (`v1.0.0`) | Stage: `PHASE2_AI_ENRICHMENT` | Status: `SUCCESS` | Date: `2026-09-26 21:23:54`
- **deterministic_dsp_engine** (`v1.0.0`) | Stage: `MEASURED_AUDIO_FACTS` | Status: `SUCCESS` | Date: `2026-09-26 22:25:18`
- **phase2_ai_orchestrator** (`v1.0.0`) | Stage: `PHASE2_AI_ENRICHMENT` | Status: `SUCCESS` | Date: `2026-09-26 22:25:18`
