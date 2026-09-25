#!/usr/bin/env python3
"""
Audiobook Factory - Story Event & Change-Triggered Event Extraction Engine (Memory 2.0).
Defines deterministic, serializable StoryEvent models with provenance, temporal mode
(narrative order vs. story chronology), and narrative salience scoring.
Implements deterministic scene-change detection first, invoking semantic LLM extraction
only for state-changing or ambiguous scenes with automatic deterministic fallback.
"""

from __future__ import annotations
import re
import json
import hashlib
from enum import Enum
from typing import Dict, Any, List, Optional, Callable, Tuple
from pydantic import BaseModel, Field, model_validator, AliasChoices


class StoryEventType(str, Enum):
    CHARACTER_INTRODUCED = "CHARACTER_INTRODUCED"
    CHARACTER_MOVED = "CHARACTER_MOVED"
    CHARACTER_INJURED = "CHARACTER_INJURED"
    CHARACTER_RECOVERED = "CHARACTER_RECOVERED"
    CHARACTER_DIED = "CHARACTER_DIED"
    SECRET_REVEALED = "SECRET_REVEALED"
    FACT_LEARNED = "FACT_LEARNED"
    KNOWLEDGE_LEARNED = "FACT_LEARNED"
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
    PROMISE_MADE = "PROMISE_CREATED"
    PROMISE_BROKEN = "PROMISE_BROKEN"
    MYSTERY_INTRODUCED = "MYSTERY_INTRODUCED"
    MYSTERY_RESOLVED = "MYSTERY_RESOLVED"
    GOAL_CHANGED = "GOAL_CHANGED"
    GOAL_UPDATED = "GOAL_CHANGED"
    BELIEF_CHANGED = "BELIEF_CHANGED"
    WORLD_STATE_CHANGED = "WORLD_STATE_CHANGED"
    OTHER = "OTHER"


class TemporalMode(str, Enum):
    """
    Distinguishes narrative presentation order from in-universe story chronology.
    Supports flashbacks, memories, dreams, historical lore, and non-linear frames
    without triggering false timeline or dead-character contradictions.
    """
    PRESENT = "PRESENT"
    FLASHBACK = "FLASHBACK"
    MEMORY_DREAM = "MEMORY_DREAM"
    HISTORICAL_NARRATION = "HISTORICAL_NARRATION"
    NON_LINEAR = "NON_LINEAR"


HIGH_SALIENCE_EVENT_TYPES = {
    StoryEventType.CHARACTER_DIED,
    StoryEventType.CHARACTER_INJURED,
    StoryEventType.SECRET_REVEALED,
    StoryEventType.PROMISE_CREATED,
    StoryEventType.PROMISE_BROKEN,
    StoryEventType.RELATIONSHIP_CHANGED,
    StoryEventType.BETRAYAL,
    StoryEventType.RECONCILIATION,
    StoryEventType.ROMANTIC_CONFESSION,
    StoryEventType.SHARED_DANGER,
    StoryEventType.OBJECT_TRANSFERRED,
    StoryEventType.MYSTERY_RESOLVED,
    StoryEventType.WORLD_STATE_CHANGED,
}


