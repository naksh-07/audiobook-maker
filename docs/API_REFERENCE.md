# 📚 API Reference: Data Contracts & Module Specifications

## Overview

The `audiobook_factory` package provides a strictly-typed, modular architecture powered by **Pydantic v2** models, clean separation of concerns, and zero hardcoded bindings. This document details the authoritative public contracts, engine classes, and core utility signatures.

---

## 📐 Data Contracts ([`audiobook_factory.contracts`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/contracts.py))

### 1. `ProjectConfig` & `CharacterProfile`
*Project setup, adult literary fidelity configuration, and character sociolect profiles.*

```python
class ProjectConfig(BaseModel):
    project_id: str                     # Unique identifier for the project
    title: str                          # Book/Project title
    author: str                         # Author name
    source_language: str                # Source text language code (e.g. 'en', 'hi')
    target_language: str = "hi-IN"      # Target TTS/audiobook language code
    assets_dir: str                     # Root directory path for all project media assets
    ebu_r128_lufs: float = -19.0        # EBU R128 integrated loudness target in LUFS
    true_peak_db: float = -1.5          # Maximum allowable True Peak in dBTP
    adult_literary_mode: bool = Field(
        default=True,
        description="Enables unfiltered Gangs-of-Wasseypur / Manto grade raw adult literary fidelity"
    )

class CharacterProfile(BaseModel):
    character_uuid: str                 # Unique UUID for character persona
    display_name: str                   # Display name of character in screenplay
    gender: str                         # Gender identifier ('male', 'female', 'neutral')
    assigned_voice_id: str              # Voice model identifier ('Charon', 'Aoede', 'Puck', etc.)
    pitch_shift: float = 0.0            # Pitch shift in semitones
    speed_multiplier: float = 1.0       # Speech rate multiplier (0.5 to 2.0)
    sociolect_trait: Optional[str] = Field(
        default=None,
        description="Subtle Desi sociolect trait (e.g. 'COLD_CYNIC', 'CAUSTIC_ARISTOCRAT', 'THARKI_BARD')"
    )

class CharacterRoster(BaseModel):
    project_id: str                     # Associated project identifier
    characters: List[CharacterProfile] = []
    pronunciation_overrides: Dict[str, str] = {}
```

### 2. `CreativeManifest`
*The authoritative creative and acoustic blueprint for a chapter.*

```python
class CreativeManifest(BaseModel):
    manifest_version: str = "3.0"
    project_id: str = ""
    chapter_id: str
    silence_percentage: float = 100.0  # Mandate: Must be >= 60.0%
    mastering: MasteringConfig = MasteringConfig()
    ambience_scenes: List[AmbienceScene] = []
    scene_acoustics: Optional[Any] = None  # Decoupled 4-stem SceneSoundscapeManifest
    music_cues: List[MusicCue] = []
    foley_cues: List[FoleyCue] = []
    total_duration_ms: Optional[int] = 0
    metadata: Dict[str, Any] = {}

    def validate_acoustic_rules(self, total_duration_ms: Optional[int] = None) -> None:
        """Enforces the >= 60.0% acoustic silence mandate against music cue durations."""

    @model_validator(mode="after")
    def parse_scene_acoustics(self) -> "CreativeManifest":
        """Rehydrates raw scene_acoustics dictionary into typed SceneSoundscapeManifest upon JSON load."""

    def to_dict(self) -> Dict[str, Any]: ...
    def to_json(self, indent: int = 2) -> str: ...
    def save_to_file(self, path: Union[str, Path]) -> None:
        """Serialize and save manifest directly to JSON file."""
    @classmethod
    def from_file(cls, path: Union[str, Path]) -> CreativeManifest:
        """Load and deserialize manifest directly from JSON file."""
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CreativeManifest: ...
    @classmethod
    def from_json(cls, json_str: str) -> CreativeManifest: ...
```

### 3. `ScreenplaySegment` & `ScreenplayScript`
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
    memory_vocal_constraint: Optional[str] = None  # Conservative physical vocal constraint (e.g. 'strained_breath')
    recommended_pronoun: Optional[str] = None      # Recommended Hindi pronoun from RelationshipState ('tu', 'tum', 'aap')
    recommended_register: Optional[str] = None     # Recommended socio-linguistic register from RelationshipState

class ScreenplayScript(BaseModel):
    segments: List[ScreenplaySegment] = []
    pronunciation_overrides: Dict[str, str] = {}

    @classmethod
    def from_file(cls, path: str | Path) -> ScreenplayScript: ...
```

### 4. `MusicCue` & `FoleyCue`
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
    until_segment: Optional[int] = None # Segment boundary where cue terminates (ADR-022)
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
    ucs_category: Optional[str] = "MISCGnl" # Universal Category System (UCS) Category ID
    is_lfe_sub_drop: bool = False       # Triggers 50Hz sub-bass physical impact weight
    trajectory: str = "static"          # 'static', 'left_to_right', 'right_to_left', 'center_zoom'
```

### 5. `AmbienceScene` & `MasteringConfig`
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

### 6. `SceneSoundscapeManifest`, `SceneAcousticProfile` & `AmbienceLayer`
*Decoupled 4-stem scene acoustics, spatial barrier occlusion, and stochastic spot transient configuration.*

