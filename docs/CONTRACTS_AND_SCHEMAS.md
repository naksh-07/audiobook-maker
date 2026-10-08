# 📜 Data Contracts & Schema Specification

**Standard**: `v6.0-ENTERPRISE-DAG`  
**Schema Version**: `"2.0"`  
**Validation Engine**: Pydantic v2 (Strict Typing & Fast C-Extension Serialization)  

---

## 1. Overview & Serialization Rules

Under the `v6.0-ENTERPRISE-DAG` standard, subsystems communicate **exclusively** via immutable JSON and WAV artifacts adhering to `schema_version: "2.0"`. 

### Deterministic Contract Hashing
All artifact checksums and cache keys use deterministic canonical JSON serialization:
- Keys sorted alphabetically (`sort_keys=True`).
- Whitespace eliminated (`separators=(',', ':')`).
- UTF-8 character encoding with Unicode preserved (`ensure_ascii=False`).
- Floats rounded to 3 decimal places for stability.

$$\text{Contract Hash} = \text{SHA-256}(\text{CanonicalJSON}(\text{Payload}))$$

---

## 2. Base Contract Model

```python
from pydantic import BaseModel, ConfigDict, Field
import hashlib
import json

class ContractBaseModel(BaseModel):
    """Base model for all v6.0-ENTERPRISE-DAG data contracts."""
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        populate_by_name=True
    )
    
    schema_version: str = Field(
        default="2.0",
        description="Contract schema version identifier"
    )

    def compute_sha256_hash(self) -> str:
        """Computes deterministic SHA-256 hash of the model data."""
        data_dict = self.model_dump(exclude={"schema_version"})
        serialized = json.dumps(
            data_dict,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
```

---

## 3. Room 1: Forensic Ingestion Contracts (`room1_ingest`)

### 3.1 `RawSentenceRecord` & `RawChapterRecord`
```python
from typing import List, Optional
from pydantic import Field

class RawSentenceRecord(ContractBaseModel):
    sentence_id: str = Field(
        ...,
        description="Deterministic sentence ID, e.g., 'ch01_p002_s01'"
    )
    text: str = Field(
        ...,
        min_length=1,
        description="Sanitized source sentence text in original script/language"
    )
    source_char_offset: int = Field(
        ...,
        ge=0,
        description="Character offset in raw source stream"
    )
    page_number: Optional[int] = Field(
        None,
        ge=1,
        description="Physical source page number if extracted from PDF"
    )

class RawChapterRecord(ContractBaseModel):
    chapter_id: int = Field(
        ...,
        ge=1,
        description="Monotonic 1-indexed chapter number"
    )
    title: str = Field(
        ...,
        description="Chapter heading title or 'Chapter X'"
    )
    source_hash: str = Field(
        ...,
        description="SHA-256 checksum of raw un-tokenized chapter text"
    )
    sentences: List[RawSentenceRecord] = Field(
        default_factory=list,
        description="Ordered sequence of raw sentences"
    )

class RawBookManifest(ContractBaseModel):
    book_id: str = Field(
        ...,
        description="Slugified unique book identifier, e.g., 'sword-of-destiny'"
    )
    title: str = Field(..., description="Full book title")
    author: str = Field(default="Unknown Author", description="Author name")
    source_file_path: str = Field(..., description="Absolute path to input EPUB/PDF/TXT")
    total_chapters: int = Field(..., ge=1)
    chapters: List[RawChapterRecord] = Field(default_factory=list)
```

