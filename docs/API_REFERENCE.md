# 📚 API Reference: Data Contracts & Module Specifications

## Overview

The `audiobook_factory` package provides a strictly-typed, modular architecture powered by **Pydantic v2** models, clean separation of concerns, and zero hardcoded bindings. This document details the authoritative public contracts, engine classes, and core utility signatures.

---

## 📐 Data Contracts ([`audiobook_factory.contracts`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/contracts.py))

### 1. `CreativeManifest`
*The authoritative creative and acoustic blueprint for a chapter.*

```python
class CreativeManifest(BaseModel):
    manifest_version: str = "3.0"
    project_id: str = ""
    chapter_id: str
    silence_percentage: float = 100.0  # Mandate: Must be >= 60.0%
    mastering: MasteringConfig = MasteringConfig()
    ambience_scenes: List[AmbienceScene] = []
    music_cues: List[MusicCue] = []
    foley_cues: List[FoleyCue] = []
    total_duration_ms: Optional[int] = 0
    metadata: Dict[str, Any] = {}

    def validate_acoustic_rules(self, total_duration_ms: Optional[int] = None) -> None:
        """Enforces the >= 60.0% acoustic silence mandate against music cue durations."""

    def to_dict(self) -> Dict[str, Any]: ...
    def to_json(self, indent: int = 2) -> str: ...
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CreativeManifest: ...
    @classmethod
    def from_json(cls, json_str: str) -> CreativeManifest: ...
```

### 2. `ScreenplaySegment` & `ScreenplayScript`
*Atomic units of standardized screenplay dialogue, narration, and action.*

```python
class ScreenplaySegment(BaseModel):
    index: int                          # 1-indexed sequential segment number
    type: Literal["dialogue", "narration", "chapter_header", "action"]
    speaker: str = "Narrator"           # Canonical English character name or 'Foley'
    text: str = ""                      # Clean speech text or '[ACTION]' marker
    emotion: str = "neutral"            # Dramatic emotion category
    pause_after_ms: int = 400           # Silence buffer following line
    acting: ActingInstructions          # Delivery style & pacing
    spatial: SpatialCoordinates         # Stereo azimuth pan (-1.0 to +1.0) & proximity
    acoustic_env: str = "open_road"     # Scene IR preset
    sfx_cues: List[str] = []            # Associated physical Foley tags
    music: SegmentMusicParams           # Music atmosphere preferences
    intensity_level: Optional[str] = "medium"  # 'low', 'medium', 'high', 'explosive'
    pre_roll_breath_ms: Optional[int] = 0      # Breath intake Foley duration

class ScreenplayScript(BaseModel):
    segments: List[ScreenplaySegment] = []
    pronunciation_overrides: Dict[str, str] = {}

    @classmethod
    def from_file(cls, path: str | Path) -> ScreenplayScript: ...
```

### 3. `MusicCue` & `FoleyCue`
*Surgical musical score and tactile sound effect instructions.*

```python
class MusicCue(BaseModel):
    cue_id: str                         # e.g. 'mc_001'
    cue_type: MusicCueType              # 'EMOTIONAL_UNDERSCORE', 'CLIMACTIC_ACTION_CUE', etc.
    track_id: int = 0                   # Catalog asset identifier
    track_name: str                     # Asset filename or title
    section_name: str                   # 'INTRO_BED', 'CLIMAX_DROP', etc.
    section_start_sec: float = 0.0      # Offset inside source track
    start_ms: int                       # Offset on chapter timeline in ms
    duration_ms: int                    # Duration of cue in ms
    fade_in_ms: int = 2000
    fade_out_ms: int = 3000
    volume_db: float = -18.0
    leitmotif_ref: Optional[str] = ""   # Associated Sonic Bible motif ID
    spectral_notch_needed: bool = False # Flag for 2.2kHz vocal notch filter
    target_valence: Optional[float] = None
    target_arousal: Optional[float] = None

class FoleyCue(BaseModel):
    cue_id: str                         # e.g. 'fc_001'
    segment_index: int                  # Triggering dialogue segment index
    anchor_word: str                    # Dialogue word triggering the sound
    pre_roll_ms: int = 100              # Lead-in time in ms
    asset_id: int = 0
    asset_path: str = ""
    gain_dbfs: float = -15.0            # Calibrated peak target
    azimuth_pan: float = 0.0            # Panning [-0.8, +0.8]
    reverb_send: float = 0.15           # Send level to shared reverb
    start_ms: Optional[int] = 0
    duration_ms: Optional[int] = 0
```

### 4. `AmbienceScene` & `MasteringConfig`
*Continuous environmental background beds and broadcast mastering parameters.*

