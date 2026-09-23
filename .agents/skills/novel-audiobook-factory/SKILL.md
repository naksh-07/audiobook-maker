---
name: novel-audiobook-factory
description: >-
  Autonomous end-to-end studio audiobook production engine. Ingests any EPUB, PDF, TXT or Markdown novel,
  extracts chapters, translates into literary dramatic Hindustani (optional), builds full-cast screenplay
  with sliding-window dialogue attribution, synthesizes audio via Google Gemini 3.1 Flash TTS (token-bucket
  concurrent pool), applies SQLite FTS5 Sound Bank ambience and -16dB dynamic sidechain ducking, masters vocals
  to EBU R128 (-19 LUFS), and packages a chaptered M4B container with cover art in one autonomous run.
  Activate whenever the user provides a book/novel file path and requests an audiobook.
---

# Novel Audiobook Factory Skill

This skill governs autonomous, studio-grade audiobook production on the high-performance PC workstation. It converts full-length novels (50,000–100,000+ words) into multi-cast, cinematic M4B audiobooks with zero manual editing.

---

## 1. Zero-Friction One-Command Invocation

Whenever the user provides an input book file (`.epub`, `.pdf`, `.txt`, `.md`) and asks to produce an audiobook:

```bash
# In c:\Users\Suraj\Documents\Antigravity\Audiobook:
python audiobook_cli.py auto "C:/path/to/novel.epub" --hindi --dramatized --voice Aoede --workers 3
```

### Command Flags:
- `file`: Path to the input novel (`.epub` strongly preferred; `.pdf` parsed via Gemini multimodal document API).
- `--hindi`: Translates English prose into dramatic, spoken Hindustani using Two-Pass Glossary Memory (*Aap/Tum/Tu* honorific hierarchy). Omit for original language.
- `--dramatized`: Multi-voice character attribution mode using sliding-window chunking (no truncation).
- `--voice`: Lead narrator voice persona (`Aoede` female narrative, `Charon` deep male narrative).
- `--workers`: Number of concurrent TTS synthesis workers (default: `3`, tuned for 15 RPM free tier).
- `--cover`: Optional path to cover art image (`.jpg` / `.png`) to embed in the M4B container.

---

## 2. Core Architecture Pipeline

```mermaid
flowchart TD
    A["Input File (.epub / .pdf)"] --> B["Stage 1: Document Extractor<br/>(audiobook_factory.extractor)"]
    B --> C["Stage 2: Literary Hindi Translation<br/>(audiobook_factory.translator)"]
    C --> D["Stage 3: Sliding-Window Screenplay Attribution<br/>(audiobook_factory.script_builder)"]
    D --> E["Stage 4: Deep Foley & Acoustic Miner<br/>(audiobook_factory.foley_miner)"]
    D --> F["Stage 5: Multi-Cast TTS Dispatcher<br/>(audiobook_factory.tts_dispatcher)"]
    E & F --> G["Stage 6: 5-Track FFmpeg Timeline Compositor<br/>(audiobook_factory.soundscape)"]
    G --> H["Stage 7: Broadcast Mastering & M4B Container<br/>(audiobook_factory.packager)"]
```

### Stage 1: Document Ingestion ([`extractor.py`](file:///C:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/extractor.py))
- **EPUB**: Traverses `.opf` spine and table of contents with zero external pip dependencies.
- **PDF**: Uses Gemini multimodal vision API to digitize clean Markdown, automatically stripping running headers and footers.

### Stage 2: Sense-for-Sense Translation ([`translator.py`](file:///C:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/translator.py))
- **Pass 1**: Extracts persistent character glossary (`translation/glossary.json`) defining Hindi spellings and honorific relationships (*Aap/Tum/Tu*).
- **Pass 2**: Sense-for-sense dramatic Hindustani translation suitable for spoken audio drama.

### Stage 3: Screenplay Attribution ([`script_builder.py`](file:///C:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/script_builder.py))
- **Sliding-Window Parsing**: Chunks chapters into 1,200-word blocks with rolling context. Eliminates text truncation for long chapters.
- **Multi-Cast Speaker Attribution**: Attributes character dialogue vs narrator, removes redundant speech tags, tags acting emotions (`whispering`, `growl`, `calm_raspy`, `angry`).

