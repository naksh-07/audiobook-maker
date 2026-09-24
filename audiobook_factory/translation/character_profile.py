#!/usr/bin/env python3
"""
Audiobook Factory - Universal Character Language Profile Engine.
Genre-agnostic engine that defines linguistic identity (vocabulary, cadence, sarcasm, honorifics, register)
for characters across ANY book or genre (Fantasy, Sci-Fi, Crime Noir, Historical Fiction, Thriller).
"""

import re
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class CharacterLanguageProfile(BaseModel):
    english_name: str
    hindi_name: str
    vocabulary_tier: str = "balanced"  # terse, scholastic, courtly, rustic, street, archaic, techno
    sentence_length_preference: str = "balanced"  # terse, staccato, balanced, elaborate, theatrical
    formality_level: int = 2           # 0 (gutter/slang) to 5 (high courtly/formal)
    profanity_tendency: str = "situational"  # none, rare, situational, frequent, visceral
    humor_style: str = "none"          # none, dry_sarcasm, theatrical_wit, ribald_banter, caustic_mockery
    honorific_preference: str = "tum"  # aap, tum, tu, dynamic
    hindustani_lexical_preference: str = "urdu_seasoned"  # hindi_dominant, urdu_seasoned, neutral, sanskritized
    speech_quirks: str = ""
    prohibited_registers: List[str] = Field(default_factory=list)

    def get_prompt_guidelines(self) -> str:
        """Returns instructional prompt lines to guide character speech."""
        lines = [
            f"CHARACTER LINGUISTIC PROFILE: {self.english_name} ({self.hindi_name})",
            f"- Sentence Structure & Rhythm: {self.sentence_length_preference.upper()} (Vocabulary tier: {self.vocabulary_tier})",
            f"- Formality Level: {self.formality_level}/5 | Default Honorific: '{self.honorific_preference}'",
            f"- Profanity & Grit Tendency: {self.profanity_tendency.upper()}",
            f"- Humor & Cadence: {self.humor_style.upper()}",
            f"- Lexical Texture: {self.hindustani_lexical_preference.upper()}",
        ]
        if self.speech_quirks:
            lines.append(f"- Speech Quirks & Tone: {self.speech_quirks}")
        if self.prohibited_registers:
            lines.append(f"- Strictly Prohibited: {', '.join(self.prohibited_registers)}")
        return "\n".join(lines)


# Universal sociolect archetype presets applicable across ANY novel genre
UNIVERSAL_ARCHETYPE_PRESETS: Dict[str, Dict[str, Any]] = {
    "COLD_CYNIC": {
        "vocabulary_tier": "terse",
        "sentence_length_preference": "terse",
        "formality_level": 2,
        "profanity_tendency": "situational",
        "humor_style": "dry_sarcasm",
        "honorific_preference": "tum",
        "hindustani_lexical_preference": "urdu_seasoned",
        "speech_quirks": "Restrained, laconic, low ornamentation. Speaks in crisp sentences with dry sarcasm and heavy pauses. Avoids preachiness.",
        "prohibited_registers": ["theatrical melodrama", "chatty exposition", "polite TV-serial Hindi"],
    },
    "THEATRICAL_WIT": {
        "vocabulary_tier": "theatrical",
        "sentence_length_preference": "theatrical",
        "formality_level": 3,
        "profanity_tendency": "frequent",
        "humor_style": "theatrical_wit",
        "honorific_preference": "tum",
        "hindustani_lexical_preference": "urdu_seasoned",
        "speech_quirks": "Expressive, elaborate, poetically exaggerated, socially agile. Uses witty cadence, tavern banter, and cheeky boastfulness.",
        "prohibited_registers": ["dull monotone", "stiff bureaucratic Hindi"],
    },
    "AUTHORITATIVE_MATRIARCH": {
        "vocabulary_tier": "courtly",
        "sentence_length_preference": "balanced",
        "formality_level": 4,
        "profanity_tendency": "situational",
        "humor_style": "caustic_mockery",
        "honorific_preference": "aap",
        "hindustani_lexical_preference": "hindi_dominant",
        "speech_quirks": "Authoritative, sharp-tongued yet protective. Commands respect, brooks no nonsense.",
        "prohibited_registers": ["servile submissiveness", "cheap street slang"],
    },
    "RAZOR_ARISTOCRAT": {
        "vocabulary_tier": "courtly",
        "sentence_length_preference": "balanced",
        "formality_level": 4,
        "profanity_tendency": "situational",
        "humor_style": "caustic_mockery",
        "honorific_preference": "tum",
        "hindustani_lexical_preference": "urdu_seasoned",
        "speech_quirks": "Razor-sharp, precise, commanding, aristocratic elegance. Cold menace mixed with magnetic presence.",
        "prohibited_registers": ["helpless damsel tones", "uncalibrated street vulgarity"],
    },
    "MILITARY_COMMANDER": {
        "vocabulary_tier": "terse",
        "sentence_length_preference": "staccato",
        "formality_level": 3,
        "profanity_tendency": "frequent",
        "humor_style": "none",
        "honorific_preference": "aap",
        "hindustani_lexical_preference": "hindi_dominant",
        "speech_quirks": "Direct, blunt, barked tactical cadence, zero diplomatic fluff.",
        "prohibited_registers": ["poetic florid prose", "hesitant whining"],
    },
    "SCHOLAR_INTELLECTUAL": {
        "vocabulary_tier": "scholastic",
        "sentence_length_preference": "elaborate",
        "formality_level": 4,
        "profanity_tendency": "none",
        "humor_style": "dry_sarcasm",
        "honorific_preference": "aap",
        "hindustani_lexical_preference": "sanskritized",
        "speech_quirks": "Analytical, measured, syntactically complex, bookish precision.",
        "prohibited_registers": ["street slurs", "unrefined colloquialisms"],
    },
    "RUSTIC_STREET_SURVIVOR": {
        "vocabulary_tier": "rustic",
        "sentence_length_preference": "staccato",
        "formality_level": 1,
        "profanity_tendency": "visceral",
        "humor_style": "ribald_banter",
        "honorific_preference": "tu",
        "hindustani_lexical_preference": "urdu_seasoned",
        "speech_quirks": "Raw, earthy, aggressive, survivalist slang and earthy idioms.",
        "prohibited_registers": ["high courtly Hindi", "delicate etiquette"],
    },
    "NEUTRAL": {
        "vocabulary_tier": "balanced",
        "sentence_length_preference": "balanced",
        "formality_level": 2,
        "profanity_tendency": "situational",
        "humor_style": "none",
        "honorific_preference": "tum",
        "hindustani_lexical_preference": "urdu_seasoned",
        "speech_quirks": "Natural conversational cadence.",
        "prohibited_registers": [],
    }
}


