#!/usr/bin/env python3
"""
Audiobook Factory - Tier 1 TakeBank Content-Addressed Audio Cache.
Standard: v6.0-ENTERPRISE-DAG
Computes deterministic SHA-256 take keys, avoids redundant TTS network synthesis,
and provides LRU disk quota management.
"""

from __future__ import annotations
import hashlib
import json
import os
import shutil
import wave
from pathlib import Path
from typing import Any, Dict, Optional, Union

from audiobook_factory.contracts.editorial import SegmentTakeMetadata
from audiobook_factory.contracts.ledger import ProjectMetadataRecord, SegmentTakeCacheRecord
from audiobook_factory.contracts.screenplay import ScreenplaySegment
from audiobook_factory.core.cache.ledger import PipelineLedger


class TakeBank:
    """
    Tier 1 Audio Take Bank Cache.
    Content-addressed WAV cache indexing audio by acoustic & linguistic signature:
    hash(text + speaker + voice_id + formant_signature + pitch + speed + temperature).
    """

    def __init__(
        self,
        cache_dir: str | Path = ".audiobook_cache",
        ledger: Optional[PipelineLedger] = None,
        max_cache_bytes: int = 10 * 1024 * 1024 * 1024,  # 10 GB default
    ):
        self.cache_dir = Path(cache_dir).resolve()
        self.takes_dir = self.cache_dir / "takes"
        self.takes_dir.mkdir(parents=True, exist_ok=True)
        self.ledger = ledger
        self.max_cache_bytes = max_cache_bytes

    @staticmethod
    def compute_take_hash(segment: Union[Dict[str, Any], ScreenplaySegment]) -> str:
        """
        Computes deterministic SHA-256 hash for a given segment.
        """
        if isinstance(segment, ScreenplaySegment):
            text_val = segment.text.strip()
            speaker_val = segment.speaker.strip()
            voice_val = segment.voice_id.strip()
            formant_val = segment.formant_signature
            pitch_val = round(float(segment.pitch_shift), 3)
            speed_val = round(float(segment.speed_multiplier), 3)
            temp_val = round(float(segment.temperature), 3)
            acting_val = str(segment.acting_instruction or "").strip()
        elif isinstance(segment, dict):
            text_val = str(segment.get("text", "")).strip()
            speaker_val = str(segment.get("speaker", "")).strip()
            voice_val = str(segment.get("voice_id", segment.get("voice", ""))).strip()
            formant_val = str(segment.get("formant_signature", "p0_t0_eq0"))
            pitch_val = round(float(segment.get("pitch_shift", 0.0)), 3)
            speed_val = round(float(segment.get("speed_multiplier", 1.0)), 3)
            temp_val = round(float(segment.get("temperature", 0.35)), 3)
            acting_val = str(segment.get("acting_instruction", segment.get("acting_directive", ""))).strip()
        else:
            raise ValueError(f"Unsupported segment type: {type(segment)}")

        payload = {
            "text": text_val,
            "speaker": speaker_val,
            "voice_id": voice_val,
            "formant_signature": formant_val,
            "pitch_shift": pitch_val,
            "speed_multiplier": speed_val,
            "temperature": temp_val,
            "acting_instruction": acting_val,
        }
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def get_take_path(self, take_content_hash: str) -> Path:
        """Returns the file path for a cached take WAV."""
        return self.takes_dir / f"{take_content_hash}.wav"

    def lookup_take(
        self,
        segment: Union[Dict[str, Any], ScreenplaySegment],
    ) -> Optional[SegmentTakeMetadata]:
        """
        Looks up a cached take in TakeBank. Returns SegmentTakeMetadata if found and valid.
        """
        take_hash = self.compute_take_hash(segment)
        take_path = self.get_take_path(take_hash)

        if not take_path.exists():
            return None

        # Check ledger record if ledger is attached
        if self.ledger:
            db_record = self.ledger.get_take_cache(take_hash)
            if not db_record or not db_record.is_valid:
                return None

        # Read audio duration and sample rate
        try:
            with wave.open(str(take_path), "rb") as wf:
                channels = wf.getnchannels()
                sample_rate = wf.getframerate()
                n_frames = wf.getnframes()
                duration_sec = round(n_frames / float(sample_rate), 4)
        except Exception:
            return None

        seg_uid = ""
        if isinstance(segment, ScreenplaySegment):
            seg_uid = segment.segment_uid
        elif isinstance(segment, dict):
            seg_uid = str(segment.get("segment_uid", segment.get("uid", "")))

        # Update access time for LRU tracking
        try:
            os.utime(str(take_path), None)
        except Exception:
            pass

        return SegmentTakeMetadata(
            segment_uid=seg_uid,
            take_content_hash=take_hash,
            take_wav_path=str(take_path),
            duration_sec=duration_sec,
            sample_rate=sample_rate,
            channels=channels,
            measured_lufs=None,
            was_cache_hit=True,
        )

    def store_take(
        self,
        segment: Union[Dict[str, Any], ScreenplaySegment],
        audio_source: Union[bytes, str, Path],
        project_id: str = "default",
        chapter_id: int = 1,
        measured_lufs: Optional[float] = None,
    ) -> SegmentTakeMetadata:
        """
        Stores an audio take in the TakeBank and updates SQLite ledger.
        """
        take_hash = self.compute_take_hash(segment)
        target_path = self.get_take_path(take_hash)

        if isinstance(audio_source, bytes):
            with open(target_path, "wb") as f:
                f.write(audio_source)
        elif isinstance(audio_source, (str, Path)):
            src_p = Path(audio_source)
            if src_p != target_path:
                shutil.copy2(str(src_p), str(target_path))

        with wave.open(str(target_path), "rb") as wf:
            channels = wf.getnchannels()
            sample_rate = wf.getframerate()
            n_frames = wf.getnframes()
            duration_sec = round(n_frames / float(sample_rate), 4)

        if isinstance(segment, ScreenplaySegment):
            seg_uid = segment.segment_uid
            speaker = segment.speaker
            voice_id = segment.voice_id
            formant = segment.formant_signature
            text_c = segment.text
        else:
            seg_uid = str(segment.get("segment_uid", segment.get("uid", "")))
            speaker = str(segment.get("speaker", "Narrator"))
            voice_id = str(segment.get("voice_id", segment.get("voice", "Aoede")))
            formant = str(segment.get("formant_signature", "p0_t0_eq0"))
            text_c = str(segment.get("text", ""))

        if self.ledger:
            # Auto-ensure project metadata exists to satisfy foreign key constraint
            if not self.ledger.get_project(project_id):
                self.ledger.upsert_project(
                    ProjectMetadataRecord(
                        project_id=project_id,
                        source_file_path="local_cache",
                        title=project_id,
                    )
                )

            record = SegmentTakeCacheRecord(
                take_content_hash=take_hash,
                project_id=project_id,
                chapter_id=chapter_id,
                segment_uid=seg_uid,
                speaker=speaker,
                voice_id=voice_id,
                formant_signature=formant,
                text_content=text_c,
                take_wav_path=str(target_path),
                duration_sec=duration_sec,
                measured_lufs=measured_lufs,
                is_valid=True,
            )
            self.ledger.put_take_cache(record)

        return SegmentTakeMetadata(
            segment_uid=seg_uid,
            take_content_hash=take_hash,
            take_wav_path=str(target_path),
            duration_sec=duration_sec,
            sample_rate=sample_rate,
            channels=channels,
            measured_lufs=measured_lufs,
            was_cache_hit=False,
        )

    def prune_lru(self, max_bytes: Optional[int] = None) -> int:
        """
        Prunes least recently accessed take WAV files when total directory size exceeds max_bytes.
        Returns the number of pruned files.
        """
        limit = max_bytes or self.max_cache_bytes
        wav_files = list(self.takes_dir.glob("*.wav"))
        total_size = sum(f.stat().st_size for f in wav_files)

        if total_size <= limit:
            return 0

        # Sort files by last access time (oldest first)
        wav_files.sort(key=lambda f: f.stat().st_atime)
        pruned_count = 0

        for f in wav_files:
            if total_size <= limit:
                break
            f_size = f.stat().st_size
            try:
                take_hash = f.stem
                if self.ledger:
                    self.ledger.invalidate_take_cache(take_hash)
                f.unlink(missing_ok=True)
                total_size -= f_size
                pruned_count += 1
            except Exception:
                pass

        return pruned_count
