# Sonic Intelligence Canonical Inspection Report: Asset #68

**File Name**: `tavern_crowd_murmur.ogg`  
**Title**: tavern_crowd_murmur.ogg  
**Category**: `AMB` / `Tavern`  
**License / Source**:  (Royalty-Free)  
**Local Disk Status**: `LOCAL_DOWNLOADED`  

---

## 1. Agent Sound Card v3.0 (Active Production View)

### 🎵 Sound Card [ID: 68] tavern_crowd_murmur.ogg
- **File / Status [SOURCE_METADATA]**: `tavern_crowd_murmur.ogg` | LOCAL (Cached) | **Duration [MEASURED]**: 76.25s
- **Source [SOURCE_METADATA]**: SoundBank (Royalty-Free)
- **Taxonomy [SOURCE METADATA]**:
  - Category [SOURCE_METADATA]: `AMB` / `Tavern`
  - Physical [SOURCE_METADATA]: Exciter: `unspecified` | Resonator: `unspecified` | Action: `unspecified` | Surface: `unspecified`
  - Source Pack Mood [SOURCE_METADATA]: `unspecified`
- **Acoustics [MEASURED DSP]**:
  - Loudness [MEASURED]: -19.3 LUFS | True Peak [MEASURED]: -0.7 dBTP
  - Spectral [MEASURED]: Centroid 456 Hz (warm) | Dynamics [MEASURED]: `medium` (transient)
  - Speech Corridor Density (1kHz–4kHz) [MEASURED]: 0.25