```python
class AmbienceScene(BaseModel):
    scene_id: int                       # Sequential scene index
    start_ms: int                       # Start offset on chapter timeline in ms
    end_ms: int                         # End offset on chapter timeline in ms
    asset_path: str                     # Filesystem path to ambient bed
    target_lufs: float = -32.0          # Calibrated background loudness in LUFS
    reverb_preset: str = "room"         # Convolution preset ('room', 'cathedral', etc.)

class MasteringConfig(BaseModel):
    target_lufs: float = -19.0          # Integrated loudness in LUFS
    true_peak_dbtp: float = -1.5        # True peak ceiling in dBTP
    ducking_attenuation_db: float = -7.5 # Attenuation gain while dialogue speaks
    ducking_attack_ms: int = 120        # Compressor attack time
    ducking_release_ms: int = 750       # Compressor release time
    spectral_carve_hz: int = 2200       # Center frequency for vocal notch filter
    spectral_carve_gain_db: float = -5.5
```

### 5. `TimelineSegment` & `TimelineLedger`
*Gate 4.5 sample-accurate transcript and millisecond timeline ledger.*

```python
class TimelineSegment(BaseModel):
    segment_index: int
    speaker: str
    text: str                           # Full unabridged speech transcript
    audio_file: str                     # Filename of synthesized WAV chunk
    duration_ms: int                    # Sample duration in ms
    start_ms: int                       # Timeline start offset in ms
    end_ms: int                         # Timeline end offset in ms
    pause_after_ms: int = 400
    emotion: str = "neutral"
    spatial_pan: float = 0.0
    acoustic_env: str = "temple_stone_hall"

class TimelineLedger(BaseModel):
    ledger_version: str = "2.0"
    project_id: str = ""
    chapter_id: str
    total_segments: int
    total_dialogue_duration_ms: int
    total_timeline_duration_ms: int
    total_silence_duration_ms: int
    silence_percentage: float
    segments: List[TimelineSegment] = []

    def get_segment(self, index: int) -> Optional[TimelineSegment]: ...
    def find_segment_at_ms(self, timestamp_ms: int) -> Optional[TimelineSegment]: ...
    @classmethod
    def from_file(cls, path: str | Path) -> TimelineLedger: ...
```

### 6. `BookMasterManifest` & Macro Contracts
*Macro-tier book-level contracts aggregating voice roster, lore bible, TOC, and packaging.*

```python
class BookMasterManifest(BaseModel):
    title: str
    author: str
    narrator: str = "Charon"
    translator_credits: Optional[str] = None
    series_title: Optional[str] = None
    book_number: Optional[int] = None
    total_duration_ms: int = 0
    global_integrated_lufs: float = -19.0
    voice_roster: BookVoiceRoster = BookVoiceRoster()
    lore_bible: GlobalLoreBible = GlobalLoreBible()
    toc: BookTableOfContents = BookTableOfContents()
    packaging_specs: BookPackagingSpecs = BookPackagingSpecs()

    @classmethod
    def from_file(cls, path: str | Path) -> BookMasterManifest: ...
```

---

## 🏛️ Core Engine Classes

### `PipelineOrchestrator` ([`audiobook_factory.orchestrator`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/orchestrator.py))
*Coordinates the complete autonomous novel production lifecycle.*

```python
class PipelineOrchestrator:
    def __init__(self, projects_dir: Path): ...

    def run_autonomous_pipeline(
        self,
        input_file: Path,
        hindi: bool = True,
        dramatized: bool = True,
        voice: str = "Aoede",
        cover_image: Optional[Path] = None,
        workers: int = 3,
        duck_db: float = -16.0,
        spatial_staging: bool = False,
    ) -> Path:
        """Runs the 6-stage autonomous novel production pipeline, returning path to final M4B."""

    def produce_chapter(
        self,
        project_dir: Path,
        chapter_num: int,
        voice: str = "Aoede",
        workers: int = 3,
        duck_db: float = -16.0,
        spatial_staging: bool = False,
    ) -> Dict[str, Any]:
        """Produces a single cinematic chapter with stems, timeline ledger, and quality checks."""
```

### `UniversalExtractor` ([`audiobook_factory.extractor`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/extractor.py))
*Zero-dependency multi-format document parser.*

```python
def process_book_file(input_file: Path, output_projects_dir: Path) -> Dict[str, Any]:
    """Ingests EPUB, PDF, TXT, or MD, creates a project folder, and extracts structured chapters."""

def extract_chapters(text: str) -> List[Dict[str, Any]]:
    """Detects semantic chapter breaks, Roman numerals, and headings."""

def split_large_chapter_on_semantic_boundary(
    chapter_text: str, max_chars: int = 45000
) -> List[str]:
    """Splits oversized chapters along paragraph boundaries to avoid LLM context overflow."""
```

