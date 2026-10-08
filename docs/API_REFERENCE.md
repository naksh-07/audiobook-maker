# 📚 API Reference: Data Contracts & Module Specifications

**Standard**: `v6.0-ENTERPRISE-DAG` & `v6.0-STUDIO-UI`  
**Package Namespace**: `audiobook_factory`  
**Validation Engine**: Pydantic v2 (`schema_version: "2.0"`)  

---

## 1. Overview & Architectural Hierarchy

The `audiobook_factory` Python framework is structured into five decoupled layers:

```
audiobook_factory/
├── contracts/          # Strict Pydantic v2 boundary models (schema_version: "2.0")
├── core/               # Standalone shared services (KeyPool, ModelManager, TakeBank, DSP, Mastering)
├── rooms/              # 5 Standalone Room subsystems (Ingestion, Translation, Screenplay, Synth, Master)
├── dag/                # DAG Orchestrator, Presets, and DiffReconciler
└── api/                # StudioBridge JSON IPC for Antigravity Sidecar Webview
```

---

## 2. Module Specifications: `audiobook_factory.contracts`

All contract models inherit from `ContractBaseModel` and enforce strict typing and deterministic SHA-256 serialization.

### 2.1 Base Model (`contracts.base`)
```python
class ContractBaseModel(BaseModel):
    schema_version: str = "2.0"
    def compute_sha256_hash(self) -> str: ...
```

### 2.2 Room 1 Ingestion Models (`contracts.ingestion` & `contracts.lore`)
- `RawSentenceRecord`: `sentence_id: str`, `text: str`, `source_char_offset: int`, `page_number: Optional[int]`.
- `RawChapterRecord`: `chapter_id: int`, `title: str`, `source_hash: str`, `sentences: List[RawSentenceRecord]`.
- `RawBookManifest`: `book_id: str`, `title: str`, `author: str`, `chapters: List[RawChapterRecord]`.
- `CharacterDossier`: `character_name: str`, `canonical_hindi_name: str`, `gender: str`, `vocal_weight: str`, `suggested_voice_id: str`, `pitch_offset: float`, `tempo_multiplier: float`.
- `BookBible`: `book_id: str`, `fidelity_tier: str`, `terminology_map: Dict[str, str]`, `characters: Dict[str, CharacterDossier]`.
- `CastLock`: `project_id: str`, `narrator_voice_id: str`, `narrator_temperature: float`, `cast_assignments: Dict[str, CharacterDossier]`.

### 2.3 Room 2 Translation Models (`contracts.translation`)
- `TranslatedSentenceRecord`: `sentence_id: str`, `source_text: str`, `translated_text: str`, `terminology_hash: str`, `confidence_score: float`.
- `TranslationBeatRecord`: `beat_uid: str`, `narrative_function: str`, `sentences: List[TranslatedSentenceRecord]`.
- `TranslationManifest`: `chapter_id: int`, `source_hash: str`, `translation_mode: str`, `beats: List[TranslationBeatRecord]`.

### 2.4 Room 3 Screenplay Models (`contracts.screenplay`)
- `SegmentProvenance`: `origin: str`, `user_locked: bool`, `content_hash: str`.
- `ScreenplaySegment`: `segment_uid: str`, `beat_ref: str`, `speaker: str`, `voice_id: str`, `text: str`, `pitch_shift: float`, `speed_multiplier: float`, `temperature: float`, `acting_instruction: str`, `provenance: SegmentProvenance`.
- `ScreenplayScript`: `chapter_id: int`, `translation_hash: str`, `segments: List[ScreenplaySegment]`.

### 2.5 Room 4 Editorial & Audio Models (`contracts.editorial`)
- `SegmentTakeMetadata`: `segment_uid: str`, `take_content_hash: str`, `take_wav_path: str`, `duration_sec: float`, `was_cache_hit: bool`.
- `TimelineCueRecord`: `segment_uid: str`, `speaker: str`, `start_time_sec: float`, `end_time_sec: float`, `fade_in_ms: float`, `fade_out_ms: float`.
- `TimelineLedger`: `chapter_id: int`, `total_duration_sec: float`, `cues: List[TimelineCueRecord]`.
- `ChapterDialogueManifest`: `chapter_id: int`, `script_hash: str`, `lossless_dialogue_wav_path: str`, `timeline_ledger: TimelineLedger`, `takes: List[SegmentTakeMetadata]`.

### 2.6 Room 5 Mastering Models (`contracts.mastering`)
- `LoudnessComplianceReport`: `integrated_lufs: float`, `true_peak_dbfs: float`, `loudness_range_lu: float`, `is_compliant: bool`.
- `MasterArtifact`: `chapter_id: int`, `mastered_audio_path: str`, `duration_sec: float`, `compliance: LoudnessComplianceReport`.
- `ContainerM4BManifest`: `book_id: str`, `container_m4b_path: str`, `total_duration_sec: float`, `file_size_bytes: int`, `chapters: List[ChapterMarker]`.

---

## 3. Module Specifications: `audiobook_factory.core`

### 3.1 `core.key_manager.KeyPool`
Manages pool of 120+ Google Gemini API keys with SQLite round-robin rotation, concurrency throttling, and cool-down tracking.
```python
class KeyPool:
    def __init__(self, db_path: str = "~/.gemini/api_keys.db"): ...
    def acquire_healthy_key(self) -> str: ...
    def acquire_key_context(self) -> Generator[str, None, None]: ...
    def report_quota_error(self, api_key: str, status_code: int = 429): ...
    def get_pool_health(self) -> Dict[str, int]: ...
```