### 3.2 `BookBible` & `CastLock`
```python
from typing import Dict

class CharacterDossier(ContractBaseModel):
    character_name: str = Field(...)
    canonical_hindi_name: str = Field(..., description="Devanagari phonetic transliteration")
    gender: str = Field(..., pattern="^(MALE|FEMALE|NEUTRAL|NARRATOR)$")
    vocal_weight: str = Field(default="MEDIUM", description="LIGHT, MEDIUM, HEAVY, GRUFF")
    social_register: str = Field(default="STANDARD", description="ROYAL, RUSTIC, SCHOLARLY, ROGUE")
    suggested_voice_id: str = Field(..., description="Gemini Voice ID, e.g., 'Puck', 'Charon'")
    pitch_offset: float = Field(default=0.0, ge=-12.0, le=12.0)
    tempo_multiplier: float = Field(default=1.0, ge=0.85, le=1.15)
    eq_profile_name: str = Field(default="FLAT")

class BookBible(ContractBaseModel):
    book_id: str = Field(...)
    literary_tradition: str = Field(default="HIGH_FANTASY")
    fidelity_tier: str = Field(default="RAW_UNRATED", pattern="^(CLASSIC_REVERENT|RAW_UNRATED)$")
    terminology_map: Dict[str, str] = Field(
        default_factory=dict,
        description="Proper nouns and terms mapped to Hindi transliterations"
    )
    characters: Dict[str, CharacterDossier] = Field(default_factory=dict)

class CastLock(ContractBaseModel):
    project_id: str = Field(...)
    narrator_voice_id: str = Field(default="Aoede")
    narrator_temperature: float = Field(default=0.32)
    cast_assignments: Dict[str, CharacterDossier] = Field(
        default_factory=dict,
        description="Locked speaker -> voice and formant mappings"
    )
```

---

## 4. Room 2: Translation Collective Contracts (`room2_translate`)

```python
from typing import List
from pydantic import Field

class TranslatedSentenceRecord(ContractBaseModel):
    sentence_id: str = Field(..., description="Must exactly match RawSentenceRecord.sentence_id")
    source_text: str = Field(..., description="Original language text")
    translated_text: str = Field(..., description="High-register Hindustani translation")
    terminology_hash: str = Field(..., description="Hash of active BookBible terms used")
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    user_override: bool = Field(default=False)

class TranslationBeatRecord(ContractBaseModel):
    beat_uid: str = Field(..., description="Unique beat ID, e.g., 'ch03_beat012'")
    narrative_function: str = Field(
        default="DIALOGUE_INTERACTION",
        pattern="^(NARRATIVE_EXPOSITION|DIALOGUE_INTERACTION|VISCERAL_COMBAT|INTIMATE_SCENE|ATMOSPHERIC_TRANSITION)$"
    )
    sentences: List[TranslatedSentenceRecord] = Field(default_factory=list)

class TranslationManifest(ContractBaseModel):
    chapter_id: int = Field(..., ge=1)
    source_hash: str = Field(..., description="Matches RawChapterRecord.source_hash")
    translation_mode: str = Field(default="RAW_UNRATED", pattern="^(CLASSIC_REVERENT|RAW_UNRATED)$")
    beats: List[TranslationBeatRecord] = Field(default_factory=list)
```

---

## 5. Room 3: Screenplay & Anti-Swap Contracts (`room3_screenplay`)

```python
from typing import List, Optional
from pydantic import Field

class SegmentProvenance(ContractBaseModel):
    origin: str = Field(default="AUTO_ATTRIBUTED", pattern="^(AUTO_ATTRIBUTED|MANUAL_PATCH|DIRECTOR_LOCK)$")
    user_locked: bool = Field(
        default=False,
        description="If true, automatic reconciliation will never overwrite this segment"
    )
    content_hash: str = Field(..., description="SHA-256 hash of text + speaker + acting directives")

class ScreenplaySegment(ContractBaseModel):
    segment_uid: str = Field(..., description="Deterministic segment ID, e.g., 'ch03_seg045'")
    beat_ref: str = Field(..., description="References TranslationBeatRecord.beat_uid")
    speaker: str = Field(..., description="Character name or 'Narrator'")
    voice_id: str = Field(..., description="Gemini Flash TTS voice identifier")
    text: str = Field(..., min_length=1, description="Devanagari text to synthesize")
    
    # 4D Acoustic Formants
    formant_signature: str = Field(default="p0_t0_eq0")
    pitch_shift: float = Field(default=0.0, ge=-12.0, le=12.0, description="Pitch delta percentage")
    speed_multiplier: float = Field(default=1.0, ge=0.85, le=1.15, description="Tempo multiplier")
    eq_curve_filter: Optional[str] = Field(
        default=None,
        description="FFmpeg parametric EQ curve (e.g. 'equalizer=f=320:width_type=o:w=1.2:g=2.5')"
    )
    
    # Directing Parameters
    temperature: float = Field(default=0.35, ge=0.30, le=0.52)
    acting_instruction: str = Field(
        default="understated natural dialogue (never theatrical)",
        description="Stanislavski physical vocal anchor"
    )
    
    # Timing & Editorial Metadata
    pre_speech_pause_ms: int = Field(default=250, ge=0, le=3000)
    post_speech_pause_ms: int = Field(default=400, ge=0, le=3000)
    
    provenance: SegmentProvenance

class ScreenplayScript(ContractBaseModel):
    chapter_id: int = Field(..., ge=1)
    translation_hash: str = Field(..., description="SHA-256 checksum of source TranslationManifest")
    segments: List[ScreenplaySegment] = Field(default_factory=list)
```