```python
class AmbienceLayer(BaseModel):
    layer_type: Literal["base_room_tone", "weather_elements", "crowd_wallah", "spot_stochastic"]
    asset_path: str                     # Asset filename or path in sound bank
    target_lufs: float = -32.0          # Loudness target (-60.0 to -15.0 LUFS)
    stereo_width: float = 1.0           # Stereo spread factor (1.0 = native stereo)
    azimuth_pan: float = 0.0            # Spatial pan coordinate (-1.0 to +1.0)
    high_pass_hz: Optional[int] = None  # Low-cut filter frequency in Hz
    low_pass_hz: Optional[int] = None   # High-cut distance damping frequency in Hz
    loop: bool = True                   # Seamlessly loop across scene
    stochastic_interval_sec: Optional[float] = None # Period for spot triggers (e.g. 35.0s)

class SceneAcousticProfile(BaseModel):
    scene_id: str                       # e.g. 'sc_001_great_hall'
    act_index: int = 1                  # Dramatic act grouping
    start_ms: int = 0                   # Timeline start in ms
    end_ms: int = 0                     # Timeline end in ms
    environment_id: str = "default"     # WorldAcousticProfile ID
    ir_preset: str = "room"             # Reverberation impulse response preset
    layers: List[AmbienceLayer] = []    # Up to 4 decoupled ambient stems
    transition_in: Literal["cut", "crossfade", "fade_from_silence"] = "crossfade"
    transition_out: Literal["cut", "crossfade", "fade_to_silence"] = "crossfade"
    crossfade_ms: int = 2500            # Crossfade duration in ms
    occlusion_cutoff_hz: int = 18000    # Low-pass barrier occlusion frequency (e.g. 1400Hz indoor)

class SceneSoundscapeManifest(BaseModel):
    schema_version: str = "2.0"
    chapter_id: str
    scenes: List[SceneAcousticProfile] = []
    metadata: Dict[str, Any] = {}

    def add_scene(self, scene: SceneAcousticProfile) -> None: ...
    def save_to_disk(self, target_path: Union[str, Path]) -> Path: ...
    @classmethod
    def load_from_disk(cls, source_path: Union[str, Path]) -> SceneSoundscapeManifest: ...
    def audit_scene_acoustics_integrity(self, sound_bank: Optional[Any] = None) -> Dict[str, Any]: ...
    def generate_stochastic_cues(
        self,
        timeline_ledger: Optional[Any] = None,
        sound_bank: Optional[Any] = None,
        seed: int = 42,
    ) -> List[Any]:
        """Procedurally places Layer 4 stochastic spot transients in pause gaps (>= 600ms)."""
```

### 7. `TimelineSegment` & `TimelineLedger`
*Gate 4.5 sample-accurate transcript and millisecond timeline ledger.*

```python
class TimelineSegment(BaseModel):
    segment_index: int
    speaker: str
    text: str                           # Full unabridged speech transcript
    audio_file: str                     # Filename of synthesized WAV chunk
    duration_ms: int                    # Sample duration in ms
    start_ms: int                       # Timeline start offset in ms (curr_t + pre_breath)
    end_ms: int                         # Timeline end offset in ms
    pause_after_ms: int = 400
    emotion: str = "neutral"
    spatial_pan: float = 0.0
    acoustic_env: str = "temple_stone_hall"
    sfx_cues: List[str] = []            # Associated physical Foley tags
    music_mood: str = "neutral"         # Underlying musical mood
    pre_roll_breath_ms: int = 0         # Organic breath intake duration (ADR-022)

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

### 8. `BookMasterManifest` & Macro Contracts
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
        adult_literary_mode: bool = True,
    ) -> Path:
        """
        Runs the 6-stage autonomous novel production pipeline, returning path to final M4B.

        Parameters:
            input_file: Path to input novel file (.epub, .pdf, .txt, .md).
            hindi: Whether to translate text into literary Hindustani (default: True).
            dramatized: Enables multi-cast dialogue attribution and soundscape staging (default: True).
            voice: Lead narrator voice identifier (default: "Aoede").
            cover_image: Optional path to JPEG/PNG cover artwork for M4B packaging.
            workers: Max concurrent synthesis threads for token-bucket pool (default: 3).
            duck_db: Dynamic music sidechain ducking attenuation in dB (default: -16.0).
            spatial_staging: Enables stereo azimuth panning across character cast (default: False).
            adult_literary_mode: bool = True: Enables unfiltered Gangs-of-Wasseypur / Manto grade
                raw adult literary fidelity, 70/30 Anti-Parody Invariant, HBO somatic erotica,
                Cynical Protagonist Grunt Engine, and ASMR intimate close proximity staging.
        """

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
*Multi-format document parser with native pypdf digital parsing and Gemini multimodal fallback.*

```python
def process_book_file(input_file: Path, output_projects_dir: Path) -> Dict[str, Any]:
    """Ingests EPUB, PDF, TXT, or MD, creates a project folder, and extracts structured chapters."""

def extract_gemini_pdf(file_path: Path, api_key: str | None = None) -> str:
    """Extracts text using local fast pypdf (zero-quota, instant) with fallback to Gemini multimodal document API."""

def extract_chapters(text: str) -> List[Dict[str, Any]]:
    """Detects semantic chapter breaks, Roman numerals, and headings."""

def split_large_chapter_on_semantic_boundary(
    chapter_text: str, max_chars: int = 45000
) -> List[str]:
    """Splits oversized chapters along paragraph boundaries to avoid LLM context overflow."""
```

### `LiteraryTranslator` ([`audiobook_factory.translator`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/translator.py))
*Two-pass literary Hindustani translation engine with glossary synchronization and rolling narrative context.*

```python
def translate_book_project(
    project_dir: Path,
    model: str = "gemini-flash-latest",
    target_lang: str = "hi",
) -> Path:
    """Translates all extracted chapters in a project, threading 250-word rolling context across chapter boundaries."""

def translate_chapter(
    chapter_text: str,
    glossary: Optional[Dict[str, str]] = None,
    chapter_num: int = 1,
    preceding_summary: str = "",
    model: str = "gemini-flash-latest",
) -> str:
    """Translates a chapter in chunks, enforcing canonical lexicon normalization."""