### `LiteraryTranslator` ([`audiobook_factory.translator`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/translator.py))
*Two-pass literary Hindustani translation engine with glossary synchronization.*

```python
def translate_book_project(
    project_dir: Path,
    model: str = "gemini-flash-latest",
    target_lang: str = "hi",
) -> Path:
    """Translates all extracted chapters in a project, maintaining consistent terminology."""

def normalize_translated_lexicon(text: str, glossary: Dict[str, str]) -> str:
    """Applies canonical proper noun substitutions to translated text."""
```

### `ScriptBuilder` ([`audiobook_factory.script_builder`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/script_builder.py))
*Sliding-window dialogue parsing and character attribution engine.*

```python
def generate_project_scripts(
    project_dir: Path,
    use_hindi: bool = False,
    dramatized: bool = True,
) -> Path:
    """Generates standardized screenplay JSON for all chapters."""

def build_dramatized_script_llm(
    text: str,
    chapter_title: str,
    character_roster: CharacterRoster,
    project_dir: Path,
) -> List[Dict[str, Any]]:
    """Extracts speaker tags, emotions, delivery styles, and spatial pan coordinates."""
```

### `TTSDispatcher` ([`audiobook_factory.tts_dispatcher`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/tts_dispatcher.py))
*Token-Bucket concurrent speech synthesizer with automatic failover.*

```python
class TTSDispatcher:
    def __init__(
        self,
        project_dir: Path,
        default_backend: str = "gemini_tts",
        default_voice: str = "Aoede",
        max_workers: int = 3,
    ): ...

    def synthesize_chapter_script(
        self,
        script_file: Path,
        chapter_idx: int,
    ) -> List[Path]:
        """Synthesizes all segments in a chapter script with token-bucket rate limiting."""

def probe_key_health(api_key: str) -> bool:
    """Verifies API key validity and active quota with Google AI Studio."""
```

### `AgentDirector` ([`audiobook_factory.agent_director`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/agent_director.py))
*Autonomous dramaturgy and acoustic soundscape director.*

```python
class AgentDirector:
    def __init__(self, project_dir: Path): ...

    def direct_chapter_manifest(
        self,
        chapter_id: str,
        script_segments: List[Dict[str, Any]],
        segment_durations_sec: Dict[int, float],
        dialogue_stem_path: Optional[Path] = None,
        timeline_ledger: Optional[TimelineLedger] = None,
        project_dir: Optional[Path] = None,
        sonic_bible: Optional[SonicBible] = None,
    ) -> CreativeManifest:
        """Executes 3-pass dramaturgy (silence carving, FTS5 music matching, foley mining)."""
```

### `SonicBible` ([`audiobook_factory.sonic_bible`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/sonic_bible.py))
*Project-level soundscape and leitmotif registry.*

```python
class SonicBible:
    def __init__(self, book_title: str = "", project_id: str = ""): ...

    def register_leitmotif(self, leitmotif: LeitmotifDefinition) -> None:
        """Registers a recurring musical theme for a character, location, or artifact."""

    def get_leitmotif_for_character(self, character_name: str) -> Optional[LeitmotifDefinition]: ...
    def save_to_disk(self, filepath: Path) -> None: ...
    @classmethod
    def load_from_disk(cls, filepath: Path) -> SonicBible: ...
```

### `SoundBank` ([`audiobook_factory.sound_bank`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/sound_bank.py))
*High-performance SQLite FTS5 audio warehouse.*

```python
class SoundBank:
    def __init__(self, db_path: Optional[Path] = None, bank_root: Optional[Path] = None): ...

    def search_sounds(
        self,
        query: str,
        category: Optional[str] = None,
        mood: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Executes Full-Text Search against the sound catalog with BM25 ranking."""

    def scan_and_index_directory(self, asset_dir: Path) -> int:
        """Scans folder and commits metadata for all valid audio assets."""

    def get_stats(self) -> Dict[str, Any]:
        """Returns track counts, durations, and category distribution."""
```

### `UniversalSoundBankIngester` ([`audiobook_factory.sound_bank_ingest`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/sound_bank_ingest.py))
*Multi-threaded batch audio ingestion pipeline.*

```python
class UniversalSoundBankIngester:
    def __init__(self, sound_bank: SoundBank, num_workers: int = 4): ...

    def ingest_directory(
        self,
        directory_path: Path,
        recursive: bool = True,
    ) -> Dict[str, Any]:
        """Probes, extracts acoustic metadata, and indexes all audio files concurrently."""
```

### `CinemaAudioEngine` ([`audiobook_factory.cinema_audio_engine`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/cinema_audio_engine.py))
*Film-standard discrete stem renderer and packaging ledger.*