class StoryEvent(BaseModel):
    event_id: str = ""
    chapter: int = Field(default=1, ge=1)
    scene: str = "scene_001"
    event_type: StoryEventType = StoryEventType.OTHER
    description: str
    participants: List[str] = Field(default_factory=list)
    location: str = "Unspecified"
    source_reference: str = ""
    evidence_text: str = ""
    importance: int = Field(default=3, ge=1, le=5)
    consequences: List[str] = Field(default_factory=list)

    # Structured domain update payloads (optional)
    character_updates: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    relationship_impacts: List[Dict[str, Any]] = Field(default_factory=list)
    knowledge_updates: List[Dict[str, Any]] = Field(default_factory=list)
    world_updates: Dict[str, Any] = Field(default_factory=dict)
    narrative_updates: Dict[str, Any] = Field(default_factory=dict)

    # Non-linear chronology metadata (Narrative Order vs Story Chronology)
    temporal_mode: TemporalMode = TemporalMode.PRESENT
    chronological_epoch: Optional[int] = None
    story_time_reference: Optional[str] = ""

    # Narrative Salience / Dramatic Memory metadata
    salience_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        validation_alias=AliasChoices("salience_score", "salience"),
    )
    emotional_valence: Any = 0.0
    dramatic_tags: List[str] = Field(default_factory=list)
    is_resolved: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def salience(self) -> float:
        return self.salience_score

    @model_validator(mode="after")
    def ensure_deterministic_id_and_salience(self) -> "StoryEvent":
        if not self.event_id or not self.event_id.strip():
            part_key = ",".join(sorted(p.strip().lower() for p in self.participants if p))
            raw = f"{self.chapter}:{self.scene}:{self.event_type.value}:{part_key}:{self.description.strip().lower()}"
            digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8]
            clean_scene = re.sub(r"[^a-zA-Z0-9_]", "_", self.scene)
            self.event_id = f"evt_c{self.chapter:03d}_{clean_scene}_{digest}"

        # Normalize emotional_valence and dramatic_tags defaults
        if self.emotional_valence in ("neutral", 0.0):
            if self.event_type in (
                StoryEventType.BETRAYAL,
                StoryEventType.CHARACTER_DIED,
                StoryEventType.CHARACTER_INJURED,
                StoryEventType.PROMISE_BROKEN,
            ):
                self.emotional_valence = -0.8
            elif self.event_type in (
                StoryEventType.RECONCILIATION,
                StoryEventType.ROMANTIC_CONFESSION,
                StoryEventType.CHARACTER_RECOVERED,
            ):
                self.emotional_valence = 0.7
            else:
                self.emotional_valence = 0.0

        if not self.dramatic_tags:
            tag_map = {
                StoryEventType.BETRAYAL: ["betrayal", "conflict"],
                StoryEventType.CHARACTER_DIED: ["death", "trauma"],
                StoryEventType.CHARACTER_INJURED: ["injury", "danger"],
                StoryEventType.PROMISE_CREATED: ["oath", "promise"],
                StoryEventType.SECRET_REVEALED: ["secret", "revelation"],
                StoryEventType.RECONCILIATION: ["reconciliation", "bond"],
                StoryEventType.ROMANTIC_CONFESSION: ["intimacy", "bond"],
            }
            if self.event_type in tag_map:
                self.dramatic_tags = list(tag_map[self.event_type])

        # Compute deterministic salience score if left at default 0.5
        if self.salience_score == 0.5:
            base = (self.importance / 5.0) * 0.75
            if self.event_type in HIGH_SALIENCE_EVENT_TYPES:
                base = min(1.0, base + 0.12)
            if not self.is_resolved and self.event_type in (
                StoryEventType.SECRET_REVEALED,
                StoryEventType.PROMISE_CREATED,
                StoryEventType.CHARACTER_INJURED,
                StoryEventType.BETRAYAL,
                StoryEventType.CHARACTER_DIED,
            ):
                base = min(1.0, base + 0.05)
            self.salience_score = round(max(0.1, min(1.0, base)), 2)
        return self


class SceneChangeAssessment(BaseModel):
    has_state_change: bool = False
    is_ambiguous: bool = False
    requires_llm_extraction: bool = False
    temporal_mode: TemporalMode = TemporalMode.PRESENT
    triggers: List[str] = Field(default_factory=list)
    deterministic_events: List[StoryEvent] = Field(default_factory=list)

    @property
    def detected_triggers(self) -> List[str]:
        return self.triggers


