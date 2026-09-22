---
name: audio-engineer-ffmpeg
description: >-
  Hollywood-grade audio drama mixing, acoustic sound design, and FFmpeg mastering skill.
  Covers 5-track audio hierarchies (Vocals, BGM, Ambience Bed, Foley SFX, Master Out),
  dynamic sidechain compression (-16dB ducking), spectral carving (-5.5dB @ 2.2kHz),
  room impulse reverberation, self-healing FFmpeg filter_complex graphs, and broadcast EBU R128 (-19 LUFS) mastering.
  Use when designing audio graphs, mastering audiobooks, diagnosing FFmpeg errors, or mixing multitrack soundscapes.
---

# Audio Engineer & FFmpeg Mastering Skill

This skill governs professional audio drama mixing, Foley placement, and broadcast audio mastering adhering to GraphicAudio, BBC Radio 4 Drama, and Audible production standards.

---

## 1. 5-Track Audio Architecture

```
[0:a] Dialogue Bus    ──> Clean Speech ──> Split ──┬──> [voc_dry] ──┐
                                                    └──> [voc_sc]  ──┼──> Sidechain Trigger
[1:a] Musical Score   ──> Spectral Carve (-5.5dB @ 2.2kHz) ──────────┴──> [bgm_ducked] ──┐
[2:a] Ambience Bed    ──> Room Reverberation & Volume Leveled (0.12-0.20) ───────────────┼──> amix ──> EBU R128 ──> [out]
[3:a] Foley SFX Bus   ──> Diegetic Spatial Panning & Leveled (0.25-0.65) ────────────────┘
```

### Hierarchy Rules:
1. **Dialogue Primacy**: Dialogue must NEVER be buried. Always center-panned with dry, crisp intelligibility.
2. **Spectral Carving**: BGM must be carved around 2–3kHz (`equalizer=f=2200:t=q:w=1.5:g=-5.5`) so vocal consonants remain distinct.
3. **Dynamic Sidechain Ducking**: BGM ducks automatically when speech is active (`sidechaincompress=threshold=0.04:ratio=8.0:attack=120:release=750:knee=2.5`).
4. **Broadcast Loudness**: EBU R128 target `I=-19 LUFS`, `TP=-1.5 dBFS`, `LRA=11`.

---

## 2. Standard Multitrack Filter Graph Recipe

```ffmpeg
[0:a]asplit=2[voc_dry][voc_sc];
[1:a]aloop=loop=-1:size=2e+09,atrim=0:TOTAL_DUR,equalizer=f=2200:t=q:w=1.5:g=-5.5[bgm_carved];
[bgm_carved][voc_sc]sidechaincompress=threshold=0.04:ratio=8.0:attack=120:release=750:knee=2.5[bgm_ducked];
[2:a]aloop=loop=-1:size=2e+09,atrim=0:TOTAL_DUR,volume=0.14[amb_bed];
[3:a]volume=0.30[fol_bus];
[voc_dry][bgm_ducked][amb_bed][fol_bus]amix=inputs=4:duration=first:dropout_transition=2[mixed];
[mixed]aresample=osr=48000,loudnorm=I=-19:TP=-1.5:LRA=11,alimiter=limit=0.89:attack=5:release=50[out]
```

---

## 3. Dedicated Tools & Subagents

- **Subagent**: `audio-engineer` (invocable via `invoke_subagent`).
- **MCP Server**: `ffmpeg-audio` (configured in `mcp_config.json`):
  - `ffmpeg_probe`: Probes duration, channels, codec, bit rate.
  - `ffmpeg_test_filter_graph`: Dry-runs filter graphs on dummy audio to detect syntax errors before rendering.
  - `ffmpeg_sidechain_duck`: Direct sidechain ducking between dialogue and music.
  - `ffmpeg_render_master`: Multi-input mixdown with EBU R128 broadcast mastering.
- **Python Runtime Self-Healing**: `audiobook_factory.ffmpeg_agent` (`build_ffmpeg_filter_graph_via_agent`).
