#!/usr/bin/env python3
"""
Audiobook Factory - Entity Discovery Engine.
Detects emerging characters, creatures, factions, and terms in each chapter.
Compares candidates against the canonical Book Bible to eliminate omissions across later chapters.
Auto-commits non-conflicting entities while flagging ambiguous lore.
"""

import re
import json
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field

from .book_bible import BookBible, BookEntity


class DiscoveredEntity(BaseModel):
    name: str
    category: str = "character"  # character, location, creature, faction
    frequency: int = 1
    sample_context: str = ""
    suggested_devanagari: str = ""
    confidence: float = 0.85


class EntityDiscoveryEngine:
    @classmethod
    def discover_entities_from_text(
        cls,
        text: str,
        book_bible: BookBible,
        chapter_num: int = 1,
        call_llm_fn: Optional[Any] = None,
    ) -> List[DiscoveredEntity]:
        """
        Discovers new potential entities in chapter text.
        """
        existing_lexicon = book_bible.get_canonical_lexicon()
        candidates: List[DiscoveredEntity] = []

        ENGLISH_NON_ENTITY_STOPWORDS = {
            "The", "He", "She", "They", "Then", "After", "There", "When", "What", "It", "In", "On", "At",
            "Are", "Yes", "Do", "You", "Who", "No", "That", "As", "Your", "Well", "And", "So", "Ah",
            "Greetings", "How", "History", "This", "Not", "Something", "But", "If", "To", "Become",
            "Why", "Where", "Which", "Can", "Could", "Would", "Should", "May", "Might", "Must",
            "Never", "Always", "Sometimes", "Perhaps", "Maybe", "Here", "Now", "Only", "Just",
            "All", "Some", "One", "Two", "My", "Our", "His", "Her", "Its", "Their", "We", "I",
            "Sit", "Let", "Geography", "Because", "Certainly", "Civilization", "Stories", "True",
            "Nonsense", "Instead", "Either", "Another", "Whatever", "Notice", "Nothing", "Someone",
            "Everybody", "Nobody", "Anyway", "Obviously", "Forgive", "Wait", "Look", "Listen", "Come"
        }

        # Heuristic capitalized noun extraction
        # Matches 2-3 capitalized words (e.g. "Baron of Gulet", "Nivellen")
        matches = re.findall(r"\b[A-Z][a-z]+(?:\s+(?:of|de|the|van)\s+[A-Z][a-z]+|\s+[A-Z][a-z]+)?\b", text)
        freq_map: Dict[str, int] = {}
        for m in matches:
            m_clean = m.strip()
            # Filter common English sentence starters and discourse markers
            if m_clean in ENGLISH_NON_ENTITY_STOPWORDS:
                continue
            if m_clean not in existing_lexicon and m_clean not in book_bible.characters:
                freq_map[m_clean] = freq_map.get(m_clean, 0) + 1

        for name, count in freq_map.items():
            if count >= 2:  # Mentioned at least twice
                is_multiword = len(name.split()) > 1
                # Check if single word appears mid-sentence (not solely at sentence start)
                has_mid_sentence = bool(re.search(rf"(?<![.!?\"\n\r])\s+\b{re.escape(name)}\b", text))
                
                if is_multiword or has_mid_sentence:
                    conf = 0.85
                else:
                    conf = 0.50  # Sentence-starter ambiguity; require manual/Bible review

                candidates.append(DiscoveredEntity(
                    name=name,
                    category="location" if any(w in name.lower() for w in ("of", "mountain", "valley", "city", "river")) else "character",
                    frequency=count,
                    confidence=conf,
                ))

        return candidates

    @classmethod
    def reconcile_and_commit(
        cls,
        discovered: List[DiscoveredEntity],
        book_bible: BookBible,
        chapter_num: int = 1,
    ) -> Tuple[int, int]:
        """
        Commits non-conflicting entities to Book Bible.
        Returns (committed_count, flagged_count).
        """
        committed = 0
        flagged = 0

        for disc in discovered:
            entity = BookEntity(
                canonical_id=disc.name.lower().replace(" ", "_"),
                english_name=disc.name,
                hindi_name=disc.suggested_devanagari or disc.name,
                category=disc.category,
                first_appearance_chapter=chapter_num,
                confidence=disc.confidence,
                is_canonical=disc.confidence >= 0.8,
            )
            success = book_bible.propose_new_entity(entity, chapter_num)
            if success:
                committed += 1
            else:
                flagged += 1

        return committed, flagged