def normalize_translated_lexicon(text: str, glossary: Dict[str, str]) -> str:
    """Applies canonical proper noun substitutions to translated text based on project glossary."""
```

### `LinguisticSanitizer` ([`audiobook_factory.sanitizer`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/sanitizer.py))
*Defense-in-depth linguistic guardrail, TTS vocal tag validator, and profanity preservation engine.*

```python
SUPPORTED_TTS_TAG_PATTERNS: List[str] = [
    r"whispers?", r"shouting", r"shouts?", r"sighs?", r"gasp", r"laughs?",
    r"giggles?", r"crying", r"trembling(?:\s+voice)?", r"cold\s+menace",
    r"intimate(?:,\s*breathy)?", r"growl", r"groan", r"spits?",
    r"bellowing\s+rage", r"breathless[\s_]+exhaustion", r"mocking\s+chuckle", ...
]

def validate_and_sanitize_translation(
    text: str,
    is_hindi: bool = True,
) -> Tuple[bool, str, str]:
    """
    Validates Devanagari purity, strips LLM meta-chatter/markdown fences,
    and guarantees 100% preservation of raw adult profanity and somatic erotica vocabulary.
    Returns: (is_valid: bool, cleaned_text: str, failure_reason: str).
    """

def sanitize_screenplay_segment(
    segment: Dict[str, Any],
    is_hindi: bool = True,
) -> Optional[Dict[str, Any]]:
    """
    Sanitizes screenplay segment text, selectively preserving permitted Gemini TTS neural
    vocal tags ([whispers], [growl], [spits], etc.) while stripping leaked non-vocal stage directions.
    Returns None if segment contains LLM refusal or conversational meta-commentary.
    """
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
*Token-Bucket concurrent speech synthesizer, multimodal audio director, and zero-voice-drift orchestrator.*  
*(See comprehensive technical manuals: [`docs/GEMINI_TTS_SYNTHESIS_AND_DIRECTING.md`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/docs/GEMINI_TTS_SYNTHESIS_AND_DIRECTING.md) and [`docs/VOICE_CASTING_DIRECTOR_GUIDE.md`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/docs/VOICE_CASTING_DIRECTOR_GUIDE.md))*

```python
class UnregisteredSpeakerError(KeyError):
    """Raised when a dialogue segment requests an unregistered character voice (ADR-021)."""

class TTSDispatcher:
    def __init__(
        self,
        project_dir: Path,
        default_backend: str = "gemini_tts",
        default_voice: str = "Aoede",
        max_workers: int = 1,
        rpm: float = DEFAULT_RPM,
        audio_dir: Optional[Path] = None,
        strict_speakers: bool = True,
    ):
        """
        Orchestrates concurrent speech synthesis with TokenBucket rate limiting and SQLite ledger state.
        When strict_speakers=True (default), prohibits silent fallback to Narrator for dialogue.
        """

    def get_speaker_config(
        self, speaker: str, seg_type: str = "narration"
    ) -> Dict[str, Any]:
        """Resolves complete speaker configuration, mapping roster aliases and checking whitelist."""

    def synthesize_segment(
        self, segment: Dict[str, Any], chapter_num: int, seg_num: int
    ) -> Tuple[Path, float]:
        """Synthesizes an individual dialogue or narration segment with SNR quality validation."""

    def synthesize_chapter_script(
        self,
        script_file: Path,
        chapter_idx: int,
    ) -> List[Path]:
        """Pre-flights all segments against voice registry, then synthesizes chunks concurrently."""

def resolve_speech_metadata_style(
    acting: Any,
    emotion: str = "neutral",
    intensity: str = "medium",
    memory_vocal_constraint: Optional[str] = None,
) -> str:
    """Transforms screenplay acting directives into natural language descriptors for speechMetadata.style."""

def synthesize_gemini_tts(
    text: str,
    output_file: Path,
    voice: str = DEFAULT_VOICE,
    model: str = "gemini-3.8-flash-tts",
    emotion: str = "neutral",
    acting: Any = None,
    intensity: str = "medium",
    memory_vocal_constraint: Optional[str] = None,
    max_retries: int = 4,
    rate_limiter: Optional[TokenBucketRateLimiter] = None,
) -> Tuple[Path, float]:
    """Synthesizes unary 24kHz WAV speech chunk with explicit BLOCK_NONE safetySettings and SNR gatekeeping."""

def synthesize_gemini_multispeaker_batch(
    batch: BatchPlanItem,
    output_file: Path,
    voice_map: Dict[str, str],
    model: str = "gemini-3.8-flash-tts",
    rate_limiter: Optional[TokenBucketRateLimiter] = None,
) -> Tuple[Path, float]:
    """Synthesizes multi-speaker 2-character dialogue rallies using multiSpeakerVoiceConfig."""

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

    def _partition_script_ambience_scenes(
        self,
        script_segments: Optional[List[Dict[str, Any]]],
        seg_starts_ms: Optional[Dict[int, int]],
        segment_durations_sec: Optional[Dict[int, float]],
        total_duration_ms: int,
    ) -> List[Tuple[str, int, int]]:
        """Partitions chapter into contiguous scene blocks based on acoustic_env shifts (ADR-022)."""

    def _compute_word_level_offset(
        self, text: str, anchor_word: str, seg_dur_ms: int, action_verb: str = ""
    ) -> int:
        """Calculates Foley anchor timing with BILINGUAL_ANCHOR_MAP, eliminating 50% dead-center trap (ADR-022)."""

    def _resolve_foley_asset(self, action_verb: str, object_material: str) -> Optional[Path]:
        """Resolves sound asset from sound bank using category guards (e.g. DOMETabl vs WEAPSwd)."""
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

### `AcousticBusMatrix` ([`audiobook_factory.acoustic_bus_matrix`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/acoustic_bus_matrix.py))
*Dynamic ducking profiles, UCS category resolution, and formant pocketing.*

```python
class DuckingProfile(BaseModel):
    profile_name: Literal["intimate_dialogue", "standard_speech", "combat_shouting", "heavy_impact", "combat_shock"]
    attenuation_db: float = -16.0
    attack_ms: int = 15
    release_ms: int = 350
    spectral_carve_hz: int = 2400
    spectral_carve_depth_db: float = -6.0