```python
def render_discrete_stems(
    manifest: CinemaAudioManifest,
    dialogue_wav: Path,
    output_dir: Path,
    sound_bank: Optional[SoundBank] = None,
    ffmpeg: Optional[str] = None,
) -> StemLedger:
    """Renders 5 discrete DME stems (DX, MX, FX, AMB, ME) and final broadcast master."""
```

### `ManifestRenderer` ([`audiobook_factory.manifest_renderer`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/manifest_renderer.py))
*Dynamic FFmpeg `filter_complex` compiler.*

```python
def render_manifest_soundscape(
    manifest: CreativeManifest,
    vocal_track_path: Path,
    output_master_file: Path,
    sound_bank: Optional[SoundBank] = None,
) -> Path:
    """Assembles and executes multitrack audio graph with ducking and reverb."""

def get_reverb_filter_string(preset: str = "room") -> Tuple[str, float]:
    """Generates FFmpeg aecho parameters and wet mix gain for scene presets."""
```

### `Mastering` ([`audiobook_factory.mastering`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/mastering.py))
*Vocal DSP processing and EBU R128 loudness normalization.*

```python
def concatenate_and_master_chapter(
    audio_segments: List[Path],
    output_chapter_file: Path,
    pause_ms: int = 400,
    loudnorm: bool = True,
    target_lufs: float = -19.0,
    true_peak_db: float = -1.5,
    loudness_range: float = 11.0,
    target_sample_rate: int = 48000,
    script_segments: Optional[List[Dict[str, Any]]] = None,
    spatial_staging: bool = False,
) -> Path:
    """Concatenates speech WAVs, applies 5-stage DSP chain, and normalizes loudness."""
```

### `Packager` ([`audiobook_factory.packager`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/packager.py))
*M4B container packaging with chapter metadata and artwork.*

```python
def package_m4b_audiobook(
    project_dir: Path,
    cover_image: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    enforce_gate6: bool = False,
) -> Path:
    """Generates FFMETADATA1 file and packages all mastered chapters into deliverable M4B."""
```

---

## 🛡️ Quality Gate Auditor ([`audiobook_factory.gate_auditor`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/gate_auditor.py))

```python
# Result Contract
class AuditResult(BaseModel):
    gate_name: str
    passed: bool
    score: float = 1.0
    errors: List[str] = []
    warnings: List[str] = []
    details: Dict[str, Any] = {}

class GateAuditError(Exception):
    """Raised when an unrecoverable gate constraint is violated."""

# Gate 0: Translation Coverage
def audit_gate0_translation(extracted_file: Path, translation_file: Path) -> Dict[str, Any]: ...

# Gate 1: Voice Collision Elimination
def audit_gate1_roster(roster_file: Union[Path, Dict], registry_file: Union[Path, Dict]) -> Dict[str, Any]: ...

# Gate 2: Screenplay Scripting Schema
def audit_gate2_script(script_file: Path) -> Dict[str, Any]: ...

# Gate 3.5: Acoustic Pre-Flight Feasibility
def audit_gate3_5_acoustic_feasibility(manifest: CreativeManifest, sound_bank: Optional[SoundBank] = None) -> AuditResult: ...

# Gate 5: Broadcast EBU R128 Master
def audit_gate5_master(master_file: Path, target_lufs: float = -19.0) -> Dict[str, Any]: ...

# Gate 5.2: Spectral Masking (DMR)
def audit_gate5_2_spectral_masking(dialogue_stem: Path, music_stem: Path, min_dmr_db: float = 12.0) -> AuditResult: ...

# Gate 5.3: Stereo Phase Correlation
def audit_gate5_3_stereo_phase(audio_file: Path, min_phase_correlation: float = 0.20) -> AuditResult: ...

# Gate 6A: Voice Continuity Across Chapters
def audit_gate6a_voice_continuity(project_dir: Path) -> AuditResult: ...

# Gate 6B: Inter-Chapter Loudness Continuity
def audit_gate6b_loudness_continuity(chapter_files: List[Path], strict: bool = False) -> AuditResult: ...

# Gate 6C: Table of Contents Monotonicity
def audit_gate6c_toc_monotonicity(chapter_files_or_project_dir: Any, toc: Optional[BookTableOfContents] = None) -> AuditResult: ...

# Gate 6D: Container Packaging Specifications
def audit_gate6d_packaging_specs(cover_image: Optional[Path], specs: Optional[BookPackagingSpecs] = None) -> AuditResult: ...

# Multi-Gate Macro Audits
def audit_chapter_gates(project_dir: Path, chapter_num: int) -> Dict[str, Any]: ...
def audit_book_master(project_dir: Path, strict: bool = False) -> Dict[str, Any]: ...
```
