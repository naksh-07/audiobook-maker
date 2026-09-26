#!/usr/bin/env python3
"""
Sonic Query Planner & Multilingual Normalization Engine (Phase 3).
================================================================
Parses natural-language sound intent into structured retrieval signals.
Supports:
- Multilingual / Hinglish query normalization (preserving original text)
- 15 canonical sound intent types
- Atomic query decomposition for compound requests
- Acoustic, physical, event, and negative constraints
- Unmapped semantic text preservation for open-vocabulary CLAP retrieval
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Literal, Optional, Tuple, Set
from pydantic import BaseModel, Field, ConfigDict


SoundIntentType = Literal[
    "OBJECT",
    "EVENT",
    "ACTION",
    "MATERIAL",
    "ENVIRONMENT",
    "ATMOSPHERE",
    "DISTANCE",
    "INTENSITY",
    "DURATION",
    "TEMPO_RHYTHM",
    "MUSIC",
    "VOICE_NON_VOICE",
    "DRAMATIC_ROLE",
    "ACOUSTIC_CHARACTER",
    "SEMANTIC_DESCRIPTION",
]


class AtomicSoundConcept(BaseModel):
    """An individual atomic sound concept decomposed from a compound request."""
    model_config = ConfigDict(extra="ignore")

    concept_text: str = Field(..., description="Canonical text describing the atomic sound")
    primary_event: Optional[str] = Field(default=None, description="Primary event e.g. 'footsteps', 'door_slam'")
    modifiers: List[str] = Field(default_factory=list, description="Descriptive modifiers e.g. ['quiet', 'distant', 'wooden']")
    sequence_order: int = Field(default=0, ge=0, description="Order index if part of a temporal sequence")


class AcousticConstraints(BaseModel):
    """Deterministic acoustic criteria derived from query intent."""
    model_config = ConfigDict(extra="ignore")

    duration_min_sec: Optional[float] = None
    duration_max_sec: Optional[float] = None
    spectral_character: Optional[Literal["bright", "warm", "dark", "neutral"]] = None
    transient_character: Optional[Literal["strong_transient", "continuous", "neutral"]] = None
    energy_level: Optional[Literal["low", "medium", "high"]] = None
    target_lufs_min: Optional[float] = None
    target_lufs_max: Optional[float] = None
    whisper_safe_only: bool = False
    is_tonal_preferred: Optional[bool] = None


class NegativeConstraints(BaseModel):
    """Explicit negative criteria to penalize or reject unwanted audio features."""
    model_config = ConfigDict(extra="ignore")

    exclude_speech: bool = Field(default=False, description="Flag to penalize detected vocal/speech content")
    exclude_music: bool = Field(default=False, description="Flag to penalize detected musical accompaniment")
    banned_terms: List[str] = Field(default_factory=list, description="Terms that should not appear in candidate metadata")
    banned_labels: List[str] = Field(default_factory=list, description="Classifier labels to strongly penalize")


class SoundQueryPlan(BaseModel):
    """
    Structured query plan produced by the Sonic Query Planner.
    Guides multi-generator candidate retrieval and downstream reranking.
    """
    model_config = ConfigDict(extra="ignore")

    original_query: str = Field(..., description="Original raw user/agent query")
    normalized_query: str = Field(..., description="Canonicalized English query")
    detected_language: str = Field(default="en", description="'en', 'hi', or 'hinglish'")
    intent_types: List[SoundIntentType] = Field(default_factory=list)
    atomic_concepts: List[AtomicSoundConcept] = Field(default_factory=list)
    structured_filters: Dict[str, Any] = Field(default_factory=dict)
    keyword_terms: List[str] = Field(default_factory=list)
    semantic_queries: List[str] = Field(default_factory=list)
    acoustic_constraints: AcousticConstraints = Field(default_factory=AcousticConstraints)
    target_classifier_labels: List[str] = Field(default_factory=list)
    negative_constraints: NegativeConstraints = Field(default_factory=NegativeConstraints)
    ranking_hints: Dict[str, Any] = Field(default_factory=dict)
    unmapped_semantic_text: str = Field(default="")


class HinglishQueryNormalizer:
    """
    Normalizes Hindi and Hinglish audio requests into canonical English sound concepts
    while preserving the raw query and domain idioms.
    """

    # Comprehensive bilingual sound lexicon
    SOUND_LEXICON: Dict[str, Dict[str, Any]] = {
        # Weapons & Combat
        "talwar": {"en": "sword", "cat": "SFX", "act": "strike", "exc": "metal"},
        "talwaar": {"en": "sword", "cat": "SFX", "act": "strike", "exc": "metal"},
        "khanjar": {"en": "dagger", "cat": "SFX", "act": "stab", "exc": "metal"},
        "dhaal": {"en": "shield", "cat": "SFX", "act": "block", "res": "wood"},
        "teer": {"en": "arrow", "cat": "SFX", "act": "whoosh", "exc": "wood"},
        "kamaan": {"en": "bow", "cat": "SFX", "act": "release", "exc": "wood"},
        "vaar": {"en": "strike", "act": "strike", "intent": "ACTION"},
        "prahar": {"en": "impact", "act": "hit", "intent": "ACTION"},
        "chot": {"en": "hit", "act": "hit"},
        "takkar": {"en": "collision", "act": "crash"},
        "goli": {"en": "gunshot", "cat": "SFX", "act": "gunshot"},
        "dhamaka": {"en": "explosion", "cat": "SFX", "act": "explode"},
        "bhaari": {"en": "heavy", "mod": "heavy", "energy": "high"},
        "bhari": {"en": "heavy", "mod": "heavy", "energy": "high"},
        "halka": {"en": "faint", "mod": "faint", "energy": "low"},
        "halki": {"en": "faint", "mod": "faint", "energy": "low"},
        "tez": {"en": "sharp", "mod": "sharp", "energy": "high"},

        # Footsteps & Movement
        "kadmon": {"en": "footsteps", "cat": "FOL", "sub": "Footsteps"},
        "kadam": {"en": "footsteps", "cat": "FOL", "sub": "Footsteps"},
        "pairon": {"en": "footsteps", "cat": "FOL", "sub": "Footsteps"},
        "footsteps": {"en": "footsteps", "cat": "FOL", "sub": "Footsteps"},
        "aahat": {"en": "footstep sound", "cat": "FOL"},
        "daudna": {"en": "running", "cat": "FOL", "act": "run"},
        "bhaagna": {"en": "running", "cat": "FOL", "act": "run"},
        "chalna": {"en": "walking", "cat": "FOL", "act": "walk"},

        # Weather & Ambience
        "baarish": {"en": "rain", "cat": "AMB", "sub": "Weather"},
        "barish": {"en": "rain", "cat": "AMB", "sub": "Weather"},
        "hawa": {"en": "wind", "cat": "AMB", "sub": "Weather"},
        "toofan": {"en": "storm", "cat": "AMB", "sub": "Weather"},
        "bijli": {"en": "thunder", "cat": "AMB", "sub": "Weather"},
        "garaj": {"en": "thunder", "cat": "AMB", "sub": "Weather"},
        "kohra": {"en": "mist", "cat": "AMB"},
        "sannata": {"en": "silence room tone", "cat": "AMB", "whisper_safe": True},
        "khamoshi": {"en": "quiet room tone", "cat": "AMB", "whisper_safe": True},
        "aag": {"en": "fire crackle", "cat": "AMB", "sub": "Nature"},
        "dhuni": {"en": "fireplace", "cat": "AMB"},

        # Materials
        "patthar": {"en": "stone", "mat": "stone", "res": "stone"},
        "pathar": {"en": "stone", "mat": "stone", "res": "stone"},
        "lakdi": {"en": "wood", "mat": "wood", "res": "wood"},
        "loha": {"en": "metal", "mat": "metal", "exc": "metal"},
        "lohe": {"en": "metal", "mat": "metal", "exc": "metal"},
        "kaanch": {"en": "glass", "mat": "glass", "res": "glass"},
        "kanch": {"en": "glass", "mat": "glass", "res": "glass"},
        "mitti": {"en": "dirt", "mat": "dirt", "res": "dirt"},
        "keechad": {"en": "mud", "mat": "mud", "res": "mud"},
        "paani": {"en": "water", "mat": "water"},
        "pani": {"en": "water", "mat": "water"},

        # Architectural
        "darwaza": {"en": "door", "cat": "SFX", "sub": "Doors"},
        "darwaze": {"en": "door", "cat": "SFX", "sub": "Doors"},
        "khatka": {"en": "knock", "cat": "SFX", "act": "knock"},
        "khidki": {"en": "window", "cat": "SFX"},
        "galiyara": {"en": "corridor", "env": "corridor"},
        "kamra": {"en": "room", "env": "room"},
        "tikhana": {"en": "dungeon", "env": "dungeon"},
        "tehkhana": {"en": "dungeon", "env": "dungeon"},

        # Magic & Supernatural
        "jadui": {"en": "magical", "cat": "SFX", "sub": "Magic"},
        "jadu": {"en": "magic", "cat": "SFX", "sub": "Magic"},
        "shakti": {"en": "energy", "cat": "SFX"},
        "dhamaka_magic": {"en": "energy blast", "cat": "SFX", "sub": "Magic"},
        "chamatkar": {"en": "spell", "cat": "SFX", "sub": "Magic"},
        "bhoot": {"en": "ghostly", "cat": "SFX"},
        "daanav": {"en": "monster", "cat": "SFX", "sub": "Monster"},
        "shaitan": {"en": "demon roar", "cat": "SFX", "sub": "Monster"},

        # Distance & Perspective
        "dur": {"en": "distant", "dist": "distant"},
        "paas": {"en": "close", "dist": "close"},
        "nazdeek": {"en": "close", "dist": "close"},
    }

    # Negation trigger patterns
    NEGATION_TERMS = {
        "without", "bina", "binaa", "no", "non", "chhod", "hata", "nahin", "nahi", "free"
    }

    @classmethod
    def detect_language(cls, text: str) -> str:
        """Determines if query is Latin English, Devanagari Hindi, or Romanized Hinglish."""
        # Check Devanagari Unicode block (\u0900-\u097F)
        if re.search(r"[\u0900-\u097F]", text):
            return "hi"
        # Check common Hinglish marker words (strictly avoiding English homophones like 'door')
        hinglish_markers = {
            "ka", "ki", "ke", "aur", "se", "me", "mein", "par", "halki", "bhaari",
            "bina", "dur", "talwar", "darwaza", "baarish", "kadam", "kadmon", "jadui"
        }
        tokens = set(re.findall(r"[a-zA-Z]+", text.lower()))
        # Check for multi-word Hindi phrases like "door se"
        if "door se" in text.lower() or "dur se" in text.lower():
            return "hinglish"
        if tokens.intersection(hinglish_markers):
            return "hinglish"
        return "en"

    @classmethod
    def normalize(cls, query: str) -> Tuple[str, str, List[str], Dict[str, Any]]:
        """
        Translates Hindi/Hinglish idioms into canonical English sound concepts.
        Returns:
            (normalized_query, detected_lang, canonical_semantic_queries, extracted_attributes)
        """
        raw_text = query.strip()
        lang = cls.detect_language(raw_text)

        # Tokenize preserving order
        tokens = re.findall(r"[\w]+", raw_text.lower())
        translated_tokens: List[str] = []
        extracted_attrs: Dict[str, Any] = {}

        i = 0
        while i < len(tokens):
            w = tokens[i]

            # Compound checks (e.g. "door se" -> distant)
            if w in ("door", "dur") and i + 1 < len(tokens) and tokens[i + 1] in ("se", "ke"):
                translated_tokens.append("distant")
                extracted_attrs["distance"] = "distant"
                i += 2
                continue
            if w in ("paas", "nazdeek") and i + 1 < len(tokens) and tokens[i + 1] in ("se", "ke"):
                translated_tokens.append("close")
                extracted_attrs["distance"] = "close"
                i += 2
                continue

            # Grammatical particles to skip in English translation
            if w in ("ka", "ki", "ke", "se", "aur", "ko", "par", "me", "mein"):
                if w == "aur":
                    translated_tokens.append("and")
                i += 1
                continue

            lex_info = cls.SOUND_LEXICON.get(w)
            if lex_info:
                translated_tokens.append(lex_info["en"])
                for k, v in lex_info.items():
                    if k not in ("en",):
                        extracted_attrs[k] = v
            else:
                translated_tokens.append(w)
            i += 1

        normalized_phrase = " ".join(translated_tokens)

        # Build clean canonical semantic queries for CLAP
        semantic_queries: List[str] = []
        if normalized_phrase:
            semantic_queries.append(normalized_phrase)

        # Add domain-specific variations
        if "talwar" in query.lower() or "sword" in normalized_phrase:
            if "bhaari" in query.lower() or "heavy" in normalized_phrase:
                semantic_queries.append("heavy metal sword impact")
                semantic_queries.append("deep steel blade strike")
            else:
                semantic_queries.append("sword clash combat")

        if "jadui" in query.lower() or "magic" in normalized_phrase:
            semantic_queries.append("magical energy spell sound effect")

        if "baarish" in query.lower() or "rain" in normalized_phrase:
            if "hawa" in query.lower() or "wind" in normalized_phrase:
                semantic_queries.append("wind and rain weather ambience")

        # Deduplicate while preserving order
        seen = set()
        clean_semantic = []
        for sq in semantic_queries:
            sq_norm = sq.strip()
            if sq_norm and sq_norm.lower() not in seen:
                seen.add(sq_norm.lower())
                clean_semantic.append(sq_norm)

        return normalized_phrase, lang, clean_semantic, extracted_attrs


class SonicQueryPlanner:
    """
    Deconstructs natural-language sound queries into structured search signals:
    - Identifies multi-dimensional retrieval intents
    - Extracts acoustic and temporal constraints
    - Decomposes compound multi-action requests
    - Extracts negative constraints ('without voices', 'non-musical')
    - Preserves unmapped semantic text
    """

    def __init__(self):
        self.normalizer = HinglishQueryNormalizer()

    def plan_query(self, query: str) -> SoundQueryPlan:
        """
        Creates a complete SoundQueryPlan from natural language input.
        """
        raw_query = query.strip()
        if not raw_query:
            return SoundQueryPlan(
                original_query="",
                normalized_query="",
                detected_language="en",
            )

        # 1. Multilingual Normalization
        norm_text, lang, semantic_queries, norm_attrs = self.normalizer.normalize(raw_query)

        # 2. Negative Constraints Extraction
        neg_constraints = self._extract_negative_constraints(raw_query, norm_text)

        # 3. Intent Identification
        intents = self._identify_intents(norm_text, norm_attrs, neg_constraints)

        # 4. Atomic Query Decomposition
        atomic_concepts = self._decompose_atomic_concepts(norm_text)

        # 5. Structured Database Filters
        struct_filters = self._build_structured_filters(norm_text, norm_attrs)

        # 6. Acoustic Constraints
        acoustic_constraints = self._extract_acoustic_constraints(norm_text, norm_attrs)

        # 7. Keyword Terms for FTS5
        keyword_terms = self._extract_keyword_terms(norm_text, neg_constraints)

        # 8. Target Classifier Labels (AudioSet 527 / Studio Taxonomy)
        classifier_targets = self._resolve_classifier_targets(norm_text, atomic_concepts)

        # 9. Unmapped Semantic Text (Preserves non-database vocabulary for CLAP)
        unmapped_text = self._extract_unmapped_text(norm_text, struct_filters, keyword_terms)

        # Ensure semantic queries has at least the normalized text if not empty
        if not semantic_queries and norm_text:
            semantic_queries = [norm_text]

        # Ranking hints
        ranking_hints: Dict[str, Any] = {
            "prefer_cached": True,
            "has_sequence": len(atomic_concepts) > 1,
            "primary_intent": intents[0] if intents else "SEMANTIC_DESCRIPTION",
        }

        return SoundQueryPlan(
            original_query=raw_query,
            normalized_query=norm_text,
            detected_language=lang,
            intent_types=intents,
            atomic_concepts=atomic_concepts,
            structured_filters=struct_filters,
            keyword_terms=keyword_terms,
            semantic_queries=semantic_queries,
            acoustic_constraints=acoustic_constraints,
            target_classifier_labels=classifier_targets,
            negative_constraints=neg_constraints,
            ranking_hints=ranking_hints,
            unmapped_semantic_text=unmapped_text,
        )

    def _extract_negative_constraints(self, raw_query: str, norm_query: str) -> NegativeConstraints:
        """Parses negative indicators like 'without voices', 'non-musical', 'no speech'."""
        text_lower = f"{raw_query.lower()} {norm_query.lower()}"
        exclude_speech = False
        exclude_music = False
        banned_terms = []
        banned_labels = []

        # Speech negation checks
        speech_neg_patterns = [
            r"without\s+(?:voices?|speech|vocal|dialogue|talking|people)",
            r"no\s+(?:voices?|speech|vocal|dialogue|talking)",
            r"bina\s+(?:awaz|aawaz|bolne|baat)",
            r"non[- ]vocal",
            r"instrumental\s+only",
        ]
        for pat in speech_neg_patterns:
            if re.search(pat, text_lower):
                exclude_speech = True
                banned_labels.extend(["Speech", "Whispering", "Screaming", "Laughter", "human.vocal"])
                break

        # Music negation checks
        music_neg_patterns = [
            r"without\s+(?:music|melody|instruments?|bgm|score)",
            r"non[- ]musical",
            r"no\s+(?:music|melody|bgm)",
            r"pure\s+(?:ambience|atmosphere|foley|nature|sfx)",
        ]
        for pat in music_neg_patterns:
            if re.search(pat, text_lower):
                exclude_music = True
                banned_labels.extend(["Music", "Musical instrument", "BGM"])
                break

        return NegativeConstraints(
            exclude_speech=exclude_speech,
            exclude_music=exclude_music,
            banned_terms=banned_terms,
            banned_labels=list(set(banned_labels)),
        )

    def _identify_intents(
        self, norm_text: str, norm_attrs: Dict[str, Any], neg_constraints: NegativeConstraints
    ) -> List[SoundIntentType]:
        """Classifies retrieval intents present in the request."""
        intents: Set[SoundIntentType] = set()
        t = norm_text.lower()

        # Physical / Object
        if any(w in t for w in ("sword", "door", "window", "bell", "gun", "dagger", "shield", "glass", "cup", "plate")):
            intents.add("OBJECT")

        # Action / Event
        if any(w in t for w in ("footstep", "strike", "hit", "slam", "creak", "blast", "explosion", "whoosh", "knock")):
            intents.add("ACTION")
            intents.add("EVENT")

        # Material
        if any(w in t for w in ("stone", "wood", "wooden", "metal", "steel", "glass", "mud", "water", "gravel")):
            intents.add("MATERIAL")

        # Environment & Atmosphere
        if any(w in t for w in ("corridor", "room", "hall", "dungeon", "forest", "tavern", "cave", "castle", "church")):
            intents.add("ENVIRONMENT")
        if any(w in t for w in ("dark", "eerie", "peaceful", "ominous", "tense", "mysterious", "epic", "warm")):
            intents.add("ATMOSPHERE")

        # Distance & Perspective
        if any(w in t for w in ("distant", "far", "close", "intimate", "nearby")) or "dist" in norm_attrs:
            intents.add("DISTANCE")

        # Intensity
        if any(w in t for w in ("quiet", "faint", "soft", "heavy", "violent", "loud", "subtle")):
            intents.add("INTENSITY")

        # Duration & Acoustic
        if any(w in t for w in ("short", "brief", "long", "continuous", "drone", "bed", "quick")):
            intents.add("DURATION")
            intents.add("ACOUSTIC_CHARACTER")

        # Voice / Non-voice
        if neg_constraints.exclude_speech or any(w in t for w in ("whisper", "scream", "sigh", "breath", "crowd", "voice")):
            intents.add("VOICE_NON_VOICE")

        # Music
        if neg_constraints.exclude_music or any(w in t for w in ("music", "melody", "orchestral", "theme", "leitmotif", "drone")):
            intents.add("MUSIC")

        # Always include semantic description
        intents.add("SEMANTIC_DESCRIPTION")

        # Preserve canonical order
        order = [
            "EVENT", "ACTION", "OBJECT", "MATERIAL", "ENVIRONMENT", "ATMOSPHERE",
            "DISTANCE", "INTENSITY", "ACOUSTIC_CHARACTER", "DURATION",
            "VOICE_NON_VOICE", "MUSIC", "DRAMATIC_ROLE", "SEMANTIC_DESCRIPTION"
        ]
        return [item for item in order if item in intents]

    def _decompose_atomic_concepts(self, text: str) -> List[AtomicSoundConcept]:
        """
        Decomposes compound multi-action sentences into atomic concepts.
        e.g. 'quiet distant footsteps followed by a heavy wooden door slam'
        """
        # Split on sequence conjunctions
        split_patterns = r"\s+(?:followed by|then|and then|aur phir|ke baad|after that)\s+"
        parts = re.split(split_patterns, text, flags=re.IGNORECASE)

        concepts: List[AtomicSoundConcept] = []
        for idx, part in enumerate(parts):
            p_clean = part.strip()
            if not p_clean:
                continue

            words = p_clean.split()
            # Extract known modifiers
            modifiers = [
                w for w in words
                if w.lower() in (
                    "quiet", "faint", "soft", "heavy", "violent", "distant", "close",
                    "wooden", "stone", "metal", "dark", "sharp", "creaking", "slow", "fast"
                )
            ]

            primary_event = None
            for w in words:
                w_l = w.lower()
                if w_l in ("footsteps", "footstep", "walk", "running"):
                    primary_event = "footsteps"
                    break
                elif w_l in ("door", "slam", "knock", "creak"):
                    primary_event = "door_slam" if "slam" in p_clean.lower() else "door"
                    break
                elif w_l in ("sword", "strike", "clash", "slash"):
                    primary_event = "sword_strike"
                    break
                elif w_l in ("blast", "explosion", "magic", "spell"):
                    primary_event = "blast"
                    break

            concepts.append(AtomicSoundConcept(
                concept_text=p_clean,
                primary_event=primary_event,
                modifiers=modifiers,
                sequence_order=idx,
            ))

        return concepts if concepts else [AtomicSoundConcept(concept_text=text, sequence_order=0)]

    def _build_structured_filters(self, text: str, norm_attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Extracts Sonic Genome relational fields."""
        filters: Dict[str, Any] = {}
        t = text.lower()

        # Category
        if any(w in t for w in ("footstep", "foley", "cloth", "rustle", "gear", "movement")):
            filters["category"] = "FOL"
        elif any(w in t for w in ("ambience", "atmosphere", "room tone", "rain", "wind", "weather", "bed")):
            filters["category"] = "AMB"
        elif any(w in t for w in ("music", "theme", "score", "leitmotif", "melody")):
            filters["category"] = "MUS"
        elif any(w in t for w in ("sword", "explosion", "magic", "gunshot", "impact", "hit", "shatter")):
            filters["category"] = "SFX"

        # Apply normalized attributes overrides if detected
        if "cat" in norm_attrs:
            filters["category"] = norm_attrs["cat"]
        if "sub" in norm_attrs:
            filters["subcategory"] = norm_attrs["sub"]
        if "exc" in norm_attrs:
            filters["exciter"] = norm_attrs["exc"]
        if "res" in norm_attrs:
            filters["resonator"] = norm_attrs["res"]
        if "act" in norm_attrs:
            filters["action_type"] = norm_attrs["act"]

        # Direct textual overrides
        if "wooden" in t or "wood" in t:
            filters.setdefault("resonator", "wood")
        if "stone" in t:
            filters.setdefault("resonator", "stone")
        if "metal" in t or "steel" in t:
            filters.setdefault("exciter", "metal")
        if "glass" in t:
            filters.setdefault("resonator", "glass")

        # Mood / Dramatic role
        moods = ["tense", "mysterious", "peaceful", "epic", "dark", "emotional"]
        for m in moods:
            if m in t:
                filters["mood"] = m
                break

        return filters

    def _extract_acoustic_constraints(self, text: str, norm_attrs: Dict[str, Any]) -> AcousticConstraints:
        """Translates acoustic descriptors into DSP boundaries."""
        t = text.lower()
        ac = AcousticConstraints()

        # Duration
        if any(w in t for w in ("short", "quick", "brief", "click", "hit", "impact", "strike", "slam")):
            ac.duration_max_sec = 3.5
            ac.transient_character = "strong_transient"
        elif any(w in t for w in ("long", "continuous", "bed", "ambience", "drone", "atmosphere")):
            ac.duration_min_sec = 5.0
            ac.transient_character = "continuous"

        # Spectral Brightness
        if any(w in t for w in ("sharp", "bright", "metal", "glass", "clink", "ring", "chime")):
            ac.spectral_character = "bright"
        elif any(w in t for w in ("dark", "dull", "warm", "sub", "thud", "heavy", "deep")):
            ac.spectral_character = "dark"

        # Energy Level
        if any(w in t for w in ("quiet", "faint", "soft", "whisper", "distant")) or norm_attrs.get("energy") == "low":
            ac.energy_level = "low"
            ac.target_lufs_max = -22.0
            ac.whisper_safe_only = True
        elif any(w in t for w in ("heavy", "violent", "loud", "explosive", "massive")) or norm_attrs.get("energy") == "high":
            ac.energy_level = "high"
            ac.target_lufs_min = -20.0

        if norm_attrs.get("whisper_safe"):
            ac.whisper_safe_only = True

        return ac

    def _extract_keyword_terms(self, text: str, neg_constraints: NegativeConstraints) -> List[str]:
        """Extracts meaningful terms for FTS5 prefix search."""
        words = re.findall(r"[a-zA-Z0-9]+", text.lower())
        stopwords = {
            "a", "an", "the", "in", "on", "at", "by", "for", "with", "and", "or",
            "to", "from", "of", "followed", "then", "after", "that", "ka", "ki", "ke", "se"
        }
        banned = set(w.lower() for w in neg_constraints.banned_terms)
        clean = [
            w for w in words
            if len(w) > 2 and w not in stopwords and w not in banned and not w.isdigit()
        ]
        return clean

    def _resolve_classifier_targets(self, text: str, concepts: List[AtomicSoundConcept]) -> List[str]:
        """Maps query concepts to AudioSet 527 / studio classifier classes."""
        t = text.lower()
        targets: List[str] = []

        mapping = {
            "footstep": ["human.footsteps", "Footsteps", "Walk, footsteps"],
            "door": ["architectural.door", "Door", "Sliding door", "Knock"],
            "sword": ["combat", "metal.strike", "Tools"],
            "rain": ["weather.rain", "Rain", "Raindrop", "Thunderstorm"],
            "thunder": ["weather.thunder", "Thunder"],
            "wind": ["weather.wind", "Wind"],
            "fire": ["ambient.fire", "Fire", "Crackling"],
            "water": ["fluid.water", "Water", "Drip", "Splash, splatter"],
            "glass": ["material.glass", "Glass", "Shatter"],
            "explosion": ["combat.explosion", "Explosion", "Burst, pop"],
            "blast": ["combat.explosion", "Explosion"],
            "creature": ["nature.creature.howl", "Howl", "Animal"],
            "monster": ["nature.creature.howl", "Groan", "Animal"],
            "bird": ["nature.bird", "Bird", "Bird vocalization, bird call, bird song"],
        }

        for kw, labels in mapping.items():
            if kw in t or any(kw in c.concept_text.lower() for c in concepts):
                targets.extend(labels)

        return list(dict.fromkeys(targets))

    def _extract_unmapped_text(
        self, text: str, filters: Dict[str, Any], keyword_terms: List[str]
    ) -> str:
        """Finds tokens that were NOT mapped to structured DB fields."""
        mapped_words = set(keyword_terms)
        for v in filters.values():
            if isinstance(v, str):
                mapped_words.update(v.lower().split())

        all_words = text.split()
        unmapped = [w for w in all_words if w.lower() not in mapped_words and len(w) > 2]
        return " ".join(unmapped)