class SceneChangeDetector:
    """
    Fast deterministic pre-analyzer that detects whether a scene contains state mutations
    (injuries, recoveries, deaths, secrets, object transfers, relationship shifts, promises)
    or epistemic/narrative ambiguity requiring semantic LLM extraction.
    """

    NON_LINEAR_PATTERNS = [
        (TemporalMode.FLASHBACK, re.compile(r"\b(?:years ago|years earlier|months earlier|long ago|remembered when|recalled the night|in the past|flashback|childhood memory|memories of when)\b", re.IGNORECASE)),
        (TemporalMode.MEMORY_DREAM, re.compile(r"\b(?:in a dream|nightmare|dreamed that|dreamt of|in the vision|hallucinated)\b", re.IGNORECASE)),
        (TemporalMode.HISTORICAL_NARRATION, re.compile(r"\b(?:according to legend|centuries ago|chronicles tell|ancient history|in the old days)\b", re.IGNORECASE)),
    ]

    INJURY_PATTERNS = re.compile(
        r"\b(?:wounded|injured|injury|injuries|bleeding|stabbed|slashed|shot|fractured|concussion|broken\s+(?:arm|leg|rib|bone)|limping|concussed|poisoned|burned|scarred|blood\s+poured)\b",
        re.IGNORECASE,
    )
    TRANSITIVE_ATTACK_VERBS = re.compile(
        r"\b(?:stabbed|slashed|shot|wounded|injured|killed|slain|murdered|poisoned|struck|attacked)\b",
        re.IGNORECASE,
    )
    MOVEMENT_PATTERNS = re.compile(
        r"\b(?:entered|arrived\s+at|arrived\s+in|walked\s+into|stepped\s+into|traveled\s+to|travelled\s+to|fled\s+to|returned\s+to|left\s+the)\b",
        re.IGNORECASE,
    )
    RECOVERY_PATTERNS = re.compile(
        r"\b(?:healed|recovered|bandaged\s+and\s+rested|cured|strength\s+returned|wounds?\s+closed|fully\s+mended)\b",
        re.IGNORECASE,
    )
    DEATH_PATTERNS = re.compile(
        r"\b(?:died|killed|slain|breathed\s+(?:his|her|their)\s+last|corpse\s+of|fell\s+dead|lifeless\s+body)\b",
        re.IGNORECASE,
    )
    SECRET_KNOWLEDGE_PATTERNS = re.compile(
        r"\b(?:confessed|revealed|secret|discovered\s+that|realized\s+that|learned\s+that|truth\s+about|admitted\s+that|whispered\s+the\s+truth|lied\s+about)\b",
        re.IGNORECASE,
    )
    PROMISE_PATTERNS = re.compile(
        r"\b(?:swore\s+an\s+oath|promised|vowed|pledged|broke\s+(?:his|her|their)\s+(?:promise|oath|word))\b",
        re.IGNORECASE,
    )
    RELATIONSHIP_PATTERNS = re.compile(
        r"\b(?:betrayed|forgave|embraced|kissed|threatened|cursed\s+at|trusted|despised|feared)\b",
        re.IGNORECASE,
    )
    OBJECT_TRANSFER_VERBS = re.compile(
        r"\b(?:handed|gave|took|stole|dropped|lost|found|picked\s+up|Unsheathed|drew|accepted\s+the)\b",
        re.IGNORECASE,
    )

    @classmethod
    def detect_temporal_mode(cls, text: str) -> Tuple[TemporalMode, Optional[int], str]:
        for mode, pattern in cls.NON_LINEAR_PATTERNS:
            m = pattern.search(text or "")
            if m:
                epoch = -1 if mode == TemporalMode.FLASHBACK else (-2 if mode == TemporalMode.HISTORICAL_NARRATION else 0)
                return mode, epoch, m.group(0)
        return TemporalMode.PRESENT, 0, ""

    @classmethod
    def _resolve_victim_and_instigator(
        cls,
        sent: str,
        sent_chars: List[str],
        fallback_chars: List[str],
        verb_match: re.Match,
    ) -> Tuple[str, Optional[str], bool]:
        """
        Resolves the patient/victim vs agent/attacker in sentences with multiple characters.
        In active transitive clauses ('Arjun stabbed Vikram'), the character after the attack verb
        is the victim, and the character before the verb is the instigator.
        In passive clauses ('Vikram was stabbed by Arjun'), the character before 'was/were' is the victim.
        """
        if not sent_chars:
            return (fallback_chars[0] if fallback_chars else "Unknown"), None, len(fallback_chars) > 1
        if len(sent_chars) == 1:
            return sent_chars[0], None, False

        # Multiple characters in the same injury/death sentence -> flag ambiguity for optional LLM refinement
        verb_pos = verb_match.start()
        sent_lower = sent.lower()
        passive_prefix = re.search(r"\b(?:was|were|got|been)\s+$", sent_lower[:verb_pos])

        chars_before = [c for c in sent_chars if sent_lower.find(c.lower()) < verb_pos]
        chars_after = [c for c in sent_chars if sent_lower.find(c.lower()) > verb_pos]

        if not passive_prefix and cls.TRANSITIVE_ATTACK_VERBS.search(verb_match.group(0)) and chars_before and chars_after:
            return chars_after[0], chars_before[0], True

        return sent_chars[0], (sent_chars[1] if len(sent_chars) > 1 else None), True

    @classmethod
    def assess_scene(
        cls,
        scene_text: str,
        known_characters: Optional[List[str]] = None,
        chapter: int = 1,
        scene_id: str = "scene_001",
        active_characters: Optional[List[str]] = None,
        location: str = "Unspecified",
        known_objects: Optional[List[str]] = None,
        previous_location: Optional[str] = None,
    ) -> SceneChangeAssessment:
        chars = list(active_characters or known_characters or [])
        objs = list(known_objects or [])
        temporal_mode, chrono_epoch, time_ref = cls.detect_temporal_mode(scene_text)
        triggers: List[str] = []
        events: List[StoryEvent] = []
        is_ambiguous = False

        # 1. Location movement check (explicit scene header transition)
        if location and location not in ("Unspecified", "Unspecified Setting", "Unknown"):
            if previous_location and previous_location not in ("Unspecified", "Unspecified Setting", "Unknown") and location.lower() != previous_location.lower():
                triggers.append(f"location_shift:{previous_location}->{location}")
                events.append(
                    StoryEvent(
                        chapter=chapter,
                        scene=scene_id,
                        event_type=StoryEventType.CHARACTER_MOVED,
                        description=f"Characters moved from {previous_location} to {location}.",
                        participants=chars,
                        location=location,
                        source_reference=f"{scene_id}:location_transition",
                        importance=2,
                        temporal_mode=temporal_mode,
                        chronological_epoch=chrono_epoch,
                        story_time_reference=time_ref,
                        consequences=[f"Current location is now {location}"],
                        metadata={"from_location": previous_location, "to_location": location},
                    )
                )

        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", scene_text) if s.strip()]
        for idx, sent in enumerate(sentences, 1):
            # Sort matched characters by their actual appearance index in the sentence
            matched_with_pos = []
            for c in chars:
                m_c = re.search(rf"\b{re.escape(c)}\b", sent, re.IGNORECASE)
                if m_c:
                    matched_with_pos.append((m_c.start(), c))
            matched_with_pos.sort(key=lambda pair: pair[0])
            sent_chars = [pair[1] for pair in matched_with_pos]

            primary_participants = sent_chars if sent_chars else chars[:2]
            ref = f"{scene_id}_s{idx:03d}"

            # Check intra-scene movement verbs (e.g. "Arjun entered the Courtyard", "left the Courtyard and arrived at the Palace")
            m_move = cls.MOVEMENT_PATTERNS.search(sent)
            if m_move:
                to_match = re.search(
                    r"\b(?:entered|arrived\s+at|arrived\s+in|walked\s+into|stepped\s+into|traveled\s+to|travelled\s+to|fled\s+to|returned\s+to)\s+(?:the\s+)?([A-Z][a-zA-Z0-9_-]*(?:\s+[A-Z][a-zA-Z0-9_-]*)*)",
                    sent,
                )
                from_match = re.search(
                    r"\b(?:left|departed(?:\s+from)?|fled\s+from)\s+(?:the\s+)?([A-Z][a-zA-Z0-9_-]*(?:\s+[A-Z][a-zA-Z0-9_-]*)*)",
                    sent,
                )
                to_loc = to_match.group(1).strip() if to_match else (location if location != "Unspecified" else "")
                from_loc = from_match.group(1).strip() if from_match else previous_location
                if to_loc:
                    triggers.append(f"movement:{m_move.group(0).lower()}->{to_loc}")
                    movers = sent_chars if sent_chars else chars[:1]
                    events.append(
                        StoryEvent(
                            chapter=chapter,
                            scene=scene_id,
                            event_type=StoryEventType.CHARACTER_MOVED,
                            description=f"{', '.join(movers) if movers else 'Characters'} moved to {to_loc}: {sent[:120]}",
                            participants=movers,
                            location=to_loc,
                            source_reference=ref,
                            importance=2,
                            temporal_mode=temporal_mode,
                            chronological_epoch=chrono_epoch,
                            story_time_reference=time_ref,
                            consequences=[f"Current location is now {to_loc}"],
                            metadata={"from_location": from_loc, "to_location": to_loc, "allow_intra_scene_travel": True},
                        )
                    )

            # Check injury
            m_inj = cls.INJURY_PATTERNS.search(sent)
            if m_inj:
                triggers.append(f"injury:{m_inj.group(0).lower()}")
                target_char, instigator, ambig = cls._resolve_victim_and_instigator(sent, sent_chars, chars, m_inj)
                if ambig:
                    is_ambiguous = True
                inj_meta: Dict[str, Any] = {
                    "injured_character": target_char,
                    "injury_detail": m_inj.group(0).lower(),
                }
                if instigator:
                    inj_meta["instigator"] = instigator
                events.append(
                    StoryEvent(
                        chapter=chapter,
                        scene=scene_id,
                        event_type=StoryEventType.CHARACTER_INJURED,
                        description=f"{target_char} sustained injury ({m_inj.group(0).lower()}): {sent[:120]}",
                        participants=sent_chars if sent_chars else [target_char],
                        location=location,
                        source_reference=ref,
                        importance=4,
                        temporal_mode=temporal_mode,
                        emotional_valence="pain",
                        dramatic_tags=["injury", "physical_condition"],
                        consequences=[f"{target_char} physical_condition is injured ({m_inj.group(0).lower()})"],
                        metadata=inj_meta,
                    )
                )

            # Check recovery
            m_rec = cls.RECOVERY_PATTERNS.search(sent)
            if m_rec:
                triggers.append(f"recovery:{m_rec.group(0).lower()}")
                target_char = sent_chars[0] if sent_chars else (chars[0] if chars else "Unknown")
                events.append(
                    StoryEvent(
                        chapter=chapter,
                        scene=scene_id,
                        event_type=StoryEventType.CHARACTER_RECOVERED,
                        description=f"{target_char} recovered ({m_rec.group(0).lower()}): {sent[:120]}",
                        participants=[target_char],
                        location=location,
                        source_reference=ref,
                        importance=3,
                        temporal_mode=temporal_mode,
                        emotional_valence="relief",
                        dramatic_tags=["recovery", "physical_condition"],
                        is_resolved=True,
                        consequences=[f"{target_char} physical_condition restored to healthy"],
                        metadata={"recovered_character": target_char},
                    )
                )

            # Check death
            m_death = cls.DEATH_PATTERNS.search(sent)
            if m_death:
                triggers.append(f"death:{m_death.group(0).lower()}")
                is_ambiguous = True  # Death requires high-precision verification
                target_char, instigator, _ = cls._resolve_victim_and_instigator(sent, sent_chars, chars, m_death)
                death_meta: Dict[str, Any] = {"deceased_character": target_char}
                if instigator:
                    death_meta["instigator"] = instigator
                events.append(
                    StoryEvent(
                        chapter=chapter,
                        scene=scene_id,
                        event_type=StoryEventType.CHARACTER_DIED,
                        description=f"{target_char} died: {sent[:120]}",
                        participants=primary_participants,
                        location=location,
                        source_reference=ref,
                        importance=5,
                        temporal_mode=temporal_mode,
                        emotional_valence="tragic",
                        dramatic_tags=["death", "major_turning_point"],
                        consequences=[f"{target_char} is deceased"],
                        metadata=death_meta,
                    )
                )

            # Check secret / knowledge acquisition
            m_sec = cls.SECRET_KNOWLEDGE_PATTERNS.search(sent)
            if m_sec:
                triggers.append(f"epistemic:{m_sec.group(0).lower()}")
                is_ambiguous = True  # Epistemic boundaries benefit from semantic parsing
                knower = sent_chars[0] if sent_chars else (chars[0] if chars else "Narrator")
                ev_type = StoryEventType.SECRET_REVEALED if "secret" in m_sec.group(0).lower() or "confessed" in m_sec.group(0).lower() else StoryEventType.FACT_LEARNED
                events.append(
                    StoryEvent(
                        chapter=chapter,
                        scene=scene_id,
                        event_type=ev_type,
                        description=f"{knower} learned/revealed knowledge: {sent[:120]}",
                        participants=primary_participants,
                        location=location,
                        source_reference=ref,
                        importance=4,
                        temporal_mode=temporal_mode,
                        dramatic_tags=["epistemic", "secret"],
                        consequences=[f"{knower} knows fact from {ref}"],
                        metadata={
                            "knower": knower,
                            "witnesses": primary_participants,
                            "fact_summary": sent[:140],
                            "epistemic_status": "FALSE_BELIEF" if "lied" in m_sec.group(0).lower() else "KNOWN",
                        },
                    )
                )

            # Check promises
            m_prom = cls.PROMISE_PATTERNS.search(sent)
            if m_prom:
                triggers.append(f"promise:{m_prom.group(0).lower()}")
                broken = "broke" in m_prom.group(0).lower()
                events.append(
                    StoryEvent(
                        chapter=chapter,
                        scene=scene_id,
                        event_type=StoryEventType.PROMISE_BROKEN if broken else StoryEventType.PROMISE_CREATED,
                        description=f"Promise {'broken' if broken else 'created'}: {sent[:120]}",
                        participants=primary_participants,
                        location=location,
                        source_reference=ref,
                        importance=4,
                        temporal_mode=temporal_mode,
                        dramatic_tags=["promise", "oath"],
                        is_resolved=broken,
                        consequences=[sent[:120]],
                        metadata={"promise_text": sent[:140], "broken": broken},
                    )
                )

            # Check relationship shift
            m_rel = cls.RELATIONSHIP_PATTERNS.search(sent)
            if m_rel and len(primary_participants) >= 2:
                word = m_rel.group(0).lower()
                triggers.append(f"relationship:{word}")
                is_ambiguous = True
                interaction_kind = "other"
                if "betray" in word:
                    interaction_kind = "betrayal"
                elif "forgave" in word:
                    interaction_kind = "reconciliation"
                elif "kiss" in word or "embrac" in word:
                    interaction_kind = "romantic_confession"
                elif "threaten" in word or "fear" in word:
                    interaction_kind = "threat"
                elif "cursed" in word or "despis" in word:
                    interaction_kind = "insult"
                elif "trust" in word:
                    interaction_kind = "shared_danger"

                ev_rel_type_map = {
                    "betrayal": StoryEventType.BETRAYAL,
                    "reconciliation": StoryEventType.RECONCILIATION,
                    "romantic_confession": StoryEventType.ROMANTIC_CONFESSION,
                    "shared_danger": StoryEventType.SHARED_DANGER,
                    "threat": StoryEventType.THREAT_ISSUED,
                }
                rel_ev_type = ev_rel_type_map.get(interaction_kind, StoryEventType.RELATIONSHIP_CHANGED)

                events.append(
                    StoryEvent(
                        chapter=chapter,
                        scene=scene_id,
                        event_type=rel_ev_type,
                        description=f"Relationship shift ({interaction_kind}) between {primary_participants[0]} and {primary_participants[1]}: {sent[:120]}",
                        participants=primary_participants[:2],
                        location=location,
                        source_reference=ref,
                        importance=4 if interaction_kind in ("betrayal", "romantic_confession") else 3,
                        temporal_mode=temporal_mode,
                        dramatic_tags=["relationship", interaction_kind],
                        consequences=[f"Relationship {primary_participants[0]}->{primary_participants[1]} shifted via {interaction_kind}"],
                        metadata={
                            "speaker": primary_participants[0],
                            "target": primary_participants[1],
                            "interaction_type": interaction_kind,
                        },
                    )
                )

            # Check object interaction
            if objs:
                matched_objs = [o for o in objs if re.search(rf"\b{re.escape(o)}\b", sent, re.IGNORECASE)]
                if matched_objs and cls.OBJECT_TRANSFER_VERBS.search(sent):
                    verb = cls.OBJECT_TRANSFER_VERBS.search(sent).group(0).lower()
                    obj_name = matched_objs[0]
                    triggers.append(f"object:{obj_name}:{verb}")
                    if any(v in verb for v in ("dropped", "lost")):
                        ev_t = StoryEventType.OBJECT_LOST
                    elif any(v in verb for v in ("handed", "gave")) and len(primary_participants) >= 2:
                        ev_t = StoryEventType.OBJECT_TRANSFERRED
                    else:
                        ev_t = StoryEventType.OBJECT_ACQUIRED

                    events.append(
                        StoryEvent(
                            chapter=chapter,
                            scene=scene_id,
                            event_type=ev_t,
                            description=f"Object '{obj_name}' ({verb}): {sent[:120]}",
                            participants=primary_participants,
                            location=location,
                            source_reference=ref,
                            importance=3,
                            temporal_mode=temporal_mode,
                            dramatic_tags=["object", obj_name],
                            consequences=[f"Object {obj_name} state updated ({ev_t.value})"],
                            metadata={
                                "object_name": obj_name,
                                "from_character": primary_participants[0] if len(primary_participants) >= 2 and ev_t == StoryEventType.OBJECT_TRANSFERRED else None,
                                "to_character": primary_participants[1] if len(primary_participants) >= 2 and ev_t == StoryEventType.OBJECT_TRANSFERRED else (primary_participants[0] if primary_participants else None),
                            },
                        )
                    )

        has_change = len(events) > 0
        requires_llm = has_change and is_ambiguous

        return SceneChangeAssessment(
            has_state_change=has_change,
            is_ambiguous=is_ambiguous,
            requires_llm_extraction=requires_llm,
            temporal_mode=temporal_mode,
            triggers=triggers,
            deterministic_events=events,
        )