def synthesize_character_profile(
    name: str,
    hindi_name: Optional[str] = None,
    description: str = "",
    archetype: Optional[str] = None,
) -> CharacterLanguageProfile:
    """
    Dynamically synthesizes a CharacterLanguageProfile from description or archetype.
    Completely universal for ANY novel.
    """
    hindi = hindi_name or name
    if archetype and archetype in UNIVERSAL_ARCHETYPE_PRESETS:
        arch_key = archetype
    else:
        combined_text = f"{name} {description}".lower()
        if any(w in combined_text for w in ("gruff", "cynic", "hunter", "mercenary", "assassin", "detective", "gunslinger")):
            arch_key = "COLD_CYNIC"
        elif any(w in combined_text for w in ("bard", "poet", "singer", "actor", "rogue", "jester", "minstrel", "joker")):
            arch_key = "THEATRICAL_WIT"
        elif any(w in combined_text for w in ("matriarch", "mother", "abbess", "priestess", "elder", "nanny")):
            arch_key = "AUTHORITATIVE_MATRIARCH"
        elif any(w in combined_text for w in ("noble", "king", "queen", "lord", "lady", "baron", "duke", "sorceress", "empress", "countess")):
            arch_key = "RAZOR_ARISTOCRAT"
        elif any(w in combined_text for w in ("soldier", "captain", "general", "commander", "guard", "officer", "admiral")):
            arch_key = "MILITARY_COMMANDER"
        elif any(w in combined_text for w in ("scholar", "doctor", "professor", "priest", "wizard", "alchemist", "sage", "scientist")):
            arch_key = "SCHOLAR_INTELLECTUAL"
        elif any(w in combined_text for w in ("thief", "bandit", "beggar", "goon", "smuggler", "pirate", "scoundrel")):
            arch_key = "RUSTIC_STREET_SURVIVOR"
        else:
            arch_key = "NEUTRAL"

    cfg = UNIVERSAL_ARCHETYPE_PRESETS[arch_key]
    return CharacterLanguageProfile(
        english_name=name,
        hindi_name=hindi,
        vocabulary_tier=cfg["vocabulary_tier"],
        sentence_length_preference=cfg["sentence_length_preference"],
        formality_level=cfg["formality_level"],
        profanity_tendency=cfg["profanity_tendency"],
        humor_style=cfg["humor_style"],
        honorific_preference=cfg["honorific_preference"],
        hindustani_lexical_preference=cfg["hindustani_lexical_preference"],
        speech_quirks=description or cfg["speech_quirks"],
        prohibited_registers=cfg["prohibited_registers"],
    )


def get_character_profile(name: str, book_bible: Optional[Any] = None) -> CharacterLanguageProfile:
    """Finds or constructs character language profile from Book Bible dynamically."""
    if book_bible and hasattr(book_bible, "characters"):
        entity = book_bible.characters.get(name)
        if entity:
            if entity.language_profile:
                lp = entity.language_profile
                return CharacterLanguageProfile(
                    english_name=entity.english_name,
                    hindi_name=entity.hindi_name,
                    vocabulary_tier=lp.get("vocabulary_tier", "balanced"),
                    sentence_length_preference=lp.get("sentence_length_preference", "balanced"),
                    formality_level=lp.get("formality_level", 2),
                    profanity_tendency=lp.get("profanity_tendency", "situational"),
                    humor_style=lp.get("humor_style", "none"),
                    honorific_preference=lp.get("honorific_preference", "tum"),
                    hindustani_lexical_preference=lp.get("hindustani_lexical_preference", "urdu_seasoned"),
                    speech_quirks=lp.get("speech_quirks", entity.description),
                )
            return synthesize_character_profile(
                name=entity.english_name,
                hindi_name=entity.hindi_name,
                description=entity.description,
                archetype=entity.sociolect_archetype,
            )

    # Dynamic synthesis for any unknown character
    return synthesize_character_profile(name=name)
