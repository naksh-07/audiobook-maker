#!/usr/bin/env python3
"""
Audiobook Factory - Persistent Canonical Book Bible.
Serves as the single canonical source of truth for all book-level entities, lore,
relationships, linguistic identities, and world rules.
Maintains legacy glossary.json as an exported projection for downstream compatibility.
"""

from __future__ import annotations
import json
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class BookEntity(BaseModel):
    canonical_id: str
    english_name: str
    hindi_name: str
    aliases: List[str] = Field(default_factory=list)
    category: str = "character"  # character, location, organization, creature, object, title, terminology, lore
    gender: Optional[str] = None  # male, female, other, neutral
    description: str = ""
    first_appearance_chapter: int = 1
    pronunciation_hint: str = ""
    sociolect_archetype: str = "NEUTRAL"
    language_profile: Optional[Dict[str, Any]] = None
    is_canonical: bool = True
    confidence: float = 1.0


class DynamicRelationship(BaseModel):
    from_entity: str
    to_entity: str
    default_pronoun: str = "tum"  # aap, tum, tu
    current_pronoun: str = "tum"
    respect_level: int = 3       # 0 to 5
    intimacy_level: int = 2      # 0 to 5
    hostility_level: int = 0     # 0 to 5
    authority_level: int = 0     # 0 to 5
    notes: str = ""
    evidence_log: List[str] = Field(default_factory=list)


class WorldRule(BaseModel):
    rule_id: str
    category: str  # magic, social_hierarchy, geography, biology
    statement: str
    immutable: bool = True


class FlaggedConflict(BaseModel):
    entity_or_concept: str
    source_chapter: int
    conflict_type: str  # name_spelling, relationship_contradiction, lore_inconsistency
    description: str
    candidate_data: Dict[str, Any]
    resolved: bool = False
    resolution_notes: str = ""