- **Classifier Inferences [CLASSIFIER]**:
  - AudioSet [CLASSIFIER]: `vocal.speech` (conf: 0.87, rank #1), `foley.tableware.dishes` (conf: 0.14, rank #2), `foley.tableware.clink` (conf: 0.12, rank #3)
  - Vocal Speech Probability [CLASSIFIER]: 0.87
  - Classifier Mood Evidence [CLASSIFIER]: None
- **Semantic Embedding [CLAP]**:
  - Query Similarity [CLASSIFIER]: None
- **Directorial Decisions & Mix Safety [AGENT_INTERPRETATION]**:
  - Dramatic Role [AGENT_INTERPRETATION]: `UNASSIGNED [AWAITING_AGENT_EVALUATION]`
  - Scene Purpose [AGENT_INTERPRETATION]: `UNASSIGNED [AGENT_INTERPRETATION: Awaiting SoundDirector]`
  - Emotional Suitability [AGENT_INTERPRETATION]: `UNINTERPRETED [AWAITING_AGENT_EVALUATION]`
  - Voice-Masking Judgment [AGENT_INTERPRETATION]: `UNASSESSED (Speech Density: 0.25 [MEASURED], Vocal Presence: 0.87 [CLASSIFIER]) [AWAITING MIX AGENT]` (Whisper Compatibility: `NOT_CALIBRATED`)
  - Dialogue Ducking Amount [AGENT_INTERPRETATION]: `SCENE_DEPENDENT (Deferred to Track 11 Mix Director)`
  - Placement / Recommended Usage [AGENT_INTERPRETATION]: `UNASSIGNED [AGENT_INTERPRETATION: Awaiting SoundDirector]`
  - Final Taxonomy [AGENT_INTERPRETATION]: `UNASSIGNED [AGENT_INTERPRETATION: Awaiting creative interpretation]`
- **Temporal Structure**: Active Region: 0.00s - 60.00s [ANALYSIS WINDOW: First 60.0s analyzed of 76.25s total] | Window [0.00s - 10.00s] [OBSERVATION WINDOW]: vocal.speech (0.87) [CLASSIFIER INFERENCE] | Window [5.00s - 15.00s] [OBSERVATION WINDOW]: vocal.speech (0.82), music.instrumental (0.31) [CLASSIFIER INFERENCE] | ... and 13 more classifier observation windows | 5 transient onsets detected [MEASURED DSP]
- **Music & Tonal [MEASURED / SOURCE METADATA]**:
  - Tonal [MEASURED]: True (Pitch: 1500.0 Hz) [MEASURED DSP, autocorrelation peak > 0.55] | BPM [SOURCE_METADATA / MEASURED]: unavailable (unmeasured) | Key [SOURCE_METADATA]: unavailable (unmeasured) | Time Signature [SOURCE_METADATA]: unavailable (unmeasured)

- **Agent Creative Interpretation**: None [AGENT_INTERPRETATION: Asset unassigned in catalog; dramatic role, scene purpose, emotional suitability, and dialogue ducking evaluated per scene by SoundDirector / Mix Director]
- **Provenance & Quality**:
  - Metadata Completeness: 70% | Status: `full_phase2`
  - Provenance: DSP=`1.0.0`, AST=`AudioSet-527`, CLAP=`HTS-AT`
- **Retrieval Evidence**:
  - Direct asset lookup

---

## 2. Technical Audio Format & File Metadata

| Property | Value | Evidence / Method |
|---|---|---|
| **Duration** | `76.251s` | [MEASURED] Container Header Probing |
| **Container & Codec** | `ogg` / `vorbis` | [MEASURED] Audio Stream Probing |
| **Sample Rate** | `44100 Hz` | [MEASURED] Exact Sample Clock |
| **Channels** | `2 ch` (Stereo) | [MEASURED] Channel Map |
| **Bit Depth** | `N/A (Lossy Codec)` | [MEASURED] Bit Resolution |
| **Bitrate** | `206707 bps` | [MEASURED] Stream Average |
| **File Size** | `1970215 bytes` | [MEASURED] Disk File Size |

---

## 3. Measured DSP & Acoustic Facts (Sonic Genome Layer 1)

### Loudness & Dynamic Profiles [MEASURED DSP]
- **Integrated Loudness**: `-19.3 LUFS` (EBU R128)
- **True Peak**: `-0.7 dBTP`
- **Loudness Range (LRA)**: `6.4 LU`
- **RMS Level**: `-22.04 dBFS`
- **Peak Level**: `-0.75 dBFS`
- **Dynamic Range**: `21.29 dB`

### Spectral & Acoustic Fingerprint [MEASURED DSP]
- **Spectral Centroid**: `455.7 Hz` (**Brightness**: `warm`)
- **Spectral Bandwidth**: `827.5 Hz`
- **Spectral Rolloff (85%)**: `632.8 Hz`
- **Spectral Flatness**: `0.0014`
- **Zero Crossing Rate**: `0.0293`
- **Speech Corridor Density (1kHz - 4kHz)**: `0.25`
- **Vocal Clash Risk**: `LOW`

---

## 4. Temporal Structure & SED Active Intervals

- **Active Sound Region**: `0.00s - 60.00s [ANALYSIS WINDOW: First 60.0s analyzed of 76.25s total]`
- **Silence Ratio**: `0.001 [MEASURED DSP]`
- **Transient Pulse Count**: `23 detected peaks [MEASURED DSP]`
- **Energy Envelope Character**: `sustained [DERIVED DSP]`
- **Major Transient Onsets**: `[0.06, 2.18, 7.46, 7.72, 8.28, 9.22, 11.72, 11.86, 13.8, 14.7]`

### Detected Temporal Intervals & Active Windows (43 total)
- `[0.04s - 60.00s]` **Active Audio Region** [MEASURED DSP, Detector: `frame_energy_gate_v1`]
- `[0.00s - 10.00s]` **Classifier Observation Window**: `vocal.speech` (0.87) [CLASSIFIER INFERENCE]
- `[5.00s - 15.00s]` **Classifier Observation Window**: `vocal.speech` (0.82), `music.instrumental` (0.31), `foley.tableware.dishes` (0.21) [CLASSIFIER INFERENCE]
- `[10.00s - 20.00s]` **Classifier Observation Window**: `vocal.speech` (0.53), `foley.tableware.dishes` (0.39), `Cutlery, silverware` (0.28) [CLASSIFIER INFERENCE]
- `[15.00s - 25.00s]` **Classifier Observation Window**: `vocal.speech` (0.51), `foley.tableware.clink` (0.25), `music.instrumental` (0.23) [CLASSIFIER INFERENCE]
- `[20.00s - 30.00s]` **Classifier Observation Window**: `vocal.speech` (0.57), `music.instrumental` (0.26) [CLASSIFIER INFERENCE]
- `[25.00s - 35.00s]` **Classifier Observation Window**: `vocal.speech` (0.56), `foley.tableware.dishes` (0.50) [CLASSIFIER INFERENCE]
- *(... and 9 more classifier observation windows in JSON)*
- **Transient Onsets [MEASURED DSP]**: [`0.06s`, `2.18s`, `7.46s`, `7.72s`, `8.28s`]

---

## 5. Music & Tonal Intelligence [MEASURED / SOURCE METADATA]

- **Is Tonal**: True (Pitch: 1500.0 Hz) [MEASURED DSP, autocorrelation peak > 0.55]
- **BPM / Tempo**: unavailable (unmeasured)
- **Key / Tonality**: unavailable (unmeasured)
- **Time Signature**: unavailable (unmeasured)

---

## 6. AI Classifier Predictions (AST AudioSet 527) [CLASSIFIER INFERENCE]

| Rank | Normalized Label | Raw AudioSet Label | Confidence | Time Window |
|:---:|---|---|:---:|:---:|
| #1 | `vocal.speech` | Speech | **0.874** | 0.0s - 76.3s |
| #2 | `foley.tableware.dishes` | Dishes, pots, and pans | **0.139** | 0.0s - 76.3s |
| #3 | `foley.tableware.clink` | Chink, clink | **0.123** | 0.0s - 76.3s |
| #4 | `—` | Inside, public space | **0.102** | 0.0s - 76.3s |
| #5 | `—` | Chatter | **0.099** | 0.0s - 76.3s |
| #6 | `—` | Inside, large room or hall | **0.077** | 0.0s - 76.3s |
| #7 | `—` | Cutlery, silverware | **0.063** | 0.0s - 76.3s |
| #8 | `music.instrumental` | Music | **0.045** | 0.0s - 76.3s |
| #9 | `—` | Conversation | **0.029** | 0.0s - 76.3s |
| #10 | `—` | Female speech, woman speaking | **0.026** | 0.0s - 76.3s |

---

## 7. CLAP Semantic Vector Embedding (512-d Open-Vocabulary) [EMBEDDING]

- **Model**: `laion/clap-htsat-unfused` (Version: `2023_v1`)
- **Vector Dimensions**: 512-d (2048 bytes IEEE-754)
- **L2 Norm**: 1.0 (Unit norm verified: `True`)
- **Vector Sample (Head)**: `[0.04583, -0.05705, -0.00085, 0.03346, 0.09636]`

---

## 8. Psychoacoustics, Mix Evidence & Agent Directorial Guidelines

### Measurable Mix Evidence [MEASURED DSP & CLASSIFIER]
- **Speech Corridor Density (1kHz–4kHz)**: `0.25` [MEASURED DSP]
- **Classifier Vocal / Speech Presence**: `0.8737` [CLASSIFIER INFERENCE]

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

## 9. Provenance, Audit Trails & Analysis Runs (13 runs)

- **phase2_orchestrator** (`v1.0.0`) | Stage: `PHASE2_AI_ENRICHMENT` | Status: `FAILED` | Date: `2026-09-26 18:30:59`
- **phase2_ai_orchestrator** (`v1.0.0`) | Stage: `PHASE2_AI_ENRICHMENT` | Status: `SUCCESS` | Date: `2026-09-26 18:37:11`
- **phase2_ai_orchestrator** (`v1.0.0`) | Stage: `PHASE2_AI_ENRICHMENT` | Status: `SUCCESS` | Date: `2026-09-26 18:37:50`
- **deterministic_dsp_engine** (`v1.0.0`) | Stage: `MEASURED_AUDIO_FACTS` | Status: `SUCCESS` | Date: `2026-09-26 20:18:48`
- **phase2_ai_orchestrator** (`v1.0.0`) | Stage: `PHASE2_AI_ENRICHMENT` | Status: `SUCCESS` | Date: `2026-09-26 20:18:51`
- **deterministic_dsp_engine** (`v1.0.0`) | Stage: `MEASURED_AUDIO_FACTS` | Status: `SUCCESS` | Date: `2026-09-26 20:24:30`
- **phase2_ai_orchestrator** (`v1.0.0`) | Stage: `PHASE2_AI_ENRICHMENT` | Status: `SUCCESS` | Date: `2026-09-26 20:24:33`
- **deterministic_dsp_engine** (`v1.0.0`) | Stage: `MEASURED_AUDIO_FACTS` | Status: `SUCCESS` | Date: `2026-09-26 20:27:11`
- **phase2_ai_orchestrator** (`v1.0.0`) | Stage: `PHASE2_AI_ENRICHMENT` | Status: `SUCCESS` | Date: `2026-09-26 20:27:13`
- **deterministic_dsp_engine** (`v1.0.0`) | Stage: `MEASURED_AUDIO_FACTS` | Status: `SUCCESS` | Date: `2026-09-26 21:23:50`
- **phase2_ai_orchestrator** (`v1.0.0`) | Stage: `PHASE2_AI_ENRICHMENT` | Status: `SUCCESS` | Date: `2026-09-26 21:23:53`
- **deterministic_dsp_engine** (`v1.0.0`) | Stage: `MEASURED_AUDIO_FACTS` | Status: `SUCCESS` | Date: `2026-09-26 22:25:15`
- **phase2_ai_orchestrator** (`v1.0.0`) | Stage: `PHASE2_AI_ENRICHMENT` | Status: `SUCCESS` | Date: `2026-09-26 22:25:17`