### Stage 4: Autonomous Directing Layer ([`agent_director.py`](file:///C:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/agent_director.py))
- **3-Pass Dramaturgy & Multi-Scene Partitioning (ADR-018 & ADR-022)**:
  - *Pass 1*: Carves acoustic silence ($\ge 60\%$).
  - *Pass 1.5*: Partitions chapters dynamically into distinct scene blocks based on `acoustic_env` shifts (`_partition_script_ambience_scenes`).
  - *Pass 2*: Queries FTS5 sound bank for scene-bound BGM underscore with `until_segment` duration calculation.
  - *Pass 3*: Mines physical Foley interactions using `BILINGUAL_ANCHOR_MAP` without the 50% dead-center trap, strictly enforcing `DOMETabl` tableware isolation.
  - Emits the authoritative Pydantic v2 `CreativeManifest`.

### Stage 5: Concurrent Multi-Cast TTS ([`tts_dispatcher.py`](file:///C:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/tts_dispatcher.py))
- **Engine**: Google Gemini 3.1 Flash TTS (`gemini-3.1-flash-tts-preview`) generating 24kHz raw PCM.
- **Multi-Cast Persona Routing**: Dynamically maps characters to distinct voices (`Charon` for Geralt, `Aoede` for Narrator, `Puck` for Dandelion/Guards, `Fenrir` for Kings/Nobles, `Kore` for Sorceresses).
- **Rate-Limiter & Key Pool**: Rotates across 80+ keys with `TokenBucketRateLimiter` and single-worker human cadence.

### Stage 6: 5-Track FFmpeg Timeline Compositor ([`soundscape.py`](file:///C:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/soundscape.py))
- **Track 1 (Voice Bus)**: Multi-speaker dialogue with subtle room impulse reverberation (`aecho`).
- **Track 2 (Foley Bus)**: Micro-timed physical object audio placed via FFmpeg `adelay`.
- **Track 3 (Ambience Bus)**: Environmental room tone and weather from CC0 Sound Bank.
- **Track 4 (Music Bus)**: Cinematic score with 1.2kHz–3.2kHz spectral carving (`equalizer=f=2200:t=q:w=1.5:g=-5.5`) and -16dB dynamic lookahead sidechain ducking.
- **Master Bus**: EBU R128 (-19 LUFS) broadcast loudness normalization at 48kHz.

### Stage 7: Broadcast Packaging ([`packager.py`](file:///C:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/packager.py))
- **Single-Pass Stream Copy**: Concat demuxer streams directly to `.m4b` container with embedded chapter metadata and cover art.

---

## 3. Voice Persona Guide (Gemini 3.1 Flash TTS)

| Persona Name | Gender | Vocal Profile & Character Casting |
| :--- | :--- | :--- |
| **Aoede** | Female | Expressive, warm, highly melodious narrative lead. Perfect for classic literature, drama, and main storytelling. |
| **Charon** | Male | Deep, commanding, resonant baritone. Ideal for authoritative male narrators, villains, mentors, and dark fantasy. |
| **Kore** | Female | Soft, gentle, friendly, youthful female dialogue. |
| **Puck** | Male | Energetic, dynamic, conversational young male voice. |
| **Fenrir** | Male | Rugged, powerful, booming warrior/action character. |
| **Zephyr** | Female | Calm, ethereal, whisper-soft atmosphere narrator. |

---

## 4. Monitoring & Recovery Protocols

### Inspecting Production Progress via SQLite:
```python
from pathlib import Path
from audiobook_factory.state import ProjectStateLedger

ledger = ProjectStateLedger(Path("audiobooks/projects/<book_slug>"))
print(ledger.get_progress())
# Output: {'total_segments': 1420, 'completed': 890, 'progress_percent': 62.7, 'total_duration_min': 94.5}
```

### Resuming Interrupted Jobs:
If network drops or the PC reboots mid-synthesis, rerun the exact same command:
```bash
python audiobook_cli.py auto "C:/path/to/novel.epub" --hindi --dramatized
```
The pipeline automatically skips completed segments in under 5ms, re-attaching immediately to the first pending segment. Zero duplicated API calls, zero lost tokens.
