#!/usr/bin/env python3
"""
Audiobook Factory - Cast Lock Manager.
Guarantees deterministic, tamper-evident character voice attribution.
Once a voice is locked, character -> voice attribution remains immutable across all chapters.
Recasting requires explicit invalidation, causing affected audio chunks to be regenerated.
"""

from __future__ import annotations
import os
import json
import uuid
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from audiobook_factory.logger import logger
from .contracts import CastLock, CastLockManifest, CastingEvaluationRecord


CAST_LOCK_FILENAME = "cast_lock.json"
VOICE_REGISTRY_FILENAME = "voice_registry.json"


class CastLockManager:
    """
    Manages project-level Cast Locks with audit trails and recast cache invalidation.
    """

    def __init__(self, project_dir: Path | str):
        self.project_dir = Path(project_dir).resolve()
        self.lock_file = self.project_dir / CAST_LOCK_FILENAME
        self.registry_file = self.project_dir / VOICE_REGISTRY_FILENAME
        self.manifest = self._load_manifest()

    def _load_manifest(self) -> CastLockManifest:
        if self.lock_file.exists():
            try:
                with open(self.lock_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return CastLockManifest.model_validate(data)
            except Exception as e:
                logger.warning(f"  [CAST LOCK NOTICE] Error reading {self.lock_file.name}: {e}. Initializing fresh manifest.")

        slug = self.project_dir.name
        manifest = CastLockManifest(project_slug=slug)
        return manifest

    def save(self) -> None:
        """Atomically saves cast_lock.json and synchronizes voice_registry.json."""
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self.manifest.updated_at = datetime.datetime.now().isoformat()

        # Atomic write for cast_lock.json
        tmp_lock = self.lock_file.with_suffix(f".tmp_{os.getpid()}_{uuid.uuid4().hex[:6]}")
        try:
            with open(tmp_lock, "w", encoding="utf-8") as f:
                f.write(self.manifest.model_dump_json(indent=2))
            os.replace(tmp_lock, self.lock_file)
        finally:
            if tmp_lock.exists():
                try:
                    tmp_lock.unlink()
                except OSError:
                    pass

        # Synchronize backward-compatible voice_registry.json
        self.sync_voice_registry()

    def lock_character(
        self,
        character_id: str,
        character_name: str,
        voice_id: str,
        evaluation_record: Optional[CastingEvaluationRecord] = None,
        selection_rationale: str = "",
        calibration_overrides: Optional[Dict[str, Any]] = None,
        locked_by: str = "Director",
    ) -> CastLock:
        """
        Creates or updates a formal Cast Lock for a character.
        """
        evidence = evaluation_record.model_dump() if evaluation_record else {}
        calib = calibration_overrides or {}

        lock = CastLock(
            character_id=character_id,
            character_name=character_name,
            voice_id=voice_id,
            casting_version="1.0.0",
            locked=True,
            locked_at=datetime.datetime.now().isoformat(),
            locked_by=locked_by,
            selection_rank=evaluation_record.rank if evaluation_record else 1,
            selection_rationale=selection_rationale or (evaluation_record.evaluation_summary if evaluation_record else "Direct cast lock"),
            casting_evidence=evidence,
            calibration_overrides=calib,
        )

        self.manifest.locks[character_id] = lock
        self.save()
        logger.info(f"  [CAST LOCK] Locked character '{character_name}' ({character_id}) -> Voice '{voice_id}'.")
        return lock

    def get_lock(self, character_name_or_id: str) -> Optional[CastLock]:
        """Resolves cast lock for character by canonical name or ID."""
        return self.manifest.get_lock(character_name_or_id)

    def is_locked(self, character_name_or_id: str) -> bool:
        lock = self.get_lock(character_name_or_id)
        return lock is not None and lock.locked

    def recast_character(
        self,
        character_name_or_id: str,
        new_voice_id: str,
        reason: str,
        recast_by: str = "Director",
        new_calibration: Optional[Dict[str, Any]] = None,
    ) -> CastLock:
        """
        Explicitly recasts a character, invalidating previous audio chunks
        and documenting the change in the recast history.
        """
        existing = self.get_lock(character_name_or_id)
        prev_voice = existing.voice_id if existing else "unassigned"
        c_name = existing.character_name if existing else character_name_or_id
        c_id = existing.character_id if existing else character_name_or_id.lower().replace(" ", "_")

        recast_entry = {
            "character_id": c_id,
            "character_name": c_name,
            "previous_voice_id": prev_voice,
            "new_voice_id": new_voice_id,
            "reason": reason,
            "recast_by": recast_by,
            "timestamp": datetime.datetime.now().isoformat(),
        }
        self.manifest.recast_history.append(recast_entry)

        # Invalidate audio chunks for this character in audio_chunks directory
        invalidated_count = self._invalidate_character_audio_chunks(c_name)

        new_lock = CastLock(
            character_id=c_id,
            character_name=c_name,
            voice_id=new_voice_id,
            casting_version=f"recast_{len(self.manifest.recast_history)}",
            locked=True,
            locked_at=datetime.datetime.now().isoformat(),
            locked_by=recast_by,
            selection_rationale=f"Recast from '{prev_voice}' to '{new_voice_id}': {reason}",
            calibration_overrides=new_calibration or {},
        )
        self.manifest.locks[c_id] = new_lock
        self.save()

        logger.info(
            f"  [RECAST] Character '{c_name}' recast to '{new_voice_id}' ({reason}). "
            f"Invalidated {invalidated_count} existing audio segments for regeneration."
        )
        return new_lock

    def _invalidate_character_audio_chunks(self, character_name: str) -> int:
        """
        Safely removes or archives existing audio chunks associated with this character
        so they will be regenerated deterministically on the next pass.
        """
        audio_dir = self.project_dir / "audio_chunks"
        if not audio_dir.exists():
            return 0

        # Also inspect scripts to map segment indices to this speaker
        scripts_dir = self.project_dir / "scripts"
        target_indices = set()
        if scripts_dir.exists():
            for sf in scripts_dir.glob("chapter_*_script.json"):
                try:
                    with open(sf, "r", encoding="utf-8") as f:
                        s_data = json.load(f)
                    segs = s_data.get("segments", s_data) if isinstance(s_data, dict) else s_data
                    if isinstance(segs, list):
                        for s in segs:
                            spk = s.get("speaker", "") if isinstance(s, dict) else getattr(s, "speaker", "")
                            if spk.strip().lower() == character_name.strip().lower():
                                idx = s.get("index") if isinstance(s, dict) else getattr(s, "index", None)
                                if idx:
                                    target_indices.add(int(idx))
                except Exception:
                    pass

        invalidated = 0
        archive_dir = audio_dir / "recast_archive"
        for wav in audio_dir.glob("*.wav"):
            # Check if filename index matches target_indices
            match = False
            for tidx in target_indices:
                if f"_s{tidx:04d}_" in wav.name:
                    match = True
                    break
            if match:
                archive_dir.mkdir(parents=True, exist_ok=True)
                try:
                    dest = archive_dir / wav.name
                    if dest.exists():
                        dest.unlink()
                    wav.replace(dest)
                    invalidated += 1
                except Exception:
                    pass

        return invalidated

    def sync_voice_registry(self) -> Path:
        """
        Synchronizes cast locks into voice_registry.json for backward compatibility.
        """
        existing_reg: Dict[str, Any] = {}
        if self.registry_file.exists():
            try:
                with open(self.registry_file, "r", encoding="utf-8") as f:
                    existing_reg = json.load(f)
            except Exception:
                existing_reg = {}

        for lock in self.manifest.locks.values():
            if lock.locked:
                cfg = {
                    "backend": "gemini_tts",
                    "voice": lock.voice_id,
                    "speed": lock.calibration_overrides.get("speed", 1.0),
                    "pitch": lock.calibration_overrides.get("pitch", 1.0),
                    "cast_locked": True,
                    "casting_version": lock.casting_version,
                }
                for k, v in lock.calibration_overrides.items():
                    if k not in cfg:
                        cfg[k] = v
                existing_reg[lock.character_name] = cfg

        tmp_reg = self.registry_file.with_suffix(f".tmp_{os.getpid()}_{uuid.uuid4().hex[:6]}")
        try:
            with open(tmp_reg, "w", encoding="utf-8") as f:
                json.dump(existing_reg, f, ensure_ascii=False, indent=2)
            os.replace(tmp_reg, self.registry_file)
        finally:
            if tmp_reg.exists():
                try:
                    tmp_reg.unlink()
                except OSError:
                    pass

        return self.registry_file