class EventExtractor:
    """
    Hybrid Event Extractor:
    1. Runs deterministic SceneChangeDetector first (0 LLM tokens).
    2. Invokes semantic LLM extraction ONLY when the scene is flagged as state-changing/ambiguous
       (or when force_llm=True) and a callable LLM function is provided.
    3. Automatically falls back to deterministic events on rate limits, parse errors, or offline runs.
    """

    @classmethod
    def extract_scene_events(
        cls,
        scene_text: str,
        chapter: int = 1,
        scene_id: str = "scene_001",
        active_characters: Optional[List[str]] = None,
        known_characters: Optional[List[str]] = None,
        location: str = "Unspecified",
        known_objects: Optional[List[str]] = None,
        previous_location: Optional[str] = None,
        call_llm_fn: Optional[Callable[..., str]] = None,
        model: Optional[str] = None,
        force_llm: bool = False,
    ) -> Tuple[List[StoryEvent], SceneChangeAssessment]:
        eff_chars = active_characters if active_characters is not None else known_characters
        assessment = SceneChangeDetector.assess_scene(
            scene_text=scene_text,
            chapter=chapter,
            scene_id=scene_id,
            active_characters=eff_chars,
            location=location,
            known_objects=known_objects,
            previous_location=previous_location,
        )

        if call_llm_fn is not None and (assessment.requires_llm_extraction or force_llm):
            try:
                llm_events = cls.propose_events_llm(
                    scene_text=scene_text,
                    chapter=chapter,
                    scene_id=scene_id,
                    active_characters=eff_chars or [],
                    location=location,
                    default_temporal_mode=assessment.temporal_mode,
                    call_llm_fn=call_llm_fn,
                )
                if llm_events:
                    # Prefer rich LLM semantic events and retain only non-overlapping deterministic events
                    llm_types = {le.event_type for le in llm_events}
                    deduped: List[StoryEvent] = list(llm_events)
                    seen_ids = {le.event_id for le in llm_events}
                    for de in assessment.deterministic_events:
                        if de.event_id not in seen_ids and de.event_type not in llm_types:
                            deduped.append(de)
                            seen_ids.add(de.event_id)
                    return deduped, assessment
            except Exception:
                # Graceful fallback to deterministic extraction on rate limits / errors
                pass

        return assessment.deterministic_events, assessment

    @classmethod
    def propose_events_llm(
        cls,
        scene_text: str,
        chapter: int,
        scene_id: str,
        active_characters: List[str],
        location: str,
        default_temporal_mode: TemporalMode,
        call_llm_fn: Callable[..., str],
    ) -> List[StoryEvent]:
        """
        Requests candidate StoryEvents from the LLM for state-changing or ambiguous scenes.
        The LLM only proposes candidate events; deterministic validation governs commit.
        """
        valid_types = ", ".join(t.value for t in StoryEventType)
        valid_modes = ", ".join(m.value for m in TemporalMode)
        chars_str = ", ".join(active_characters) if active_characters else "Unknown"

        system_instruction = (
            "You are a narrative continuity analyst extracting structured story events from a novel scene. "
            "Only propose events that actually cause narrative, physical, epistemic, relationship, or world-state changes. "
            "Distinguish PRESENT story events from FLASHBACK, MEMORY_DREAM, or HISTORICAL_NARRATION. "
            "Output valid JSON only."
        )

        prompt = f"""Chapter: {chapter} | Scene: {scene_id} | Location: {location}
Active Characters: {chars_str}
Detected Temporal Mode Hint: {default_temporal_mode.value}

Scene Text:
\"\"\"
{scene_text[:4500]}
\"\"\"

Return a JSON object with an "events" array where each item has:
- "event_type": one of [{valid_types}]
- "description": concise factual summary of what happened
- "participants": list of canonical character names involved
- "location": scene location
- "source_reference": brief quote or beat reference
- "importance": integer 1 to 5
- "temporal_mode": one of [{valid_modes}]
- "emotional_valence": string (e.g. "neutral", "pain", "betrayal", "relief", "dread", "intimate")
- "dramatic_tags": list of short tags (e.g. ["injury", "secret", "betrayal", "oath", "turning_point"])
- "consequences": list of state consequences
- "metadata": optional object with structured keys (e.g. {{"injured_character": "...", "injury_detail": "..."}}, {{"knower": "...", "witnesses": [...], "fact_summary": "..."}}, {{"speaker": "...", "target": "...", "interaction_type": "..."}})
"""
        raw_resp = call_llm_fn(
            prompt=prompt,
            system_instruction=system_instruction,
            json_mode=True,
        )
        cleaned = raw_resp.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned).strip()

        parsed = json.loads(cleaned)
        raw_list = parsed.get("events", parsed) if isinstance(parsed, dict) else parsed
        if not isinstance(raw_list, list):
            return []

        results: List[StoryEvent] = []
        for item in raw_list:
            if not isinstance(item, dict) or not item.get("description"):
                continue
            raw_type = str(item.get("event_type", "OTHER")).upper()
            ev_type = StoryEventType(raw_type) if raw_type in StoryEventType.__members__ else StoryEventType.OTHER

            raw_mode = str(item.get("temporal_mode", default_temporal_mode.value)).upper()
            t_mode = TemporalMode(raw_mode) if raw_mode in TemporalMode.__members__ else default_temporal_mode

            results.append(
                StoryEvent(
                    chapter=chapter,
                    scene=scene_id,
                    event_type=ev_type,
                    description=str(item["description"]),
                    participants=[str(p) for p in item.get("participants", []) if p],
                    location=str(item.get("location") or location or "Unspecified"),
                    source_reference=str(item.get("source_reference") or scene_id),
                    importance=max(1, min(5, int(item.get("importance", 3)))),
                    temporal_mode=t_mode,
                    emotional_valence=str(item.get("emotional_valence", "neutral")),
                    dramatic_tags=[str(t) for t in item.get("dramatic_tags", []) if t],
                    consequences=[str(c) for c in item.get("consequences", []) if c],
                    metadata=item.get("metadata", {}) if isinstance(item.get("metadata"), dict) else {},
                )
            )
        return results