PROFILE_COMBAT_SHOCK = DuckingProfile(profile_name="combat_shock", attenuation_db=-24.0, release_ms=4000)
PROFILE_COMBAT = DuckingProfile(profile_name="combat_shouting", attenuation_db=-22.0, release_ms=250)

def get_ducking_profile(name_or_scene_type: str) -> DuckingProfile: ...
def derive_ucs_category(action_verb_or_cue: str, exciter: str = "") -> str:
    """Derives Universal Category System ID (e.g. DOMETabl for dining, WEAPSwd for swords, GOREAnat for flesh/bone)."""
def filter_concurrency_window(
    foley_cues: List[FoleyCue],
    window_ms: int = 200,
    max_concurrency: int = 3,
) -> List[FoleyCue]:
    """Applies voice limiter & priority stealing to prevent transient clumping within 200ms."""
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
*Film-standard discrete stem renderer and packaging ledger with Music-Only 2.2kHz notch EQ.*

```python
def render_discrete_stems(
    manifest: CinemaAudioManifest,
    dialogue_wav: Path,
    output_dir: Path,
    sound_bank: Optional[SoundBank] = None,
    ffmpeg: Optional[str] = None,
) -> StemLedger:
    """Renders 5 discrete DME stems (DX, MX, FX, AMB, ME) with isolated 2.2kHz notch on Music [0:a] only, and final broadcast master."""
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
    """Assembles and executes multitrack audio graph with ducking, IR reverb, and music-only notch."""

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
*M4B container packaging with AAC safety validation, faststart atom placement, and artwork embedding.*

```python
def package_m4b_audiobook(
    project_dir: Path,
    cover_image: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    enforce_gate6: bool = False,
) -> Path:
    """Validates AAC streams (is_all_aac); automatically transcodes uncompressed WAV or non-AAC chapters to AAC 192k."""

def _escape_ffmetadata(val: Any) -> str:
    """Escapes special characters (=, ;, #, \\) for FFMETADATA1 specification."""

def generate_ffmetadata(
    metadata: Dict[str, Any],
    chapter_durations: List[Dict[str, Any]],
    output_file: Path,
) -> Path:
    """Generates standard FFMETADATA1 file with escaped title, artist, and chapter timestamps."""
```

### `Foley & Magic Composite Baker` ([`scripts/bake_foley_composites.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/scripts/bake_foley_composites.py))
*Offline pre-rendering of multi-phase Harry Potter magic spells and tactile props, indexed into SQLite FTS5.*

```python
def bake_composite(
    output_path: Path,
    filter_complex: str,
    inputs: List[str],
    duration_sec: float = 2.0,
    ffmpeg: str = "ffmpeg",
) -> bool:
    """Renders a single pre-baked composite asset via FFmpeg with zero runtime filter graph bloat."""

def bake_all_magic_and_foley_composites() -> None:
    """Pre-bakes the core Harry Potter & fantasy tactile composite sound set and indexes them into Sound Bank."""
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

# Gate 1: Voice Collision Elimination & Acoustic Gender Alignment (ADR-021)
def audit_gate1_roster(
    roster_file: Union[Path, Dict],
    registry_file: Union[Path, Dict],
    active_characters: Optional[List[str]] = None,
) -> Dict[str, Any]: ...

# Gate 2: Screenplay Scripting Schema & Canonical Whitelist Enforcement (ADR-021)
def audit_gate2_script(
    script_file: Path,
    allowed_speakers: Optional[Set[str]] = None,
    project_dir: Optional[Path] = None,
) -> Dict[str, Any]: ...

# Gate 3 & 3.5: Acoustic Feasibility & Scene Coverage
def audit_gate3_scenes(scenes_file: Path, script_file: Path) -> Dict[str, Any]: ...
def audit_gate3_5_acoustic_feasibility(manifest: CreativeManifest, sound_bank: Optional[SoundBank] = None) -> AuditResult: ...

# Gate 4.5: Master Timeline & Audio Transcript Ledger
def audit_gate4_ledger(ledger_file: Path, script_file: Path, audio_dir: Path) -> Dict[str, Any]: ...

# Gate 5: Broadcast EBU R128 Master (Standardized 1.0 LU tolerance)
def audit_gate5_master(
    master_file: Path,
    target_lufs: float = -19.0,
    tolerance_lu: float = 1.0,
    max_true_peak: float = -1.4,
) -> Dict[str, Any]: ...

# Gate 5.2: Spectral Masking (DMR)
def audit_gate5_2_spectral_masking(dialogue_stem: Path, music_stem: Path, min_dmr_db: float = 12.0) -> AuditResult: ...

# Gate 5.3: Stereo Phase Correlation
def audit_gate5_3_stereo_phase(audio_file: Path, min_phase_correlation: float = 0.20) -> AuditResult: ...

# Gate 6A: Voice Continuity Across Chapters
def audit_gate6a_voice_continuity(project_dir: Path) -> AuditResult: ...

# Gate 6B: Inter-Chapter Loudness Continuity (1.0 LU max variance)
def audit_gate6b_loudness_continuity(chapter_files: List[Path], target_lufs: float = -19.0, max_variance: float = 1.0, strict: bool = False) -> AuditResult: ...

# Gate 6C: Table of Contents Monotonicity
def audit_gate6c_toc_monotonicity(chapter_files_or_project_dir: Any, toc: Optional[BookTableOfContents] = None) -> AuditResult: ...

# Gate 6D: Container Packaging Specifications
def audit_gate6d_packaging_specs(cover_image: Optional[Path], specs: Optional[BookPackagingSpecs] = None) -> AuditResult: ...

# Multi-Gate Macro Audits (Dynamic Gate 3 handling)
def audit_chapter_gates(project_dir: Path, chapter_num: int, active_speakers: Optional[List[str]] = None) -> Dict[str, Any]: ...
def audit_book_master(project_dir: Path, strict: bool = False) -> Dict[str, Any]: ...
```