class BookBible(BaseModel):
    schema_version: str = "2.0.0"
    book_title: str = "Unknown"
    author: str = "Unknown"
    narrative_voice: str = "Dark fantasy, cinematic dramatic Hindustani"
    characters: Dict[str, BookEntity] = Field(default_factory=dict)
    locations: Dict[str, str] = Field(default_factory=dict)  # English -> Devanagari
    organizations: Dict[str, str] = Field(default_factory=dict)
    creatures: Dict[str, str] = Field(default_factory=dict)
    objects: Dict[str, str] = Field(default_factory=dict)
    titles: Dict[str, str] = Field(default_factory=dict)
    terminology: Dict[str, str] = Field(default_factory=dict)  # General lore terms
    terminology_variants: Dict[str, str] = Field(default_factory=dict)  # Project forbidden regex variants -> canonical
    relationships: List[DynamicRelationship] = Field(default_factory=list)
    world_rules: List[WorldRule] = Field(default_factory=list)
    flagged_conflicts: List[FlaggedConflict] = Field(default_factory=list)
    candidate_entities: List[BookEntity] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def get_version_hash(self) -> str:
        """Calculates deterministic SHA256 hash of the canonical state for provenance tracking."""
        core_state = {
            "title": self.book_title,
            "characters": {k: v.model_dump() for k, v in sorted(self.characters.items())},
            "terminology": sorted(self.terminology.items()),
            "locations": sorted(self.locations.items()),
            "creatures": sorted(self.creatures.items()),
            "relationships": [r.model_dump() for r in self.relationships],
        }
        dumped = json.dumps(core_state, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(dumped.encode("utf-8")).hexdigest()[:16]

    def get_canonical_lexicon(self) -> Dict[str, str]:
        """Combines all canonical terms, proper nouns, locations, and creature names."""
        lexicon: Dict[str, str] = {}
        for entity in self.characters.values():
            if entity.is_canonical and entity.hindi_name:
                lexicon[entity.english_name] = entity.hindi_name
                for alias in entity.aliases:
                    lexicon[alias] = entity.hindi_name
        lexicon.update(self.locations)
        lexicon.update(self.organizations)
        lexicon.update(self.creatures)
        lexicon.update(self.objects)
        lexicon.update(self.titles)
        lexicon.update(self.terminology)
        return lexicon

    def export_legacy_glossary(self) -> Dict[str, Any]:
        """
        Projects canonical Book Bible state into legacy glossary.json schema.
        Used as a one-way backward-compatibility mirror.
        """
        char_list = []
        for c in self.characters.values():
            if c.is_canonical:
                char_list.append({
                    "english_name": c.english_name,
                    "hindi_name": c.hindi_name,
                    "gender": c.gender or "other",
                    "voice_style": c.description,
                    "recommended_pronoun_level": (
                        c.language_profile.get("honorific_preference", "tum")
                        if c.language_profile else "tum"
                    ),
                    "hindustani_archetype": c.sociolect_archetype,
                })

        rel_list = []
        for r in self.relationships:
            rel_list.append({
                "from": r.from_entity,
                "to": r.to_entity,
                "level": r.current_pronoun,
            })

        loc_and_terms = {}
        loc_and_terms.update(self.locations)
        loc_and_terms.update(self.creatures)
        loc_and_terms.update(self.objects)
        loc_and_terms.update(self.terminology)

        return {
            "characters": char_list,
            "relationships": rel_list,
            "locations_and_terms": loc_and_terms,
            "general_tone": self.narrative_voice,
        }

    def save(self, project_dir: Path):
        """
        Persists canonical state to book_bible.json, and exports legacy projection to glossary.json.
        """
        project_dir = Path(project_dir)
        bible_path = project_dir / "book_bible.json"
        with open(bible_path, "w", encoding="utf-8") as f:
            json.dump(self.model_dump(), f, ensure_ascii=False, indent=2)

        # Mirror projection to translation/glossary.json
        trans_dir = project_dir / "translation"
        trans_dir.mkdir(parents=True, exist_ok=True)
        glossary_path = trans_dir / "glossary.json"
        with open(glossary_path, "w", encoding="utf-8") as f:
            json.dump(self.export_legacy_glossary(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load_from_project(cls, project_dir: Path) -> BookBible:
        """
        Loads canonical book_bible.json if present; otherwise imports from legacy glossary.json.
        """
        project_dir = Path(project_dir)
        bible_path = project_dir / "book_bible.json"
        glossary_path = project_dir / "translation" / "glossary.json"
        meta_path = project_dir / "metadata.json"

        meta: Dict[str, Any] = {}
        if meta_path.exists():
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
            except Exception:
                pass

        if bible_path.exists():
            with open(bible_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls.model_validate(data)

        # Initial import from legacy glossary
        bible = cls(
            book_title=meta.get("title", "Unknown"),
            author=meta.get("author", "Unknown"),
        )
        if glossary_path.exists():
            bible.import_legacy_glossary(glossary_path)
            bible.save(project_dir)
        return bible

    def import_legacy_glossary(self, glossary_path: Path):
        """Initial one-way migration from legacy glossary.json."""
        with open(glossary_path, "r", encoding="utf-8") as f:
            glossary = json.load(f)

        for c in glossary.get("characters", []):
            eng = c.get("english_name", "").strip()
            hi = c.get("hindi_name", "").strip()
            if not eng:
                continue
            entity = BookEntity(
                canonical_id=eng.lower().replace(" ", "_"),
                english_name=eng,
                hindi_name=hi,
                gender=c.get("gender", "male"),
                description=c.get("voice_style", ""),
                sociolect_archetype=c.get("hindustani_archetype", "NEUTRAL"),
                language_profile={
                    "honorific_preference": c.get("recommended_pronoun_level", "tum"),
                    "speech_quirks": c.get("speech_quirks", ""),
                },
                is_canonical=True,
            )
            self.characters[eng] = entity

        for r in glossary.get("relationships", []):
            f_ent = r.get("from", "")
            t_ent = r.get("to", "")
            level = r.get("level", "tum")
            if f_ent and t_ent:
                self.relationships.append(
                    DynamicRelationship(
                        from_entity=f_ent,
                        to_entity=t_ent,
                        default_pronoun=level,
                        current_pronoun=level,
                    )
                )

        terms = glossary.get("locations_and_terms", {})
        for eng, hi in terms.items():
            eng_s = eng.strip()
            hi_s = hi.strip()
            # Heuristic partitioning
            if any(w in eng_s.lower() for w in ("temple", "castle", "forest", "mountain", "mountains", "river", "valley", "kingdom", "tavern", "inn", "street", "road", "gate", "palace", "tower", "city", "village", "town")):
                self.locations[eng_s] = hi_s
            elif any(w in eng_s.lower() for w in ("monster", "beast", "creature", "demon", "dragon", "troll", "vampire", "ghoul", "goblin", "specter", "wraith", "fiend", "hound")):
                self.creatures[eng_s] = hi_s
            elif any(w in eng_s.lower() for w in ("sword", "blade", "medallion", "potion", "elixir", "amulet", "ring", "wand", "staff", "shield", "armor", "dagger")):
                self.objects[eng_s] = hi_s
            else:
                self.terminology[eng_s] = hi_s

        if "general_tone" in glossary:
            self.narrative_voice = glossary["general_tone"]

    def propose_new_entity(self, entity: BookEntity, chapter_num: int) -> bool:
        """
        Auto-commits high-confidence non-conflicting new entities.
        If ambiguity or contradiction is detected, logs a flagged conflict.
        """
        # Check for existing canonical entity with same name
        existing = self.characters.get(entity.english_name)
        if existing:
            # Check for conflict in Hindi spelling or gender
            if existing.hindi_name != entity.hindi_name:
                self.flagged_conflicts.append(
                    FlaggedConflict(
                        entity_or_concept=entity.english_name,
                        source_chapter=chapter_num,
                        conflict_type="name_spelling",
                        description=f"Candidate spelling '{entity.hindi_name}' contradicts canonical '{existing.hindi_name}'",
                        candidate_data=entity.model_dump(),
                    )
                )
                return False
            return True

        # Non-conflicting: auto-commit if confidence is high
        if entity.confidence >= 0.8:
            entity.is_canonical = True
            self.characters[entity.english_name] = entity
            return True
        else:
            self.candidate_entities.append(entity)
            return False
