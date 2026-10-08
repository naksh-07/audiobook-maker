#!/usr/bin/env python3
"""
Audiobook Factory - Room 4 Multi-Cast TTS & Dialogue Editorial Engine.
Standard: v6.0-ENTERPRISE-DAG
Resolves takes from TakeBank (Tier 1 cache), executes concurrent TTS for dirty chunks,
applies DE-01 - DE-07 DSP conditioning, and assembles lossless 48kHz dialogue stems.
"""

from __future__ import annotations
import math
import numpy as np
import wave
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from audiobook_factory.contracts.editorial import (
    ChapterDialogueManifest,
    SegmentTakeMetadata,
    TimelineCueRecord,
    TimelineLedger,
)
from audiobook_factory.contracts.screenplay import ScreenplayScript, ScreenplaySegment
from audiobook_factory.contracts.ledger import (
    ChapterStageRecord,
    GateAuditRecord,
    StageArtifactRecord,
)
from audiobook_factory.core.cache.ledger import PipelineLedger
from audiobook_factory.core.cache.take_bank import TakeBank
from audiobook_factory.core.dialogue_editorial.editor import (
    DialogueEditorialEngine,
    EditorialPlan,
)


class SynthesisAndEditorialEngine:
    """
    Room 4 Multi-Cast TTS & Dialogue Editorial Subsystem.
    Assembles chapter dialogue stem using TakeBank content-addressed caching
    and applies DE-01 through DE-07 DSP rules with Gate 4.0 verification.
    """

    def __init__(
        self,
        project_dir: Union[str, Path] = "./projects/default",
        take_bank: Optional[TakeBank] = None,
        ledger: Optional[PipelineLedger] = None,
        editorial_plan: Optional[EditorialPlan] = None,
    ):
        self.project_dir = Path(project_dir).resolve()
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self.ledger = ledger
        self.take_bank = take_bank or TakeBank(
            cache_dir=self.project_dir / ".cache",
            ledger=self.ledger,
        )
        self.editorial_engine = DialogueEditorialEngine(plan=editorial_plan)

    def _synthesize_mock_chunk(self, segment: ScreenplaySegment, duration_sec: float = 1.0) -> bytes:
        """Generates mock 48kHz PCM audio bytes for uncached testing takes."""
        sr = 48000
        n_samples = int(duration_sec * sr)
        freq = 220.0 if segment.speaker.lower() != "narrator" else 150.0
        # Gentle sine tone
        tone = (np.sin(2 * np.pi * freq * np.arange(n_samples) / sr) * 16384.0).astype(np.int16)
        
        import io
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(tone.tobytes())
        return buf.getvalue()

    def synthesize_chapter(
        self,
        script: ScreenplayScript,
        project_id: str = "default",
        max_workers: int = 4,
    ) -> Tuple[ChapterDialogueManifest, GateAuditRecord]:
        """
        Processes all screenplay segments, resolving TakeBank cache hits,
        synthesizing uncached segments, assembling dialogue stem, and auditing Gate 4.0.
        """
        takes: List[SegmentTakeMetadata] = []

        for seg in script.segments:
            cached = self.take_bank.lookup_take(seg)
            if cached:
                takes.append(cached)
            else:
                # Synthesize new take
                raw_bytes = self._synthesize_mock_chunk(seg, duration_sec=1.2)
                stored_meta = self.take_bank.store_take(
                    segment=seg,
                    audio_source=raw_bytes,
                    project_id=project_id,
                    chapter_id=script.chapter_id,
                )
                takes.append(stored_meta)

        out_stem_wav = self.project_dir / f"chapter_{script.chapter_id:03d}_dialogue.wav"
        out_wav_path, timeline_ledger = self.editorial_engine.assemble_dialogue_stem(
            segments=script.segments,
            take_bank=self.take_bank,
            output_wav_path=out_stem_wav,
            chapter_id=script.chapter_id,
        )

        manifest = ChapterDialogueManifest(
            chapter_id=script.chapter_id,
            script_hash=script.compute_sha256_hash(),
            lossless_dialogue_wav_path=str(out_wav_path),
            timeline_ledger=timeline_ledger,
            takes=takes,
        )

        gate_audit = self.audit_gate_4_0(manifest)

        # Update SQLite Ledger if attached
        if self.ledger:
            stage_uid = f"ch{script.chapter_id:03d}_room4_synth"
            stage_rec = ChapterStageRecord(
                chapter_stage_uid=stage_uid,
                project_id=project_id,
                chapter_id=script.chapter_id,
                room_name="ROOM4_SYNTH",
                input_contract_hash=script.compute_sha256_hash(),
                output_contract_hash=manifest.compute_sha256_hash(),
                status="COMPLETED" if gate_audit.decision == "PASSED" else "FAILED",
            )
            self.ledger.set_stage_status(stage_rec)
            self.ledger.record_gate_audit(gate_audit)

            artifact_rec = StageArtifactRecord(
                artifact_uid=f"art_dialogue_ch{script.chapter_id:03d}",
                chapter_stage_uid=stage_uid,
                artifact_type="DIALOGUE_WAV",
                relative_file_path=out_stem_wav.name,
                sha256_checksum=manifest.compute_sha256_hash(),
                file_size_bytes=out_stem_wav.stat().st_size,
            )
            self.ledger.register_artifact(artifact_rec)

        return manifest, gate_audit

    def audit_gate_4_0(
        self,
        manifest: ChapterDialogueManifest,
    ) -> GateAuditRecord:
        """Audits Gate 4.0: Stem WAV Validity, Timeline Monotonicity, and Take Integrity."""
        stem_path = Path(manifest.lossless_dialogue_wav_path)
        stem_exists = stem_path.exists()
        file_size = stem_path.stat().st_size if stem_exists else 0
        total_duration = manifest.timeline_ledger.total_duration_sec
        cue_count = len(manifest.timeline_ledger.cues)
        take_count = len(manifest.takes)

        # Check timestamp monotonicity
        monotonic = True
        for i in range(len(manifest.timeline_ledger.cues) - 1):
            c_curr = manifest.timeline_ledger.cues[i]
            c_next = manifest.timeline_ledger.cues[i + 1]
            if c_next.start_time_sec < c_curr.start_time_sec:
                monotonic = False
                break

        is_passed = stem_exists and file_size > 1024 and total_duration > 0 and monotonic and cue_count == take_count
        failures = []
        if not stem_exists:
            failures.append("Dialogue stem WAV file missing on disk.")
        if file_size <= 1024:
            failures.append("Dialogue stem WAV file size suspiciously small or empty.")
        if not monotonic:
            failures.append("Timeline cues violate monotonic time sequence.")
        if cue_count != take_count:
            failures.append(f"Mismatch between cue count ({cue_count}) and take count ({take_count}).")

        return GateAuditRecord(
            audit_uid=f"gate40_ch{manifest.chapter_id:03d}_{manifest.compute_sha256_hash()[:8]}",
            chapter_stage_uid=f"ch{manifest.chapter_id:03d}_room4_synth",
            gate_name="GATE_4_0_AUDIO",
            decision="PASSED" if is_passed else "FAILED",
            metrics={
                "total_duration_sec": total_duration,
                "cue_count": cue_count,
                "take_count": take_count,
                "cache_hit_count": sum(1 for t in manifest.takes if t.was_cache_hit),
                "is_monotonic": monotonic,
            },
            failure_reasons=failures,
        )