---

## 🧠 Literary Translation Intelligence & Memory 2.0 ([`audiobook_factory.translation`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/translation/))

*(See full architectural manual: [`docs/LITERARY_TRANSLATION_INTELLIGENCE.md`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/docs/LITERARY_TRANSLATION_INTELLIGENCE.md))*

### 1. `BookBible` & `BookEntity` ([`audiobook_factory.translation.book_bible`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/translation/book_bible.py))
*Persistent canonical repository (`book_bible.json`) with SHA-256 versioning and one-way legacy glossary projection.*

```python
class BookEntity(BaseModel):
    canonical_en: str
    canonical_hi: str
    category: Literal["character", "location", "organization", "creature", "object", "title"] = "character"
    gender: Literal["male", "female", "neutral", "unknown"] = "unknown"
    aliases_en: List[str] = []
    aliases_hi: List[str] = []
    forbidden_variants: List[str] = []
    social_class: str = "standard"
    archetype: str = "NEUTRAL"
    speech_register: str = "standard_literary"
    voice_notes: str = ""
    first_seen_chapter: int = 1
    confidence: float = 1.0
    locked: bool = False

class BookBible(BaseModel):
    schema_version: str = "2.0.0"
    book_title: str = ""
    genre: str = "fantasy"
    tone_signature: str = "literary_dramatic"
    characters: Dict[str, BookEntity] = {}
    locations: Dict[str, BookEntity] = {}
    organizations: Dict[str, BookEntity] = {}
    creatures: Dict[str, BookEntity] = {}
    objects: Dict[str, BookEntity] = {}
    titles: Dict[str, BookEntity] = {}
    terminology: Dict[str, str] = {}
    terminology_variants: Dict[str, str] = {}  # Forbidden regex -> Canonical Devanagari
    relationships: List[DynamicRelationship] = []
    world_rules: List[WorldRule] = []
    flagged_conflicts: List[FlaggedConflict] = []

    def get_version_hash(self) -> str:
        """Returns a deterministic 16-char SHA-256 digest of all canonical entities and variants."""

    def propose_new_entity(self, entity: BookEntity, chapter_num: int = 1, context_snippet: str = "") -> bool:
        """Auto-commits non-conflicting entities with confidence >= 0.80; logs FlaggedConflict on mismatch."""

    def export_legacy_glossary(self, output_path: Optional[Path] = None) -> Dict[str, str]:
        """Projects canonical entities into flat translation/glossary.json format."""

    @classmethod
    def load(cls, path: Path) -> "BookBible": ...
    def save(self, path: Path) -> None: ...
```

### 2. `HindustaniRegisterEngine`, `CharacterLanguageProfile` & `RelationshipStateEngine`
*Contextual Urdu seasoning, sociolect archetypes, and 7D pronoun honorific resolution (`आप` / `तुम` / `तू`).*

```python
# audiobook_factory/translation/hindustani_register.py
class HindustaniRegisterEngine:
    @classmethod
    def from_genre(cls, genre: str) -> "HindustaniRegisterEngine": ...
    def build_prompt_directive(self, scene_intensity: Optional[Dict[str, float]] = None) -> str: ...
    def audit_text(self, hindi_text: str) -> HindustaniAuditResult: ...

# audiobook_factory/translation/character_profile.py
class CharacterLanguageProfile(BaseModel):
    character_name: str
    archetype: str = "NEUTRAL"
    sociolect: str = "standard_literary"
    sentence_tempo: Literal["clipped", "measured", "melodic", "hurried"] = "measured"
    discourse_markers_hi: List[str] = []
    signature_expressions_hi: List[str] = []

# audiobook_factory/translation/relationship_state.py
class DynamicRelationshipState(BaseModel):
    speaker: str
    listener: str
    respect: float = 0.0                # [-5.0, +5.0]
    familiarity: float = 0.0            # [0.0, 5.0]
    hostility: float = 0.0              # [0.0, 5.0]
    intimacy: float = 0.0               # [0.0, 5.0]
    authority_differential: float = 0.0 # [-5.0, +5.0]
    fear: float = 0.0                   # [0.0, 5.0]
    trust: float = 0.0                  # [-5.0, +5.0]

class RelationshipStateEngine:
    @staticmethod
    def resolve_pronoun_level(state: DynamicRelationshipState) -> Literal["aap", "tum", "tu"]: ...
    @staticmethod
    def apply_relationship_mutation(
        state: DynamicRelationshipState,
        interaction_type: str,
        event_id: str,
        chapter_num: int,
    ) -> DynamicRelationshipState: ...
```

### 3. `LiteraryIntensityVector`, `ScenePlanner` & `SourceSemanticMap`
*7D maturity vector ("Nothing Above Source"), transition-driven scene segmentation, and frozen proposition maps.*

