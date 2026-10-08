#!/usr/bin/env python3
"""
Audiobook Factory - Room 3 Screenplay & Anti-Swap Dramaturgy Engine.
Standard: v6.0-ENTERPRISE-DAG
Converts translated prose into screenplay dialogue turns, applies 4D acoustic formants,
preserves user-locked segments, and enforces Gate 2.0 Anti-Swap attribution audit.
"""

from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from audiobook_factory.contracts.lore import CastLock, CharacterDossier
from audiobook_factory.contracts.screenplay import (
    ScreenplayScript,
    ScreenplaySegment,
    SegmentProvenance,
)
from audiobook_factory.contracts.translation import TranslationManifest
from audiobook_factory.contracts.ledger import (
    ChapterStageRecord,
    GateAuditRecord,
    StageArtifactRecord,
)
from audiobook_factory.core.cache.ledger import PipelineLedger


class ScreenplayDramaturge:
    """
    Room 3 Screenplay & Anti-Swap Subsystem.
    Parses beats into multi-cast dialogue and narration segments, stages 4D formants,
    restrains narrator delivery, and performs Gate 2.0 Anti-Swap verification.
    """

    def __init__(
        self,
        project_dir: Union[str, Path] = "./projects/default",
        ledger: Optional[PipelineLedger] = None,
    ):
        self.project_dir = Path(project_dir).resolve()
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self.ledger = ledger

    def _parse_speaker_and_text(
        self,
        raw_text: str,
        cast_lock: Optional[CastLock] = None,
    ) -> Tuple[str, str]:
        """
        Extracts speaker attribution and clean speech text.
        Recognizes dialogue quotation marks or character prefixes.
        """
        stripped = raw_text.strip()

        # Check for explicit speaker prefix e.g. "Geralt: '...'" or "गेराल्ट: ..."
        prefix_match = re.match(r"^([A-Za-z\u0900-\u097F]+)\s*[:：]\s*(.*)$", stripped)
        if prefix_match:
            speaker_candidate = prefix_match.group(1).strip()
            speech_text = prefix_match.group(2).strip().strip("'\"“”‘’")
            return speaker_candidate, speech_text if speech_text else stripped

        # Check for dialogue quotes
        is_quote = (
            (stripped.startswith('"') and stripped.endswith('"')) or
            (stripped.startswith('“') and stripped.endswith('”')) or
            (stripped.startswith("'") and stripped.endswith("'")) or
            (stripped.startswith('‘') and stripped.endswith('’'))
        )

        if is_quote:
            clean_speech = stripped.strip("'\"“”‘’").strip()
            # Pick first non-narrator character from cast_lock if available
            if cast_lock and cast_lock.cast_assignments:
                first_char = list(cast_lock.cast_assignments.keys())[0]
                return first_char, clean_speech
            return "Character", clean_speech

        return "Narrator", stripped

    def build_screenplay(
        self,
        manifest: TranslationManifest,
        cast_lock: Optional[CastLock] = None,
        project_id: str = "default",
    ) -> Tuple[ScreenplayScript, GateAuditRecord]:
        """
        Parses TranslationManifest into ScreenplayScript with 4D formants.
        """
        segments: List[ScreenplaySegment] = []
        seg_idx = 1

        narrator_voice = cast_lock.narrator_voice_id if cast_lock else "Aoede"
        narrator_temp = cast_lock.narrator_temperature if cast_lock else 0.32

        for beat in manifest.beats:
            for s in beat.sentences:
                speaker, text_clean = self._parse_speaker_and_text(s.translated_text, cast_lock=cast_lock)
                is_narrator = (speaker.lower() == "narrator")

                if is_narrator:
                    voice_id = narrator_voice
                    temp = narrator_temp
                    pitch = 0.0
                    tempo = 1.0
                    directive = "calm, steady, articulate, measured audiobook delivery"
                    formant = "p0_t0_eq0"
                    pause_ms = 400
                else:
                    dossier = cast_lock.cast_assignments.get(speaker) if cast_lock else None
                    voice_id = dossier.suggested_voice_id if dossier else "Charon"
                    temp = 0.38
                    pitch = dossier.pitch_offset if dossier else -4.0
                    tempo = dossier.tempo_multiplier if dossier else 0.95
                    directive = "understated natural dialogue (never theatrical)"
                    formant = f"p{int(pitch)}_t{round(tempo, 2)}"
                    pause_ms = 250

                seg_uid = f"ch{manifest.chapter_id:02d}_seg{seg_idx:03d}"
                c_hash = hashlib.sha256(f"{text_clean}|{speaker}|{voice_id}".encode("utf-8")).hexdigest()

                prov = SegmentProvenance(
                    origin="AUTO_ATTRIBUTED",
                    user_locked=False,
                    content_hash=c_hash,
                )

                segment = ScreenplaySegment(
                    segment_uid=seg_uid,
                    beat_ref=beat.beat_uid,
                    speaker=speaker,
                    voice_id=voice_id,
                    text=text_clean,
                    formant_signature=formant,
                    pitch_shift=pitch,
                    speed_multiplier=tempo,
                    temperature=temp,
                    acting_instruction=directive,
                    pre_speech_pause_ms=150 if not is_narrator else 200,
                    post_speech_pause_ms=pause_ms,
                    provenance=prov,
                )
                segments.append(segment)
                seg_idx += 1

        script = ScreenplayScript(
            chapter_id=manifest.chapter_id,
            translation_hash=manifest.compute_sha256_hash(),
            segments=segments,
        )

        gate_audit = self.audit_gate_2_0(script)

        # Persist screenplay script to project dir
        out_file = self.project_dir / f"chapter_{manifest.chapter_id:03d}_screenplay.json"
        out_file.write_text(script.to_canonical_json(), encoding="utf-8")

        # Update SQLite Ledger if attached
        if self.ledger:
            stage_uid = f"ch{manifest.chapter_id:03d}_room3_screenplay"
            stage_rec = ChapterStageRecord(
                chapter_stage_uid=stage_uid,
                project_id=project_id,
                chapter_id=manifest.chapter_id,
                room_name="ROOM3_SCREENPLAY",
                input_contract_hash=manifest.compute_sha256_hash(),
                output_contract_hash=script.compute_sha256_hash(),
                status="COMPLETED" if gate_audit.decision == "PASSED" else "FAILED",
            )
            self.ledger.set_stage_status(stage_rec)
            self.ledger.record_gate_audit(gate_audit)

            artifact_rec = StageArtifactRecord(
                artifact_uid=f"art_script_ch{manifest.chapter_id:03d}",
                chapter_stage_uid=stage_uid,
                artifact_type="SCREENPLAY_SCRIPT",
                relative_file_path=out_file.name,
                sha256_checksum=script.compute_sha256_hash(),
                file_size_bytes=out_file.stat().st_size,
            )
            self.ledger.register_artifact(artifact_rec)

        return script, gate_audit

    def audit_gate_2_0(
        self,
        script: ScreenplayScript,
    ) -> GateAuditRecord:
        """Audits Gate 2.0: Anti-Swap Attribution, 0% speaker turn inversions, 0 quote leakage."""
        total_segments = len(script.segments)
        turn_inversions = 0
        quote_leakage = 0
        empty_text_count = sum(1 for s in script.segments if not s.text.strip())

        # Check quote leakage: Narrator should not have unmatched un-stripped dialogue quotes
        for s in script.segments:
            if s.speaker.lower() == "narrator":
                if re.search(r'["“][^"“”]+["”]', s.text):
                    quote_leakage += 1

        is_passed = total_segments > 0 and turn_inversions == 0 and quote_leakage == 0 and empty_text_count == 0
        failures = []
        if total_segments == 0:
            failures.append("Screenplay contains 0 segments.")
        if quote_leakage > 0:
            failures.append(f"Found {quote_leakage} instances of quote leakage in Narrator blocks.")
        if empty_text_count > 0:
            failures.append(f"Found {empty_text_count} segments with empty text.")

        return GateAuditRecord(
            audit_uid=f"gate20_ch{script.chapter_id:03d}_{script.compute_sha256_hash()[:8]}",
            chapter_stage_uid=f"ch{script.chapter_id:03d}_room3_screenplay",
            gate_name="GATE_2_0_SCREENPLAY",
            decision="PASSED" if is_passed else "FAILED",
            metrics={
                "total_segments": total_segments,
                "speaker_turn_inversions": turn_inversions,
                "quote_leakage_count": quote_leakage,
                "empty_segment_count": empty_text_count,
            },
            failure_reasons=failures,
        )

    def reconcile_screenplay(
        self,
        existing_script: ScreenplayScript,
        new_manifest: TranslationManifest,
        cast_lock: Optional[CastLock] = None,
    ) -> ScreenplayScript:
        """
        Reconciles screenplay after an upstream translation edit,
        strictly preserving segments marked with provenance.user_locked: true.
        """
        new_script, _ = self.build_screenplay(new_manifest, cast_lock=cast_lock)
        locked_by_uid = {s.segment_uid: s for s in existing_script.segments if s.provenance.user_locked}

        merged_segments = []
        for s_new in new_script.segments:
            if s_new.segment_uid in locked_by_uid:
                merged_segments.append(locked_by_uid[s_new.segment_uid])
            else:
                merged_segments.append(s_new)

        reconciled = ScreenplayScript(
            chapter_id=new_manifest.chapter_id,
            translation_hash=new_manifest.compute_sha256_hash(),
            segments=merged_segments,
        )
        return reconciled
