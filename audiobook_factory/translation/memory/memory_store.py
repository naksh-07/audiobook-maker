#!/usr/bin/env python3
"""
Audiobook Factory - Versioned & Auditable Memory Store (Memory 2.0).
Maintains dynamic CharacterState, DynamicRelationshipState, KnowledgeFact registry,
WorldState, StoryEvent ledger, and deterministic MemoryCommitRecord history.
"""

from __future__ import annotations
import hashlib
import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

from audiobook_factory.translation.book_bible import BookBible, FlaggedConflict
from audiobook_factory.translation.relationship_state import DynamicRelationshipState
from .events import StoryEvent
from .memory_delta import StateDelta, DeltaDomain, StateDeltaEngine
from .character_memory import CharacterState, KnowledgeFact
from .world_memory import WorldState, LocationState, ObjectState, OrganizationState
from .memory_validator import MemoryValidator, MemoryValidationReport
from .state import (
    apply_character_delta,
    apply_relationship_delta,
    apply_knowledge_delta,
    apply_world_or_narrative_delta,
    record_events_on_timeline,
)

logger = logging.getLogger(__name__)


class MemoryPersistenceError(RuntimeError):
    """Raised when MemoryStore persistence fails, is corrupted, or cannot safely recover state."""
    pass


class MemoryCommitRecord(BaseModel):
    """
    Immutable provenance record for a single scene memory commit.
    """
    memory_version: int
    previous_version: int
    version_hash: str
    scene_id: str
    chapter: int
    source_hash: str
    event_ids: List[str] = Field(default_factory=list)
    state_deltas: List[StateDelta] = Field(default_factory=list)
    rejected_deltas: List[StateDelta] = Field(default_factory=list)
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class MemoryStore(BaseModel):
    """
    Central versioned store for World + Character Memory 2.0.
    Strictly separates Hard Canon (referenced via BookBible) from Dynamic State.
    """
    schema_version: str = "2.0"
    memory_version: int = 0
    version_hash: str = "genesis"
    book_bible_hash: str = ""
    character_states: Dict[str, CharacterState] = Field(default_factory=dict)
    relationships: Dict[str, DynamicRelationshipState] = Field(default_factory=dict)
    facts_registry: Dict[str, KnowledgeFact] = Field(default_factory=dict)
    world_state: WorldState = Field(default_factory=WorldState)
    events: Dict[str, StoryEvent] = Field(default_factory=dict)
    rejected_events: Dict[str, StoryEvent] = Field(default_factory=dict)
    commit_history: List[MemoryCommitRecord] = Field(default_factory=list)
    flagged_conflicts: List[FlaggedConflict] = Field(default_factory=list)

    @staticmethod
    def default_store_path(project_dir: Path) -> Path:
        """Returns canonical disk path for MemoryStore JSON inside a project directory."""
        return Path(project_dir) / "memory" / "memory_store.json"

    def _create_snapshot(self) -> Dict[str, Any]:
        """Creates a deep, isolated snapshot of all mutable state in MemoryStore."""
        return {
            "schema_version": self.schema_version,
            "memory_version": self.memory_version,
            "version_hash": self.version_hash,
            "book_bible_hash": self.book_bible_hash,
            "character_states": {
                k: v.model_copy(deep=True) for k, v in self.character_states.items()
            },
            "relationships": {
                k: v.model_copy(deep=True) for k, v in self.relationships.items()
            },
            "facts_registry": {
                k: v.model_copy(deep=True) for k, v in self.facts_registry.items()
            },
            "world_state": self.world_state.model_copy(deep=True),
            "events": {k: v.model_copy(deep=True) for k, v in self.events.items()},
            "rejected_events": {
                k: v.model_copy(deep=True) for k, v in self.rejected_events.items()
            },
            "commit_history": [c.model_copy(deep=True) for c in self.commit_history],
            "flagged_conflicts": [f.model_copy(deep=True) for f in self.flagged_conflicts],
        }

    def _restore_snapshot(self, snapshot: Dict[str, Any]) -> None:
        """Restores MemoryStore state from a snapshot exactly, leaving zero partial mutation."""
        self.schema_version = snapshot["schema_version"]
        self.memory_version = snapshot["memory_version"]
        self.version_hash = snapshot["version_hash"]
        self.book_bible_hash = snapshot["book_bible_hash"]
        self.character_states = snapshot["character_states"]
        self.relationships = snapshot["relationships"]
        self.facts_registry = snapshot["facts_registry"]
        self.world_state = snapshot["world_state"]
        self.events = snapshot["events"]
        self.rejected_events = snapshot["rejected_events"]
        self.commit_history = snapshot["commit_history"]
        self.flagged_conflicts = snapshot["flagged_conflicts"]

    def resolve_canonical_character_name(
        self,
        raw_name: str,
        book_bible: Optional[BookBible] = None,
    ) -> str:
        """Resolves aliases to canonical character names via BookBible when available."""
        if not raw_name:
            return raw_name
        if book_bible is not None:
            entry = book_bible.find_character(raw_name)
            if entry is not None:
                return entry.canonical_name
        return raw_name.strip()

    def seed_from_book_bible(self, bible: BookBible) -> None:
        """
        Non-destructively seeds initial CharacterState, WorldState, and DynamicRelationshipState
        entries from a canonical BookBible. Existing dynamic mutations are preserved.
        """
        char_iterable = (
            bible.characters.values()
            if isinstance(bible.characters, dict)
            else bible.characters
        )
        for char_entry in char_iterable:
            c_name = char_entry.canonical_name
            if c_name not in self.character_states:
                st = CharacterState(
                    character_name=c_name,
                    last_updated_chapter=char_entry.first_seen_chapter,
                )
                self.character_states[c_name] = st

        for loc_key in bible.locations:
            if loc_key not in self.world_state.location_states:
                self.world_state.location_states[loc_key] = LocationState(
                    location_name=loc_key,
                    atmosphere="neutral",
                    acoustic_env="neutral_room",
                )

        for org_key in bible.organizations:
            if org_key not in self.world_state.organization_states:
                self.world_state.organization_states[org_key] = OrganizationState(
                    organization_name=org_key,
                    status="active",
                    disposition="neutral",
                )

        for obj_key in bible.objects:
            if obj_key not in self.world_state.object_states:
                self.world_state.object_states[obj_key] = ObjectState(
                    object_name=obj_key,
                    condition="intact",
                    status="present",
                )

        for rel in bible.relationships:
            rel_key = f"{rel.from_entity}->{rel.to_entity}"
            if rel_key not in self.relationships:
                self.relationships[rel_key] = DynamicRelationshipState(
                    speaker=rel.from_entity,
                    target=rel.to_entity,
                    respect=max(-5, min(5, rel.respect_level - 2)),
                    familiarity=max(0, min(5, rel.intimacy_level)),
                    tension=max(0, min(5, rel.hostility_level)),
                    power_balance=max(-5, min(5, rel.authority_level)),
                    active_pronoun=rel.current_pronoun or rel.default_pronoun or "tum",
                )

    def get_character_state(
        self,
        name: str,
        book_bible: Optional[BookBible] = None,
    ) -> CharacterState:
        """Retrieves or initializes a CharacterState by canonical name."""
        canon_name = self.resolve_canonical_character_name(name, book_bible)
        if canon_name not in self.character_states:
            self.character_states[canon_name] = CharacterState(character_name=canon_name)
        return self.character_states[canon_name]

    def get_relationship(
        self,
        speaker: str,
        target: str,
        book_bible: Optional[BookBible] = None,
    ) -> Optional[DynamicRelationshipState]:
        """Retrieves the directed relationship state speaker -> target if present."""
        s_canon = self.resolve_canonical_character_name(speaker, book_bible)
        t_canon = self.resolve_canonical_character_name(target, book_bible)
        return self.relationships.get(f"{s_canon}->{t_canon}")

    def commit_scene_memory(
        self,
        scene_id: str,
        chapter: int,
        events: List[StoryEvent],
        deltas: Optional[List[StateDelta]] = None,
        source_text: str = "",
        book_bible: Optional[BookBible] = None,
        location: str = "Unspecified",
        time_marker: str = "Unspecified",
    ) -> MemoryValidationReport:
        """
        Executes the EXTRACT -> CALCULATE DELTAS -> VALIDATE -> COMMIT lifecycle for a scene.
        Guarantees transactional atomicity: if an exception occurs during execution, the
        complete pre-commit state is restored exactly.
        BookBible remains strictly immutable Hard Canon (no dynamic writes back to BookBible).
        """
        snapshot = self._create_snapshot()
        try:
            if book_bible is not None:
                self.seed_from_book_bible(book_bible)

            # Canonicalize participant names in events if BookBible is available
            if book_bible is not None:
                for ev in events:
                    ev.participants = [
                        self.resolve_canonical_character_name(p, book_bible)
                        for p in ev.participants
                    ]
                    if ev.location and ev.location != "Unspecified":
                        p_name = book_bible.find_place(ev.location)
                        if p_name is not None:
                            ev.location = p_name

            if deltas is None:
                candidate_deltas = StateDeltaEngine.compute_deltas_for_events(
                    events=events,
                    character_states=self.character_states,
                    relationships=self.relationships,
                    facts_registry=self.facts_registry,
                    world_state=self.world_state,
                )
            else:
                candidate_deltas = list(deltas)

            events_by_id = {e.event_id: e for e in events}
            events_by_id.update(self.events)

            validation_report = MemoryValidator.validate_deltas(
                deltas=candidate_deltas,
                book_bible=book_bible,
                character_states=self.character_states,
                relationships=self.relationships,
                facts_registry=self.facts_registry,
                world_state=self.world_state,
                events_by_id=events_by_id,
            )

            rejected_set = set(validation_report.rejected_event_ids)
            accepted_events: List[StoryEvent] = []
            for ev in events:
                if ev.event_id in rejected_set:
                    self.rejected_events[ev.event_id] = ev
                else:
                    self.events[ev.event_id] = ev
                    accepted_events.append(ev)

            # Apply accepted deltas deterministically
            for delta in validation_report.accepted_deltas:
                if delta.domain == DeltaDomain.CHARACTER:
                    apply_character_delta(self.character_states, self.world_state, delta)
                elif delta.domain == DeltaDomain.RELATIONSHIP:
                    apply_relationship_delta(self.relationships, delta)
                elif delta.domain == DeltaDomain.KNOWLEDGE:
                    apply_knowledge_delta(self.facts_registry, self.character_states, delta)
                elif delta.domain in (DeltaDomain.WORLD, DeltaDomain.NARRATIVE):
                    apply_world_or_narrative_delta(self.world_state, self.character_states, delta)

            # Update timeline with accepted scene events only
            eff_location = location
            if eff_location == "Unspecified" and accepted_events:
                for ev in accepted_events:
                    if ev.location and ev.location != "Unspecified":
                        eff_location = ev.location
                        break

            record_events_on_timeline(
                world_state=self.world_state,
                events=accepted_events,
                chapter=chapter,
                scene=scene_id,
                location=eff_location,
                time_marker=time_marker,
            )

            # Record conflicts in MemoryStore
            for fc in validation_report.flagged_conflicts:
                self.flagged_conflicts.append(fc)

            # NOTE: BookBible remains Hard Canon. Dynamic relationship state
            # (active_pronoun, trust, etc.) lives strictly in MemoryStore.relationships.
            # No writes are made back to BookBible.

            # Compute deterministic commit hash & version
            prev_ver = self.memory_version
            next_ver = prev_ver + 1
            src_hash = hashlib.sha256((source_text or f"{chapter}:{scene_id}").encode("utf-8")).hexdigest()[:16]
            delta_digest_payload = json.dumps(
                [d.model_dump() for d in validation_report.accepted_deltas],
                sort_keys=True,
                ensure_ascii=False,
            )
            ver_hash_input = f"{self.version_hash}|{next_ver}|{chapter}|{scene_id}|{src_hash}|{delta_digest_payload}"
            ver_hash = hashlib.sha256(ver_hash_input.encode("utf-8")).hexdigest()[:16]

            commit_record = MemoryCommitRecord(
                memory_version=next_ver,
                previous_version=prev_ver,
                version_hash=ver_hash,
                scene_id=scene_id,
                chapter=chapter,
                source_hash=src_hash,
                event_ids=[e.event_id for e in accepted_events],
                state_deltas=validation_report.accepted_deltas,
                rejected_deltas=validation_report.rejected_deltas,
            )
            self.memory_version = next_ver
            self.version_hash = ver_hash
            self.commit_history.append(commit_record)

            return validation_report
        except Exception:
            self._restore_snapshot(snapshot)
            raise

    def trace_mutations(
        self,
        entity_name: Optional[str] = None,
        chapter: Optional[int] = None,
        scene_id: Optional[str] = None,
        domain: Optional[DeltaDomain] = None,
    ) -> List[StateDelta]:
        """
        Audits committed state deltas filtered by entity_name, chapter, scene_id, or domain.
        """
        results: List[StateDelta] = []
        for commit in self.commit_history:
            if chapter is not None and commit.chapter != chapter:
                continue
            if scene_id is not None and commit.scene_id != scene_id:
                continue
            for d in commit.state_deltas:
                if entity_name is not None and entity_name.lower() not in d.target_entity.lower():
                    continue
                if domain is not None and d.domain != domain:
                    continue
                results.append(d)
        return results

    def save(self, path: Path) -> None:
        """
        Atomically persists MemoryStore to JSON on disk.
        Creates a verified backup copy (.bak) of the existing file before replacing.
        """
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = target.with_suffix(".json.tmp")
        tmp_path.write_text(self.model_dump_json(indent=2), encoding="utf-8")

        # Before replacing target, if target already exists and is non-empty, back it up
        if target.exists() and target.stat().st_size > 0:
            bak_path = target.with_name(target.name + ".bak")
            try:
                shutil.copy2(target, bak_path)
            except Exception as e:
                logger.warning(f"Failed to create backup at {bak_path}: {e}")

        tmp_path.replace(target)

    @classmethod
    def _validate_store_integrity(cls, data: Any, source_path: Path) -> MemoryStore:
        """
        Validates JSON structure, required schema fields, model types, and version consistency.
        """
        if not isinstance(data, dict):
            raise ValueError(f"Root JSON at {source_path} must be an object, got {type(data).__name__}")

        schema_ver = data.get("schema_version")
        if not schema_ver or str(schema_ver) not in ("2.0", "2.0.0"):
            raise ValueError(f"Incompatible or missing schema_version '{schema_ver}' in {source_path} (expected '2.0')")

        for field in ("character_states", "relationships", "facts_registry", "world_state", "events", "commit_history"):
            if field not in data:
                raise ValueError(f"Corrupted MemoryStore structure: missing essential field '{field}' in {source_path}")

        store = cls.model_validate(data)

        # Integrity check: commit_history version consistency
        if store.memory_version > 0 and store.commit_history:
            last_commit = store.commit_history[-1]
            if last_commit.memory_version != store.memory_version:
                raise ValueError(
                    f"Integrity check failed in {source_path}: store.memory_version={store.memory_version} "
                    f"does not match latest commit version {last_commit.memory_version}"
                )

        return store

    @classmethod
    def load(cls, path: Path, book_bible: Optional[BookBible] = None) -> MemoryStore:
        """
        Loads MemoryStore from disk or initializes a fresh store seeded from BookBible.
        Never silently resets to a fresh store when the primary file is corrupted.
        Attempts recovery from a validated backup (.bak), and fails closed with clear
        diagnostics if unrecoverable.
        """
        target = Path(path)
        if not target.exists():
            store = cls()
            if book_bible is not None:
                store.seed_from_book_bible(book_bible)
            return store

        # Primary load attempt
        primary_err: Optional[Exception] = None
        try:
            raw_text = target.read_text(encoding="utf-8")
            if not raw_text.strip():
                raise ValueError("Empty primary MemoryStore file (0 bytes)")
            raw = json.loads(raw_text)
            store = cls._validate_store_integrity(raw, target)
            if book_bible is not None:
                store.seed_from_book_bible(book_bible)
            return store
        except Exception as e:
            primary_err = e
            logger.error(
                f"[MemoryStore] Primary memory file at '{target}' is corrupted or invalid: {e}. "
                f"Attempting recovery from backup."
            )

        # Recovery attempt from backup
        bak_candidates = [
            target.with_name(target.name + ".bak"),
            target.with_suffix(".bak"),
        ]
        backup_err: Optional[Exception] = None
        for bak_path in bak_candidates:
            if bak_path.exists():
                try:
                    bak_text = bak_path.read_text(encoding="utf-8")
                    if not bak_text.strip():
                        raise ValueError("Backup file is empty (0 bytes)")
                    bak_raw = json.loads(bak_text)
                    recovered_store = cls._validate_store_integrity(bak_raw, bak_path)
                    if book_bible is not None:
                        recovered_store.seed_from_book_bible(book_bible)
                    logger.warning(
                        f"[MemoryStore] Successfully recovered MemoryStore from backup at '{bak_path}' "
                        f"following primary file corruption."
                    )
                    return recovered_store
                except Exception as b_err:
                    backup_err = b_err
                    logger.error(
                        f"[MemoryStore] Backup file at '{bak_path}' failed integrity validation: {b_err}"
                    )

        # Both primary failed and backup missing/failed -> FAIL CLOSED
        diag_msg = (
            f"Failed to load MemoryStore from '{target}'. Primary file is corrupted/unreadable: {primary_err}. "
        )
        if backup_err:
            diag_msg += f"Backup file also failed validation: {backup_err}. "
        else:
            diag_msg += "No valid backup (.bak) file found. "
        diag_msg += "Silent reset is prevented to protect narrative continuity and character state."

        raise MemoryPersistenceError(diag_msg) from primary_err