```python
# audiobook_factory/translation/intensity_model.py
class LiteraryIntensityVector(BaseModel):
    profanity: float = 0.0              # [0.0, 5.0]
    sexual_intimacy: float = 0.0        # [0.0, 5.0]
    violence: float = 0.0               # [0.0, 5.0]
    emotional_intensity: float = 1.0    # [0.0, 5.0]
    formality: float = 2.5              # [0.0, 5.0]
    urdu_register: float = 2.0          # [0.0, 5.0]
    colloquiality: float = 2.0          # [0.0, 5.0]

class IntensityEvaluator:
    SOFT_WARN_DELTA: float = 0.75       # Non-blocking calibration notice
    HARD_FAIL_DELTA: float = 2.00       # Hard Gate T8 rejection threshold

    @classmethod
    def compare_vectors(cls, source: LiteraryIntensityVector, target: LiteraryIntensityVector) -> Dict[str, Any]: ...

# audiobook_factory/translation/scene_planner.py
class ScenePlanner:
    @classmethod
    def plan_chapter(cls, chapter_text: str, chapter_num: int, known_characters: Optional[List[str]] = None) -> ChapterPlan: ...

# audiobook_factory/translation/source_semantic_map.py
class SourceSemanticMapEngine:
    @classmethod
    def extract_semantic_map(cls, scene_id: str, chapter_num: int, source_text: str, known_entities: Optional[List[str]] = None) -> SourceSemanticMap: ...
```

### 4. `TranslationCertifier`, `TieredRepairEngine` & `IntelligentTranslationPipeline`
*12-Gate independent certification (`Gates T0–T11`), 3-tier self-healing repair, and end-to-end chapter orchestration.*

```python
# audiobook_factory/translation/certification.py
class TranslationCertifier:
    def certify_scene(
        self,
        scene_plan: ScenePlan,
        source_text: str,
        translated_text: str,
        semantic_map: SourceSemanticMap,
        provenance_record: Optional[SceneProvenanceRecord] = None,
        run_llm_audits: bool = True,
    ) -> SceneCertificationReport:
        """Executes Gates T0 through T11 and returns a complete SceneCertificationReport."""

# audiobook_factory/translation/repair_engine.py
class TieredRepairEngine:
    MAX_PARAGRAPH_ATTEMPTS: int = 2
    MAX_SCENE_ATTEMPTS: int = 1

    def repair_scene(
        self,
        scene_plan: ScenePlan,
        source_text: str,
        translated_text: str,
        semantic_map: SourceSemanticMap,
        cert_report: SceneCertificationReport,
        retranslate_scene_fn: Optional[Callable[[str, str], str]] = None,
    ) -> Tuple[str, SceneCertificationReport, List[str]]:
        """Escalates Tier 1 (0ms Regex/Advisory DB) -> Tier 2 (Surgical Paragraph LLM) -> Tier 3 (Full Scene)."""

# audiobook_factory/translation/pipeline.py
class IntelligentTranslationPipeline:
    def __init__(
        self,
        project_dir: Path,
        book_bible: Optional[BookBible] = None,
        policy: Optional[TranslationPolicyConfig] = None,
        genre: str = "fantasy",
        enable_llm_audits: bool = True,
    ): ...

    def translate_chapter(
        self,
        chapter_text: str,
        chapter_num: int,
        chapter_title: str = "",
        force_retranslate: bool = False,
    ) -> str:
        """Executes full Pillar 2 scene planning, Memory 2.0 retrieval, drafting, T0-T11 certification, and repair."""
```

### 5. World & Character Memory 2.0 ([`audiobook_factory.translation.memory`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/translation/memory/))
*(See complete specification: [`docs/WORLD_AND_CHARACTER_MEMORY_2_0.md`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/docs/WORLD_AND_CHARACTER_MEMORY_2_0.md))*

*Event-driven narrative continuity, epistemic isolation (`MUST_NOT_KNOW`), dual-chronology validation, and performance guidance.*

