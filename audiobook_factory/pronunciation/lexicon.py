#!/usr/bin/env python3
"""
Audiobook Factory - Canonical Pronunciation Lexicon.
Central repository for all pronunciation-sensitive entities, tokens, acronyms, and names.
Fully integrates with BookBible, preserves occurrence histories, and enforces manual overrides.
"""

from __future__ import annotations
import os
import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from .contracts import (
    PronunciationEntry,
    PronunciationStatus,
    PronunciationSource,
    SpokenLanguage,
    PronunciationPolicy,
)


class PronunciationLexicon(BaseModel):
    """
    Canonical pronunciation repository for an audiobook production project.
    """
    entries: Dict[str, PronunciationEntry] = Field(default_factory=dict)
    overrides: Dict[str, PronunciationEntry] = Field(default_factory=dict)
    alias_map: Dict[str, str] = Field(default_factory=dict)

    def add_entry(self, entry: PronunciationEntry) -> None:
        """Registers or updates a canonical pronunciation entry."""
        cid = entry.canonical_id
        self.entries[cid] = entry

        # Update alias map
        self.alias_map[cid.lower()] = cid
        self.alias_map[entry.canonical_text.strip().lower()] = cid
        for alias in entry.aliases:
            if alias.strip():
                self.alias_map[alias.strip().lower()] = cid
        for s in entry.surface_forms:
            if s.strip():
                self.alias_map[s.strip().lower()] = cid

    def add_override(
        self,
        token: str,
        spoken_form: str,
        pronunciation_hint: str = "",
        expected_language: SpokenLanguage = SpokenLanguage.HINDI,
        category: str = "custom_override",
    ) -> PronunciationEntry:
        """Adds an absolute priority manual override for an entity or token."""
        cid = token.strip().lower().replace(" ", "_")
        entry = PronunciationEntry(
            canonical_id=cid,
            canonical_text=token.strip(),
            spoken_form=spoken_form.strip(),
            pronunciation_hint=pronunciation_hint.strip() or spoken_form.strip(),
            expected_language=expected_language,
            category=category,
            status=PronunciationStatus.VERIFIED,
            source=PronunciationSource.MANUAL_OVERRIDE,
            policy=PronunciationPolicy.STRICT_CANONICAL,
            notes="Manual book-level pronunciation override",
        )
        self.overrides[cid] = entry
        self.add_entry(entry)
        return entry

    def get_entry(self, canonical_id: str) -> Optional[PronunciationEntry]:
        """Retrieves an entry by its canonical identifier."""
        return self.entries.get(canonical_id)

    def find_by_token(self, token: str) -> Optional[PronunciationEntry]:
        """
        Looks up a pronunciation entry by token, checking:
        1. Manual overrides
        2. Exact canonical_id
        3. Alias map (case-insensitive)
        4. Surface forms
        """
        if not token or not token.strip():
            return None

        clean = token.strip()
        norm_key = clean.lower().replace(" ", "_")

        # 1. Manual overrides
        if norm_key in self.overrides:
            return self.overrides[norm_key]

        # 2. Exact match
        if norm_key in self.entries:
            return self.entries[norm_key]

        # 3. Alias map
        target_lower = clean.lower()
        if target_lower in self.alias_map:
            cid = self.alias_map[target_lower]
            return self.entries.get(cid)

        # 4. Strip trailing punctuation and retry
        stripped = re.sub(r"^[^\w\u0900-\u097F]+|[^\w\u0900-\u097F]+$", "", clean).lower()
        if stripped and stripped in self.alias_map:
            cid = self.alias_map[stripped]
            return self.entries.get(cid)

        return None

    def record_occurrence(self, canonical_id: str, chapter_num: int) -> None:
        """Records an occurrence of an entity in a given chapter."""
        entry = self.entries.get(canonical_id)
        if entry:
            entry.occurrence_count += 1
            if chapter_num not in entry.chapter_occurrences:
                entry.chapter_occurrences.append(chapter_num)
                entry.chapter_occurrences.sort()

    def sync_from_book_bible(self, book_bible: Any) -> int:
        """
        Synchronizes BookBible entities into the pronunciation lexicon.
        Extracts existing pronunciation_hints and aliases from characters, locations, and lore terms.
        """
        synced_count = 0
        if not book_bible:
            return 0

        # Characters
        characters = getattr(book_bible, "characters", {})
        if isinstance(characters, dict):
            for eng_name, char_ent in characters.items():
                cid = getattr(char_ent, "canonical_id", "") or eng_name.strip().lower().replace(" ", "_")
                hindi = getattr(char_ent, "hindi_name", "") or eng_name
                hint = getattr(char_ent, "pronunciation_hint", "") or hindi
                aliases = list(getattr(char_ent, "aliases", []))
                if hindi and hindi not in aliases:
                    aliases.append(hindi)

                # If manual override exists, preserve it
                if cid in self.overrides:
                    continue

                status = PronunciationStatus.VERIFIED if hint else PronunciationStatus.LIKELY
                entry = PronunciationEntry(
                    canonical_id=cid,
                    canonical_text=eng_name,
                    aliases=aliases,
                    category=getattr(char_ent, "category", "character"),
                    expected_language=SpokenLanguage.HINDI if not getattr(char_ent, "is_foreign", False) else SpokenLanguage.ENGLISH,
                    pronunciation_hint=hint,
                    spoken_form=hint or hindi or eng_name,
                    status=status,
                    source=PronunciationSource.BOOK_BIBLE,
                    policy=PronunciationPolicy.STRICT_CANONICAL,
                    notes=f"Synced from BookBible character {eng_name}",
                )
                self.add_entry(entry)
                synced_count += 1

        # Locations, Organizations, Creatures, Objects, Terminology
        for cat_name in ("locations", "organizations", "creatures", "objects", "titles", "terminology"):
            cat_dict = getattr(book_bible, cat_name, {})
            if isinstance(cat_dict, dict):
                for term_en, term_hi in cat_dict.items():
                    cid = term_en.strip().lower().replace(" ", "_")
                    if cid in self.overrides:
                        continue
                    aliases = [term_hi] if term_hi else []
                    entry = PronunciationEntry(
                        canonical_id=cid,
                        canonical_text=term_en,
                        aliases=aliases,
                        category=cat_name.rstrip("s"),
                        pronunciation_hint=term_hi,
                        spoken_form=term_hi or term_en,
                        status=PronunciationStatus.VERIFIED if term_hi else PronunciationStatus.LIKELY,
                        source=PronunciationSource.BOOK_BIBLE,
                        notes=f"Synced from BookBible {cat_name}",
                    )
                    self.add_entry(entry)
                    synced_count += 1

        return synced_count

    def export_to_book_bible(self, book_bible: Any) -> None:
        """
        Exports verified pronunciations back into BookBible entities.
        """
        if not book_bible or not hasattr(book_bible, "characters"):
            return

        for cid, entry in self.entries.items():
            if entry.status in (PronunciationStatus.VERIFIED, PronunciationStatus.LIKELY):
                for char in book_bible.characters.values():
                    if char.english_name.lower() == entry.canonical_text.lower() or char.canonical_id == cid:
                        if entry.spoken_form and not char.pronunciation_hint:
                            char.pronunciation_hint = entry.spoken_form

    def save(self, project_dir: Path) -> Path:
        """Persists the lexicon to JSON in the project directory atomically."""
        target = Path(project_dir) / "pronunciation_lexicon.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp_target = target.with_suffix(".tmp")
        with open(tmp_target, "w", encoding="utf-8") as f:
            json.dump(self.model_dump(), f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_target, target)
        return target

    @classmethod
    def load_or_create(cls, project_dir: Path, book_bible: Optional[Any] = None) -> PronunciationLexicon:
        """Loads existing pronunciation_lexicon.json or initializes a fresh seed lexicon."""
        target = Path(project_dir) / "pronunciation_lexicon.json"
        if target.exists():
            try:
                with open(target, "r", encoding="utf-8") as f:
                    data = json.load(f)
                lex = cls.model_validate(data)
                if book_bible:
                    lex.sync_from_book_bible(book_bible)
                return lex
            except Exception:
                pass

        # Create fresh and seed
        lex = cls()
        lex.seed_default_lexicon()
        if book_bible:
            lex.sync_from_book_bible(book_bible)
            lex.save(project_dir)
        return lex

    def seed_default_lexicon(self) -> None:
        """Pre-seeds standard high-frequency difficult names and terms."""
        defaults = [
            # Acronyms & Organizations
            PronunciationEntry(
                canonical_id="fbi",
                canonical_text="FBI",
                spoken_form="एफ़.बी.आई.",
                pronunciation_hint="एफ़.बी.आई.",
                category="acronym",
                expected_language=SpokenLanguage.ENGLISH,
                status=PronunciationStatus.VERIFIED,
                source=PronunciationSource.CANONICAL_LEXICON,
            ),
            PronunciationEntry(
                canonical_id="cbi",
                canonical_text="CBI",
                spoken_form="सी.बी.आई.",
                pronunciation_hint="सी.बी.आई.",
                category="acronym",
                expected_language=SpokenLanguage.HINDI,
                status=PronunciationStatus.VERIFIED,
                source=PronunciationSource.CANONICAL_LEXICON,
            ),
            PronunciationEntry(
                canonical_id="who",
                canonical_text="WHO",
                spoken_form="डब्ल्यू.एच.ओ.",
                pronunciation_hint="डब्ल्यू.एच.ओ.",
                category="acronym",
                expected_language=SpokenLanguage.ENGLISH,
                status=PronunciationStatus.VERIFIED,
                source=PronunciationSource.CANONICAL_LEXICON,
            ),
            PronunciationEntry(
                canonical_id="vip",
                canonical_text="VIP",
                spoken_form="वी.आई.पी.",
                pronunciation_hint="वी.आई.पी.",
                category="acronym",
                expected_language=SpokenLanguage.ENGLISH,
                status=PronunciationStatus.VERIFIED,
                source=PronunciationSource.CANONICAL_LEXICON,
            ),
            # Classic foreign / English proper nouns in Hindi context
            PronunciationEntry(
                canonical_id="sherlock_holmes",
                canonical_text="Sherlock Holmes",
                aliases=["शरलॉक होम्स"],
                spoken_form="शरलॉक होम्स",
                pronunciation_hint="शरलॉक होम्स",
                category="character",
                expected_language=SpokenLanguage.ENGLISH,
                status=PronunciationStatus.VERIFIED,
                source=PronunciationSource.CANONICAL_LEXICON,
            ),
            PronunciationEntry(
                canonical_id="sherlock",
                canonical_text="Sherlock",
                aliases=["शरलॉक"],
                spoken_form="शरलॉक",
                pronunciation_hint="शरलॉक",
                category="character",
                expected_language=SpokenLanguage.ENGLISH,
                status=PronunciationStatus.VERIFIED,
                source=PronunciationSource.CANONICAL_LEXICON,
            ),
            PronunciationEntry(
                canonical_id="holmes",
                canonical_text="Holmes",
                aliases=["होम्स"],
                spoken_form="होम्स",
                pronunciation_hint="होम्स",
                category="character",
                expected_language=SpokenLanguage.ENGLISH,
                status=PronunciationStatus.VERIFIED,
                source=PronunciationSource.CANONICAL_LEXICON,
            ),
            PronunciationEntry(
                canonical_id="dr_watson",
                canonical_text="Dr. Watson",
                aliases=["डॉक्टर वॉटसन"],
                spoken_form="डॉक्टर वॉटसन",
                pronunciation_hint="डॉक्टर वॉटसन",
                category="character",
                expected_language=SpokenLanguage.ENGLISH,
                status=PronunciationStatus.VERIFIED,
                source=PronunciationSource.CANONICAL_LEXICON,
            ),
            PronunciationEntry(
                canonical_id="watson",
                canonical_text="Watson",
                aliases=["वॉटसन"],
                spoken_form="वॉटसन",
                pronunciation_hint="वॉटसन",
                category="character",
                expected_language=SpokenLanguage.ENGLISH,
                status=PronunciationStatus.VERIFIED,
                source=PronunciationSource.CANONICAL_LEXICON,
            ),
            PronunciationEntry(
                canonical_id="kaer_morhen",
                canonical_text="Kaer Morhen",
                aliases=["केर मॉरहेन"],
                spoken_form="केर मॉरहेन",
                pronunciation_hint="केर मॉरहेन",
                category="location",
                expected_language=SpokenLanguage.FOREIGN,
                status=PronunciationStatus.VERIFIED,
                source=PronunciationSource.CANONICAL_LEXICON,
            ),
        ]
        for d in defaults:
            self.add_entry(d)