---

## 6. Room 4: Multi-Cast TTS & Dialogue Editorial Contracts (`room4_synth`)

```python
from typing import List, Optional
from pydantic import Field

class SegmentTakeMetadata(ContractBaseModel):
    segment_uid: str = Field(...)
    take_content_hash: str = Field(...)
    take_wav_path: str = Field(...)
    duration_sec: float = Field(..., gt=0.0)
    sample_rate: int = Field(default=48000)
    channels: int = Field(default=1)
    measured_lufs: Optional[float] = None
    was_cache_hit: bool = Field(default=False)

class TimelineCueRecord(ContractBaseModel):
    segment_uid: str = Field(...)
    speaker: str = Field(...)
    start_time_sec: float = Field(..., ge=0.0)
    end_time_sec: float = Field(..., gt=0.0)
    fade_in_ms: float = Field(default=12.0)
    fade_out_ms: float = Field(default=18.0)
    pause_after_sec: float = Field(default=0.4)

class TimelineLedger(ContractBaseModel):
    chapter_id: int = Field(..., ge=1)
    total_duration_sec: float = Field(..., gt=0.0)
    cues: List[TimelineCueRecord] = Field(default_factory=list)

class ChapterDialogueManifest(ContractBaseModel):
    chapter_id: int = Field(..., ge=1)
    script_hash: str = Field(...)
    lossless_dialogue_wav_path: str = Field(...)
    timeline_ledger: TimelineLedger
    takes: List[SegmentTakeMetadata] = Field(default_factory=list)
```

---

## 7. Room 5: Broadcast Mastering & Container Contracts (`room5_master`)

```python
from typing import List, Optional
from pydantic import Field

class LoudnessComplianceReport(ContractBaseModel):
    integrated_lufs: float = Field(..., description="Target: -19.0 LUFS ±0.5 LUFS")
    true_peak_dbfs: float = Field(..., description="Ceiling: <= -1.5 dBTP")
    loudness_range_lu: float = Field(..., description="Target: <= 6.5 LU")
    threshold_lufs: float = Field(...)
    is_compliant: bool = Field(...)

class MasterArtifact(ContractBaseModel):
    chapter_id: int = Field(..., ge=1)
    mastered_audio_path: str = Field(..., description="Path to 48kHz / 24-bit mastered M4A")
    duration_sec: float = Field(..., gt=0.0)
    compliance: LoudnessComplianceReport

class ChapterMarker(ContractBaseModel):
    chapter_index: int = Field(..., ge=1)
    title: str = Field(...)
    start_time_ms: int = Field(..., ge=0)
    end_time_ms: int = Field(..., gt=0)

class ContainerM4BManifest(ContractBaseModel):
    book_id: str = Field(...)
    container_m4b_path: str = Field(...)
    total_duration_sec: float = Field(...)
    file_size_bytes: int = Field(...)
    cover_image_path: Optional[str] = None
    chapters: List[ChapterMarker] = Field(default_factory=list)
```

---

## 8. Quality Gate Audit Contracts

```python
from typing import Dict, Any
from pydantic import Field

class GateAuditRecord(ContractBaseModel):
    audit_uid: str = Field(..., description="Unique audit run ID")
    chapter_stage_uid: str = Field(..., description="References chapter_stage_ledger.chapter_stage_uid")
    gate_name: str = Field(
        ...,
        pattern="^(GATE_0_1_INGEST|GATE_1_0_TRANSLATION|GATE_2_0_SCREENPLAY|GATE_4_0_AUDIO|GATE_5_0_MASTER)$"
    )
    decision: str = Field(..., pattern="^(PASSED|FAILED|REVIEW_REQUIRED)$")
    metrics: Dict[str, Any] = Field(
        default_factory=dict,
        description="Deterministic gate metrics (e.g. error rate, inversion count, LUFS diff)"
    )
    failure_reasons: List[str] = Field(default_factory=list)
```