```python
# audiobook_factory/translation/memory/state.py
def apply_character_delta(character_states: Dict[str, CharacterState], world_state: WorldState, delta: StateDelta) -> CharacterState: ...
def apply_relationship_delta(relationships: Dict[str, DynamicRelationshipState], delta: StateDelta) -> DynamicRelationshipState: ...
def apply_knowledge_delta(facts_registry: Dict[str, KnowledgeFact], character_states: Dict[str, CharacterState], delta: StateDelta) -> KnowledgeFact: ...
def apply_world_or_narrative_delta(world_state: WorldState, character_states: Dict[str, CharacterState], delta: StateDelta) -> None: ...
def record_events_on_timeline(world_state: WorldState, events: List[StoryEvent], chapter: int, scene: str, location: str = "Unspecified", time_marker: str = "Unspecified") -> None: ...

# audiobook_factory/translation/memory/events.py
class StoryEventType(str, Enum):
    CHARACTER_INTRODUCED = "CHARACTER_INTRODUCED"
    CHARACTER_MOVED = "CHARACTER_MOVED"
    CHARACTER_INJURED = "CHARACTER_INJURED"
    CHARACTER_RECOVERED = "CHARACTER_RECOVERED"
    CHARACTER_DIED = "CHARACTER_DIED"
    SECRET_REVEALED = "SECRET_REVEALED"
    FACT_LEARNED = "FACT_LEARNED"
    FACT_DISPROVEN = "FACT_DISPROVEN"
    RELATIONSHIP_CHANGED = "RELATIONSHIP_CHANGED"
    BETRAYAL = "BETRAYAL"
    RECONCILIATION = "RECONCILIATION"
    ROMANTIC_CONFESSION = "ROMANTIC_CONFESSION"
    SHARED_DANGER = "SHARED_DANGER"
    THREAT_ISSUED = "THREAT_ISSUED"
    OBJECT_ACQUIRED = "OBJECT_ACQUIRED"
    OBJECT_TRANSFERRED = "OBJECT_TRANSFERRED"
    OBJECT_LOST = "OBJECT_LOST"
    LOCATION_CHANGED = "LOCATION_CHANGED"
    PROMISE_CREATED = "PROMISE_CREATED"
    PROMISE_BROKEN = "PROMISE_BROKEN"
    MYSTERY_INTRODUCED = "MYSTERY_INTRODUCED"
    MYSTERY_RESOLVED = "MYSTERY_RESOLVED"
    GOAL_CHANGED = "GOAL_CHANGED"
    BELIEF_CHANGED = "BELIEF_CHANGED"
    WORLD_STATE_CHANGED = "WORLD_STATE_CHANGED"
    OTHER = "OTHER"

class TemporalMode(str, Enum):
    PRESENT = "PRESENT"
    FLASHBACK = "FLASHBACK"
    MEMORY_DREAM = "MEMORY_DREAM"
    HISTORICAL_NARRATION = "HISTORICAL_NARRATION"
    NON_LINEAR = "NON_LINEAR"

class StoryEvent(BaseModel):
    event_id: str = ""
    chapter: int = 1
    scene: str = "scene_001"
    event_type: StoryEventType = StoryEventType.OTHER
    description: str
    participants: List[str] = []
    location: str = "Unspecified"
    source_reference: str = ""
    importance: int = 3
    temporal_mode: TemporalMode = TemporalMode.PRESENT
    salience_score: float = 0.5
    emotional_valence: Any = 0.0
    dramatic_tags: List[str] = []
    is_resolved: bool = False
    metadata: Dict[str, Any] = {}

class SceneChangeDetector:
    @classmethod
    def detect_temporal_mode(cls, text: str) -> Tuple[TemporalMode, Optional[int], str]: ...
    @classmethod
    def assess_scene(cls, scene_text: str, known_characters: Optional[List[str]] = None, chapter: int = 1, scene_id: str = "scene_001", active_characters: Optional[List[str]] = None, location: str = "Unspecified", known_objects: Optional[List[str]] = None, previous_location: Optional[str] = None) -> SceneChangeAssessment: ...

class EventExtractor:
    @classmethod
    def extract_scene_events(cls, scene_text: str, chapter: int = 1, scene_id: str = "scene_001", active_characters: Optional[List[str]] = None, known_characters: Optional[List[str]] = None, location: str = "Unspecified", known_objects: Optional[List[str]] = None, previous_location: Optional[str] = None, call_llm_fn: Optional[Callable[..., str]] = None, model: Optional[str] = None, force_llm: bool = False) -> Tuple[List[StoryEvent], SceneChangeAssessment]: ...
    @classmethod
    def propose_events_llm(cls, scene_text: str, chapter: int, scene_id: str, active_characters: List[str], location: str, default_temporal_mode: TemporalMode, call_llm_fn: Callable[..., str]) -> List[StoryEvent]: ...

# audiobook_factory/translation/memory/character_memory.py
class KnowledgeStatus(str, Enum):
    KNOWN = "KNOWN"
    SUSPECTED = "SUSPECTED"
    FALSE_BELIEF = "FALSE_BELIEF"
    UNKNOWN = "UNKNOWN"
    DISPROVEN = "DISPROVEN"

class KnowledgeFact(BaseModel):
    fact_id: str
    subject: str
    predicate: str
    value: str
    confidence: float = 1.0
    source_event: str
    learned_at: str = "ch001_scene_001"
    known_by: List[str] = []
    status: KnowledgeStatus = KnowledgeStatus.KNOWN
    character_statuses: Dict[str, KnowledgeStatus] = {}

class CharacterState(BaseModel):
    character_name: str
    is_alive: bool = True
    current_location: str = "Unspecified"
    current_emotion: str = "neutral"
    emotion_intensity: float = 0.5
    physical_condition: str = "healthy"
    active_injuries: List[str] = []
    energy: float = 0.8
    immediate_goal: str = ""
    known_facts: List[str] = []
    suspected_facts: List[str] = []
    false_beliefs: List[str] = []
    recent_events: List[str] = []
    arc_state: CharacterArcMemory = Field(default_factory=CharacterArcMemory)

class CharacterKnowledgeEngine:
    @staticmethod
    def register_or_update_fact(facts_registry: Dict[str, KnowledgeFact], character_states: Dict[str, CharacterState], fact_id: str, subject: str, predicate: str, value: str, source_event: str, learned_at: str, learners: List[str], status: KnowledgeStatus = KnowledgeStatus.KNOWN, confidence: float = 1.0) -> KnowledgeFact: ...
    @staticmethod
    def get_character_knowledge_status(character_name: str, fact_id: str, facts_registry: Dict[str, KnowledgeFact], character_states: Optional[Dict[str, CharacterState]] = None) -> KnowledgeStatus: ...
    @staticmethod
    def build_epistemic_constraints_for_scene(active_characters: List[str], facts_registry: Dict[str, KnowledgeFact], character_states: Optional[Dict[str, CharacterState]] = None, max_facts_per_bucket: int = 8) -> Dict[str, Dict[str, List[str]]]: ...

# audiobook_factory/translation/memory/memory_delta.py
class DeltaDomain(str, Enum):
    CHARACTER = "CHARACTER"
    RELATIONSHIP = "RELATIONSHIP"
    KNOWLEDGE = "KNOWLEDGE"
    WORLD = "WORLD"
    NARRATIVE = "NARRATIVE"

class StateMutability(str, Enum):
    HARD_CANON = "HARD_CANON"
    SOFT_STATE = "SOFT_STATE"

class StateDelta(BaseModel):
    delta_id: str = ""
    source_event_id: str
    chapter: int = 1
    scene: str = "scene_001"
    domain: DeltaDomain
    mutability: StateMutability = StateMutability.SOFT_STATE
    target_entity: str
    field_name: str
    operation: Literal["set", "add", "remove", "adjust"] = "set"
    old_value: Optional[Any] = None
    new_value: Any = None
    numeric_delta: Optional[float] = None
    temporal_mode: TemporalMode = TemporalMode.PRESENT
    rationale: str = ""
    metadata: Dict[str, Any] = {}

class StateDeltaEngine:
    @classmethod
    def derive_deltas_from_event(cls, event: StoryEvent, existing_relationships: Optional[Dict[str, DynamicRelationshipState]] = None) -> List[StateDelta]: ...
    @classmethod
    def compute_deltas_for_events(cls, events: List[StoryEvent], character_states: Optional[Dict[str, CharacterState]] = None, relationships: Optional[Dict[str, DynamicRelationshipState]] = None, facts_registry: Optional[Dict[str, KnowledgeFact]] = None, world_state: Optional[WorldState] = None) -> List[StateDelta]: ...

# audiobook_factory/translation/memory/memory_validator.py
class ValidationOutcome(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    CONFLICT = "CONFLICT"

class MemoryValidationReport(BaseModel):
    outcome: ValidationOutcome = ValidationOutcome.PASS
    accepted_deltas: List[StateDelta] = []
    rejected_deltas: List[StateDelta] = []
    rejected_event_ids: List[str] = []
    warnings: List[str] = []
    flagged_conflicts: List[FlaggedConflict] = []
    repair_instructions: List[str] = []

class MemoryValidator:
    @classmethod
    def validate_deltas(cls, deltas: List[StateDelta], book_bible: Optional[BookBible], character_states: Dict[str, CharacterState], relationships: Dict[str, DynamicRelationshipState], facts_registry: Dict[str, KnowledgeFact], world_state: WorldState, events_by_id: Optional[Dict[str, StoryEvent]] = None) -> MemoryValidationReport:
        """Enforces 7 contradiction classes (canon, timeline, dead character, physical impossibility, relationship jump, knowledge leakage, world rule)."""

# audiobook_factory/translation/memory/memory_store.py
class MemoryStore(BaseModel):
    schema_version: str = "2.0"
    memory_version: int = 0
    version_hash: str = "genesis"
    character_states: Dict[str, CharacterState] = {}
    relationships: Dict[str, DynamicRelationshipState] = {}
    facts_registry: Dict[str, KnowledgeFact] = {}
    world_state: WorldState = Field(default_factory=WorldState)
    events: Dict[str, StoryEvent] = {}
    rejected_events: Dict[str, StoryEvent] = {}
    commit_history: List[MemoryCommitRecord] = []
    flagged_conflicts: List[FlaggedConflict] = []

    def seed_from_book_bible(self, bible: BookBible) -> None: ...
    def commit_scene_memory(self, scene_id: str, chapter: int, events: List[StoryEvent], deltas: Optional[List[StateDelta]] = None, source_text: str = "", book_bible: Optional[BookBible] = None, location: str = "Unspecified", time_marker: str = "Unspecified") -> MemoryValidationReport: ...
    def trace_mutations(self, entity_name: Optional[str] = None, chapter: Optional[int] = None, scene_id: Optional[str] = None, domain: Optional[DeltaDomain] = None) -> List[StateDelta]: ...
    def save(self, path: Path) -> None: ...
    @classmethod
    def load(cls, path: Path, book_bible: Optional[BookBible] = None) -> MemoryStore: ...

# audiobook_factory/translation/memory/memory_retriever.py & memory_context.py
class MemoryContext(BaseModel):
    chapter: int = 1
    scene_id: str = "scene_01"
    location_name: str = "Unspecified"
    temporal_mode: TemporalMode = TemporalMode.PRESENT
    canon_identities: List[Dict[str, Any]] = []
    relevant_world_rules: List[str] = []
    active_character_states: Dict[str, CharacterState] = {}
    active_relationships: List[DynamicRelationshipState] = []
    epistemic_constraints: Dict[str, Dict[str, List[str]]] = {}
    location_state: Optional[LocationState] = None
    relevant_objects: List[ObjectState] = []
    recent_events: List[StoryEvent] = []
    salient_events: List[StoryEvent] = []
    unresolved_threads: List[NarrativeThreadState] = []

    @property
    def high_salience_events(self) -> List[StoryEvent]: ...
    def enforce_token_budget(self, max_token_budget: int = 800) -> "MemoryContext": ...
    def get_character_performance_guidance(self, speaker: str, target: Optional[str] = None) -> Dict[str, Any]: ...
    def apply_performance_guidance_to_segment(self, seg_dict: Dict[str, Any], target_speaker: Optional[str] = None) -> Dict[str, Any]: ...
    def get_prompt_context(self) -> str: ...

class MemoryRetriever:
    @classmethod
    def infer_active_entities(cls, scene_text: str, store: MemoryStore, book_bible: Optional[BookBible] = None, explicit_characters: Optional[List[str]] = None, explicit_location: Optional[str] = None) -> Tuple[List[str], str]: ...
    @classmethod
    def retrieve_for_scene(cls, store: MemoryStore, book_bible: Optional[BookBible] = None, chapter: int = 1, scene_id: str = "scene_01", active_characters: Optional[List[str]] = None, location: Optional[str] = None, active_location: Optional[str] = None, scene_text: str = "", max_recent_events: int = 5, max_salient_events: int = 4, max_token_budget: int = 800) -> MemoryContext: ...
```