### 3.2 `core.model_manager.ModelManager`
Enforces Tier-1 Flagship routing and permanent `BLOCK_NONE` safety settings for creative text processing.
```python
class ModelTier(Enum):
    TIER_1_FLAGSHIP = "tier_1_flagship" # gemini-3.8-flash / 3.7-flash
    TIER_2_FAST = "tier_2_fast"         # banned for creative dramaturgy

class ModelManager:
    @staticmethod
    def get_client_for_tier(tier: ModelTier) -> genai.Client: ...
    @staticmethod
    def get_permissive_safety_settings() -> List[types.SafetySetting]: ...
```

### 3.3 `core.cache.TakeBank`
Content-addressed Tier 1 audio take cache with transaction-safe SQLite ledger registration and LRU disk eviction.
```python
class TakeBank:
    def __init__(self, cache_dir: str = ".audiobook_cache", db_path: str = "pipeline_ledger.db"): ...
    def compute_hash(self, segment_spec: dict) -> str: ...
    def lookup_take(self, segment_spec: dict) -> Optional[SegmentTakeMetadata]: ...
    def store_take(self, segment_spec: dict, wav_bytes: bytes) -> SegmentTakeMetadata: ...
    def enforce_lru_quota(self, max_bytes: int = 10 * 1024 * 1024 * 1024): ...
```

### 3.4 `core.dialogue_editorial.DialogueEditorialEngine`
Implements DE-01 through DE-07 DSP rules: 12ms/18ms Hann micro-fades, -52 dBFS zero-crossing snapping, and relative breath attenuation.
```python
class DialogueEditorialEngine:
    def apply_editorial_conditioning(self, input_wav_path: str, plan: EditorialPlan) -> str: ...
    def assemble_dialogue_stem(self, takes: List[SegmentTakeMetadata], cues: List[TimelineCueRecord], output_wav: str) -> str: ...
```

### 3.5 `core.mastering.MasterEngine`
Broadcast vocal mastering suite applying two-pass measured linear loudnorm and Kaiser Sinc 48kHz / 24-bit resampling.
```python
class MasterEngine:
    def __init__(self, spec: MasteringSpec): ...
    def master_dialogue_stem(self, input_wav: str, output_m4a: str) -> MasterArtifact: ...
```

---

## 4. Module Specifications: `audiobook_factory.rooms`

### 4.1 Room 1: `rooms.room1_ingest.IngestionEngine`
```python
class IngestionEngine:
    def __init__(self, project_dir: str): ...
    def process_source(self, source_file_path: str, fidelity_tier: str = "RAW_UNRATED") -> Tuple[RawBookManifest, BookBible, CastLock]: ...
```

### 4.2 Room 2: `rooms.room2_translate.TranslationCollective`
```python
class TranslationCollective:
    def __init__(self, project_dir: str): ...
    def translate_chapter(self, chapter_id: int, mode: str = "RAW_UNRATED") -> TranslationManifest: ...
    def patch_beat(self, chapter_id: int, beat_uid: str, refined_text: str) -> TranslationManifest: ...
```

### 4.3 Room 3: `rooms.room3_screenplay.ScreenplayDramaturge`
```python
class ScreenplayDramaturge:
    def __init__(self, project_dir: str): ...
    def build_screenplay(self, chapter_id: int) -> ScreenplayScript: ...
    def reconcile_dirty_segments(self, chapter_id: int) -> ScreenplayScript: ...
```

### 4.4 Room 4: `rooms.room4_synth.SynthesisAndEditorialEngine`
```python
class SynthesisAndEditorialEngine:
    def __init__(self, project_dir: str): ...
    def synthesize_chapter(self, chapter_id: int, max_workers: int = 3) -> ChapterDialogueManifest: ...
    def synthesize_single_segment(self, chapter_id: int, segment_uid: str) -> SegmentTakeMetadata: ...
```

### 4.5 Room 5: `rooms.room5_master.BroadcastMasteringEngine`
```python
class BroadcastMasteringEngine:
    def __init__(self, project_dir: str): ...
    def master_chapter(self, chapter_id: int, target_lufs: float = -19.0) -> MasterArtifact: ...
    def package_audiobook(self, cover_image_path: str, output_filename: str) -> ContainerM4BManifest: ...
```

---

## 5. Module Specifications: `audiobook_factory.dag`

### 5.1 `dag.orchestrator.DAGOrchestrator`
```python
class DAGOrchestrator:
    def __init__(self, project_dir: str, db_path: str = "pipeline_ledger.db"): ...
    def run_preset(self, preset_name: str, source_path: Optional[str] = None, **kwargs) -> Dict[str, Any]: ...
    def reconcile_dirty(self) -> Dict[str, Any]: ...
```

### 5.2 `dag.diff_reconciler.DiffReconciler`
```python
class DiffReconciler:
    def __init__(self, db_path: str = "pipeline_ledger.db"): ...
    def evaluate_project_dirty_stages(self, project_id: str) -> DirtyExecutionPlan: ...
```

---

## 6. Module Specifications: `audiobook_factory.api.studio_bridge`

```python
def handle_bridge_command(subcommand: str, args: List[str]) -> Dict[str, Any]:
    """CLI JSON-over-stdout entrypoint invoked by Node.js Sidecar (main.mjs)."""
    ...
```
