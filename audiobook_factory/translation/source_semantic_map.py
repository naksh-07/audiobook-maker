#!/usr/bin/env python3
"""
Audiobook Factory - Persistent Source & Target Semantic Map Engine.
Builds and persists stable structured representations of propositions:
(WHO -> DID WHAT -> TO WHOM -> OBJECT -> NEGATION -> TIME/LOCATION)
per scene/chapter for both Source (English) and Target (Hindi).
Enables Semantic QA and Alignment Layers to compare translations against
frozen semantic ledgers without relying on blind LLM re-reading.
"""

from __future__ import annotations
import re
import json
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set
from pydantic import BaseModel, Field

SEMANTIC_MAP_VERSION = "2.0"

# ---------------------------------------------------------------------------
# Lexical Marker Constants for Deterministic Analysis
# ---------------------------------------------------------------------------

NEGATION_TOKENS: Set[str] = {
    "not", "never", "no", "nothing", "neither", "nor", "none", "nobody",
    "nowhere", "without", "hardly", "scarcely", "barely", "cannot", "can't",
    "won't", "wouldn't", "didn't", "doesn't", "don't", "refused", "failed",
    "stopped", "wasn't", "weren't", "isn't", "aren't", "haven't", "hasn't",
    "hadn't", "shouldn't", "couldn't", "mustn't", "denied"
}

SPEECH_VERBS: Set[str] = {
    "said", "asked", "replied", "muttered", "whispered", "shouted", "cried",
    "added", "agreed", "groaned", "grunted", "snorted", "mumbled", "demanded",
    "sighed", "screamed", "yelled", "called", "answered", "remarked", "retorted",
    "interrupted", "murmured", "chuckled", "gasped", "roared", "barked"
}

GENERIC_ROLES: Set[str] = {
    "poet", "bard", "witcher", "hunter", "priestess", "priest", "mother superior",
    "abbess", "alderman", "mayor", "peasant", "peasants", "knight", "king",
    "queen", "sorceress", "sorcerer", "mage", "girl", "boy", "man", "woman",
    "monster", "creature", "beast", "devil", "stranger", "guard", "guards",
    "traveler", "merchant", "innkeeper", "doctor", "healer", "warrior", "elder"
}

SUBJECT_PRONOUNS: Set[str] = {"he", "she", "they", "i", "we", "you", "it"}

TIME_MARKERS: List[str] = [
    "yesterday", "today", "tomorrow", "now", "then", "before", "after",
    "later", "suddenly", "meanwhile", "soon", "already", "still", "once",
    "at dawn", "at dusk", "at night", "in the morning", "in the evening",
    "that evening", "the next morning", "at that moment", "instantly",
    "for years", "a moment later", "shortly after"
]

LOCATION_PREPOSITIONS: Set[str] = {
    "in", "at", "on", "into", "from", "through", "under", "across", "behind",
    "near", "inside", "outside", "upon", "toward", "towards"
}

HINDI_NEGATION_TOKENS: Set[str] = {
    "नहीं", "मत", "ना", "न", "बिना", "बग़ैर", "कभी नहीं", "कुछ नहीं", "कोई नहीं",
    "इनकार", "रोका", "मना", "नाकाम"
}

HINDI_SPEECH_VERBS: Set[str] = {
    "कहा", "बोला", "बोली", "पूछा", "पूछी", "फुसफुसाया", "फुसफुसाई",
    "चिल्लाया", "चिल्लाई", "सहमति जताई", "जवाब दिया", "कहा उसने", "कहा उसने"
}

# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

class SemanticProposition(BaseModel):
    beat_id: str
    paragraph_idx: int
    source_sentence: str
    actors: List[str] = Field(default_factory=list)
    action: str = ""
    recipients: List[str] = Field(default_factory=list)
    has_negation: bool = False
    negation_keywords: List[str] = Field(default_factory=list)
    key_entities: List[str] = Field(default_factory=list)
    key_objects: List[str] = Field(default_factory=list)
    is_dialogue: bool = False
    speaker: Optional[str] = None
    time_marker: str = ""
    location_marker: str = ""


class SourceSemanticMap(BaseModel):
    scene_id: str
    total_beats: int
    source_hash: str
    semantic_map_version: str = SEMANTIC_MAP_VERSION
    propositions: List[SemanticProposition] = Field(default_factory=list)

    def save(self, output_path: Path):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.model_dump(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, file_path: Path) -> SourceSemanticMap:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.model_validate(data)

    def get_paragraphs(self) -> Dict[int, List[SemanticProposition]]:
        paragraphs: Dict[int, List[SemanticProposition]] = {}
        for p in self.propositions:
            paragraphs.setdefault(p.paragraph_idx, []).append(p)
        return paragraphs


class TargetSemanticProposition(BaseModel):
    beat_id: str
    paragraph_idx: int
    target_sentence: str
    actors_hi: List[str] = Field(default_factory=list)
    action_hi: str = ""
    recipients_hi: List[str] = Field(default_factory=list)
    has_negation: bool = False
    negation_keywords_hi: List[str] = Field(default_factory=list)
    key_entities_hi: List[str] = Field(default_factory=list)
    key_objects_hi: List[str] = Field(default_factory=list)
    is_dialogue: bool = False
    speaker_hi: Optional[str] = None
    time_marker_hi: str = ""
    location_marker_hi: str = ""


class TargetSemanticMap(BaseModel):
    scene_id: str
    total_beats: int
    target_hash: str
    semantic_map_version: str = SEMANTIC_MAP_VERSION
    propositions: List[TargetSemanticProposition] = Field(default_factory=list)

    def save(self, output_path: Path):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.model_dump(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, file_path: Path) -> TargetSemanticMap:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.model_validate(data)

    def get_paragraphs(self) -> Dict[int, List[TargetSemanticProposition]]:
        paragraphs: Dict[int, List[TargetSemanticProposition]] = {}
        for p in self.propositions:
            paragraphs.setdefault(p.paragraph_idx, []).append(p)
        return paragraphs


class ParagraphAlignment(BaseModel):
    paragraph_idx: int
    source_beat_ids: List[str] = Field(default_factory=list)
    target_beat_ids: List[str] = Field(default_factory=list)
    source_negations: int = 0
    target_negations: int = 0
    negation_parity: bool = True
    missing_actors: List[str] = Field(default_factory=list)
    dialogue_parity: bool = True
    coverage_ratio: float = 1.0
    status: str = "PASS"  # PASS, WARN, FAIL
    issues: List[str] = Field(default_factory=list)


class SemanticAlignmentResult(BaseModel):
    scene_id: str
    total_source_paragraphs: int = 0
    total_target_paragraphs: int = 0
    paragraph_alignments: List[ParagraphAlignment] = Field(default_factory=list)
    affected_paragraphs: List[int] = Field(default_factory=list)
    overall_negation_parity: bool = True
    overall_coverage_ratio: float = 1.0
    is_valid: bool = True
    summary: Dict[str, Any] = Field(default_factory=dict)

# ---------------------------------------------------------------------------
# Extraction Helpers: Source (English)
# ---------------------------------------------------------------------------

def _normalize_text_quotes(text: str) -> str:
    """Normalizes typographic single and double quotes to facilitate tokenization."""
    # Replace curly double quotes
    text = text.replace("“", '"').replace("”", '"')
    # Replace curly apostrophes with standard single quote
    text = text.replace("’", "'").replace("‘", "'")
    return text


def _extract_source_speech_attribution(
    sentence: str,
    known_entities: List[str],
    role_aliases: Optional[Dict[str, str]] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Detects speech attribution patterns like '"..." agreed the poet' or 'The traveler said, "..."'.
    Returns (speaker, speech_verb).
    """
    s_clean = sentence.strip()
    # Pattern 1: closing quote followed by verb + subject, e.g. '"..." said the traveler' or '"..." agreed the elder'
    m1 = re.search(r'["\']\s*(?:,\s*)?([a-z]+)\s+([a-zA-Z\s]+?)[.?!]?$', s_clean)
    if m1:
        verb, candidate = m1.group(1).lower(), m1.group(2).strip()
        if verb in SPEECH_VERBS:
            # Check candidate against known entities or generic roles
            for e in known_entities:
                if re.search(rf"\b{re.escape(e)}\b", candidate, re.IGNORECASE):
                    return e, verb
            candidate_clean = re.sub(r"^(?:the|a|an)\s+", "", candidate.lower()).strip()
            if candidate_clean in GENERIC_ROLES:
                resolved = (role_aliases or {}).get(candidate_clean, f"the {candidate_clean}")
                return resolved, verb

    # Pattern 2: subject + verb before opening quote, e.g. 'The traveler said, "..."' or 'The poet asked, "..."'
    m2 = re.search(r'^\s*([a-zA-Z\s]+?)\s+([a-z]+)\s*,\s*["\']', s_clean)
    if m2:
        candidate, verb = m2.group(1).strip(), m2.group(2).lower()
        if verb in SPEECH_VERBS:
            for e in known_entities:
                if re.search(rf"\b{re.escape(e)}\b", candidate, re.IGNORECASE):
                    return e, verb
            candidate_clean = re.sub(r"^(?:the|a|an)\s+", "", candidate.lower()).strip()
            if candidate_clean in GENERIC_ROLES:
                resolved = (role_aliases or {}).get(candidate_clean, f"the {candidate_clean}")
                return resolved, verb

    return None, None


def _extract_source_action_and_actors(
    sentence: str,
    known_entities: List[str],
    role_aliases: Optional[Dict[str, str]] = None,
) -> Tuple[List[str], str, List[str], List[str]]:
    """
    Extracts (actors, action, recipients, key_objects) deterministically from sentence structure.
    WHO -> DID WHAT -> TO WHOM -> OBJECT
    """
    s_norm = _normalize_text_quotes(sentence)
    actors: List[str] = []
    recipients: List[str] = []
    key_objects: List[str] = []
    action: str = ""

    # Check speech attribution first
    speaker, speech_verb = _extract_source_speech_attribution(s_norm, known_entities, role_aliases)
    if speaker and speech_verb:
        actors.append(speaker)
        action = speech_verb

    # Find all entity occurrences with positions
    matched_pos: List[Tuple[int, str]] = []
    for e in known_entities:
        for m in re.finditer(rf"\b{re.escape(e)}\b", s_norm, re.IGNORECASE):
            matched_pos.append((m.start(), e))

    # Also detect generic role nouns
    for role in GENERIC_ROLES:
        for m in re.finditer(rf"\b(?:the|a|an)?\s*\b({re.escape(role)})\b", s_norm, re.IGNORECASE):
            r_name = m.group(1).lower()
            resolved = (role_aliases or {}).get(r_name, f"the {r_name}")
            matched_pos.append((m.start(), resolved))

    matched_pos.sort(key=lambda x: x[0])
    ordered_entities = [item[1] for item in matched_pos]

    # Deduplicate while preserving order
    dedup_entities: List[str] = []
    for ent in ordered_entities:
        if ent not in dedup_entities:
            dedup_entities.append(ent)

    if dedup_entities:
        if not actors:
            actors.append(dedup_entities[0])
        for ent in dedup_entities:
            if ent not in actors:
                recipients.append(ent)
    else:
        # Check for subject pronouns if no named entities or roles
        first_words = re.findall(r"\b[a-zA-Z']+\b", s_norm.lower())
        for w in first_words[:3]:
            if w in SUBJECT_PRONOUNS:
                actors.append(w.capitalize())
                break

    # Extract primary predicate (DID WHAT) if not already set by speech attribution
    if not action:
        # Match common verb phrase structures: auxiliary + verb or finite action verb
        vp_match = re.search(
            r"\b(?:did|does|do|was|were|is|are|had|have|has|would|could|should|will|can|might|must)?\s*"
            r"(?:not\s+|never\s+)?"
            r"([a-z]+(?:ed|ing|s)?)\b",
            s_norm.lower(),
        )
        # Avoid common grammatical words being marked as actions
        stop_actions = {"the", "a", "an", "in", "on", "at", "to", "for", "with", "from", "of", "and", "but", "or"}
        if vp_match:
            candidate_act = vp_match.group(0).strip()
            if candidate_act not in stop_actions:
                action = candidate_act
        if not action:
            # Fallback to first non-stop verb-like word
            tokens = [w for w in re.findall(r"\b[a-zA-Z]+\b", s_norm.lower()) if w not in stop_actions]
            action = tokens[1] if len(tokens) > 1 else (tokens[0] if tokens else "stated")

    # Extract recipients via prepositional patterns (to/at/with/for/from <Entity/Role/Pronoun>)
    prep_recips = re.findall(
        r"\b(?:to|at|with|for|from|toward|towards)\s+(?:the\s+)?([A-Z][a-z]+|[a-z]+)\b",
        s_norm,
    )
    for pr in prep_recips:
        pr_clean = pr.strip()
        if pr_clean.lower() in SUBJECT_PRONOUNS or pr_clean.lower() in GENERIC_ROLES:
            if pr_clean not in recipients and pr_clean not in actors:
                recipients.append(pr_clean)

    # Extract key concrete direct objects following verbs or prepositions
    object_candidates = re.findall(
        r"\b(?:the|a|an|his|her|their|this|that)\s+([a-z]+\s+[a-z]+|[a-z]+)\b",
        s_norm.lower(),
    )
    stop_objs = {"time", "way", "moment", "thing", "voice", "eyes", "head", "face", "man", "woman"}
    for oc in object_candidates:
        oc = oc.strip()
        if oc not in stop_objs and oc not in GENERIC_ROLES and len(oc) > 3:
            if oc not in key_objects and oc not in [a.lower() for a in actors]:
                key_objects.append(oc)

    return actors, action, recipients, key_objects[:4]


def _extract_source_time_and_location(sentence: str) -> Tuple[str, str]:
    """Extracts temporal and locative phrases from an English sentence."""
    s_clean = sentence.strip()
    s_lower = s_clean.lower()
    time_marker = ""
    location_marker = ""

    for tm in TIME_MARKERS:
        if re.search(rf"\b{re.escape(tm)}\b", s_lower):
            time_marker = tm
            break

    # Look for locative prepositional phrases: in the <noun>, at the <noun>, etc.
    loc_match = re.search(
        r"\b(?:in|at|on|into|from|through|under|across|behind|near)\s+the\s+([a-zA-Z\s]+?)(?:[,.]|\s+(?:and|but|with|looking|sitting|standing|walking))",
        s_clean,
        re.IGNORECASE,
    )
    if loc_match:
        loc_candidate = loc_match.group(1).strip()
        if len(loc_candidate.split()) <= 3:
            location_marker = f"in the {loc_candidate}"

    return time_marker, location_marker

# ---------------------------------------------------------------------------
# Extraction Helpers: Target (Hindi)
# ---------------------------------------------------------------------------

def _extract_target_actors_and_action(
    sentence: str,
    book_bible: Optional[Any] = None,
) -> Tuple[List[str], str, List[str], List[str]]:
    """Extracts Hindi actors, action, recipients, and objects deterministically."""
    s_clean = sentence.strip()
    actors: List[str] = []
    recipients: List[str] = []
    key_objects: List[str] = []
    action: str = ""

    # Match Hindi entity names from BookBible if available
    if book_bible and hasattr(book_bible, "characters"):
        chars = book_bible.characters
        char_items = chars.values() if isinstance(chars, dict) else chars
        for c in char_items:
            h_name = getattr(c, "hindi_name", None) or (c.get("hindi_name") if isinstance(c, dict) else None)
            if h_name and h_name in s_clean:
                actors.append(h_name)

    # Hindi generic roles
    hindi_roles = ["कवि", "विचर", "पुजारिन", "मुखिया", "किसान", "राजा", "रानी", "जादूगरनी", "लड़की", "राक्षस", "सिपाही"]
    for hr in hindi_roles:
        if hr in s_clean and hr not in actors:
            actors.append(hr)

    # Subject pronouns if no actors
    if not actors:
        hindi_pronouns = ["उसने", "वह", "वे", "उन्होंने", "मैं", "हम", "तुम", "आप", "इसने"]
        for hp in hindi_pronouns:
            if re.search(rf"\b{hp}\b", s_clean):
                actors.append(hp)
                break

    # Hindi recipients marked by postpositions (को, से, के पास, की ओर)
    recip_matches = re.findall(r"([^\s।,?!]+)\s+(?:को|से|के लिए|के पास|की ओर)\b", s_clean)
    for rm in recip_matches:
        if rm not in actors and rm not in ["मुझ", "तुझ", "उस", "उन", "इस", "इन"]:
            recipients.append(rm)

    # Verb phrase: Hindi sentence typically ends with verb before । or punctuation
    v_match = re.search(r"([^\s।,?!]+(?:\s+[^\s।,?!]+){0,2})\s*[।?!]$", s_clean)
    if v_match:
        action = v_match.group(1).strip()

    # Objects from glossary terms if available
    if book_bible and hasattr(book_bible, "terminology"):
        terms = book_bible.terminology
        term_items = terms.items() if isinstance(terms, dict) else []
        for eng, hin in term_items:
            if hin and hin in s_clean and hin not in actors and hin not in recipients:
                key_objects.append(hin)

    return actors, action, recipients, key_objects[:4]


def _extract_target_negation(sentence: str) -> Tuple[bool, List[str]]:
    """Detects Devanagari negation particles in Hindi sentence."""
    found: List[str] = []
    for neg in HINDI_NEGATION_TOKENS:
        # Match as word boundary or distinct token
        if re.search(rf"(?:^|\s){re.escape(neg)}(?:\s|$|[।,?!])", sentence):
            found.append(neg)
    return len(found) > 0, found

# ---------------------------------------------------------------------------
# Public Construction Functions
# ---------------------------------------------------------------------------

def build_source_semantic_map(
    scene_text: str,
    scene_id: str = "scene_001",
    known_entities: Optional[List[str]] = None,
    known_objects: Optional[List[str]] = None,
    role_aliases: Optional[Dict[str, str]] = None,
    call_llm_fn: Optional[Any] = None,
) -> SourceSemanticMap:
    """
    Parses source scene text into a structured Source Semantic Map.
    Reliably captures WHO -> DID WHAT -> TO WHOM -> OBJECT -> NEGATION -> TIME/LOCATION.
    Enforces quotation tracking across sentences within paragraphs.
    When call_llm_fn is provided (Decision A3), enriches propositions via Gemini JSON pass.
    """
    source_hash = hashlib.sha256(scene_text.encode("utf-8")).hexdigest()[:16]
    paragraphs = [p.strip() for p in scene_text.split("\n\n") if p.strip()]

    # If no known entities provided, dynamically discover capitalized names
    if not known_entities:
        candidates = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b", scene_text)
        stop_words = {
            "The", "He", "She", "They", "Then", "After", "Before", "There", "When",
            "What", "It", "In", "On", "At", "And", "But", "Or", "So", "However",
            "Suddenly", "Meanwhile", "Later", "Now", "Just", "Even", "Though", "Later"
        }
        known_entities = list(set(c for c in candidates if c not in stop_words and len(c) > 2))

    propositions: List[SemanticProposition] = []
    beat_counter = 0

    for p_idx, para in enumerate(paragraphs):
        para_norm = _normalize_text_quotes(para)
        raw_sentences = re.split(r"(?<=[.!?])\s+", para_norm)

        # Quotation tracking across multi-sentence dialogue in the paragraph
        in_quote = False

        for s in raw_sentences:
            s_clean = s.strip()
            if not s_clean:
                continue

            beat_counter += 1
            words = re.findall(r"\b[a-zA-Z']+\b", s_clean.lower())

            # Negation detection
            found_negations = [w for w in words if w in NEGATION_TOKENS]
            has_neg = len(found_negations) > 0

            # Dialogue detection: check quotes in sentence or paragraph continuation
            has_open_quote = '"' in s_clean
            quote_count = s_clean.count('"')

            if in_quote:
                is_diag = True
                if quote_count % 2 != 0:
                    # Closing quote found in this sentence
                    in_quote = False
            else:
                if has_open_quote:
                    is_diag = True
                    if quote_count % 2 != 0:
                        # Unbalanced opening quote starts multi-sentence dialogue
                        in_quote = True
                else:
                    is_diag = False

            # Extract WHO -> DID WHAT -> TO WHOM -> OBJECT
            actors, action, recipients, key_objs = _extract_source_action_and_actors(
                s_clean, known_entities, role_aliases
            )

            # Extract TIME and LOCATION
            time_m, loc_m = _extract_source_time_and_location(s_clean)

            # Also check explicit known_objects
            if known_objects:
                for obj in known_objects:
                    if re.search(rf"\b{re.escape(obj)}\b", s_clean, re.IGNORECASE):
                        if obj not in key_objs:
                            key_objs.append(obj)

            speaker = actors[0] if (is_diag and actors) else None

            matched_entities = [e for e in known_entities if re.search(rf"\b{re.escape(e)}\b", s_clean, re.IGNORECASE)]

            prop = SemanticProposition(
                beat_id=f"{scene_id}_b{beat_counter:03d}",
                paragraph_idx=p_idx,
                source_sentence=s_clean,
                actors=actors,
                action=action,
                recipients=recipients,
                has_negation=has_neg,
                negation_keywords=found_negations,
                key_entities=matched_entities,
                key_objects=key_objs,
                is_dialogue=is_diag,
                speaker=speaker,
                time_marker=time_m,
                location_marker=loc_m,
            )
            propositions.append(prop)

    # Step 2: Full LLM JSON Enrichment Pass (Decision A3)
    if call_llm_fn is not None and len(propositions) > 0:
        try:
            propositions = _enrich_source_semantic_map_llm(propositions, call_llm_fn)
        except Exception:
            # Fall back to deterministic baseline on any LLM error
            pass

    return SourceSemanticMap(
        scene_id=scene_id,
        total_beats=len(propositions),
        source_hash=source_hash,
        propositions=propositions,
    )


def build_target_semantic_map(
    target_text: str,
    scene_id: str = "scene_001",
    book_bible: Optional[Any] = None,
    call_llm_fn: Optional[Any] = None,
) -> TargetSemanticMap:
    """
    Parses Hindi target scene text into a TargetSemanticMap.
    Extracts Hindi actors, actions, recipients, negation particles, and dialogue state.
    Enriches with LLM JSON extraction when call_llm_fn is available (Decision A3).
    """
    target_hash = hashlib.sha256(target_text.encode("utf-8")).hexdigest()[:16]
    paragraphs = [p.strip() for p in target_text.split("\n\n") if p.strip()]

    propositions: List[TargetSemanticProposition] = []
    beat_counter = 0

    for p_idx, para in enumerate(paragraphs):
        # Split Hindi sentences on Devanagari danda, question mark, or exclamation
        raw_sentences = re.split(r"(?<=[।?!])\s+", para)
        in_quote = False

        for s in raw_sentences:
            s_clean = s.strip()
            if not s_clean:
                continue

            beat_counter += 1
            has_neg, found_neg = _extract_target_negation(s_clean)

            # Check quotes
            quote_count = s_clean.count('"') + s_clean.count("“") + s_clean.count("”")
            if in_quote:
                is_diag = True
                if quote_count % 2 != 0:
                    in_quote = False
            else:
                if quote_count > 0:
                    is_diag = True
                    if quote_count % 2 != 0:
                        in_quote = True
                else:
                    is_diag = False

            actors, action, recips, key_objs = _extract_target_actors_and_action(s_clean, book_bible)

            speaker = actors[0] if (is_diag and actors) else None

            prop = TargetSemanticProposition(
                beat_id=f"{scene_id}_tgt_b{beat_counter:03d}",
                paragraph_idx=p_idx,
                target_sentence=s_clean,
                actors_hi=actors,
                action_hi=action,
                recipients_hi=recips,
                has_negation=has_neg,
                negation_keywords_hi=found_neg,
                key_entities_hi=actors,
                key_objects_hi=key_objs,
                is_dialogue=is_diag,
                speaker_hi=speaker,
            )
            propositions.append(prop)

    # Step 2: Full LLM JSON Enrichment Pass (Decision A3)
    if call_llm_fn is not None and len(propositions) > 0:
        try:
            propositions = _enrich_target_semantic_map_llm(propositions, call_llm_fn)
        except Exception:
            pass

    return TargetSemanticMap(
        scene_id=scene_id,
        total_beats=len(propositions),
        target_hash=target_hash,
        propositions=propositions,
    )

# ---------------------------------------------------------------------------
# Semantic Aligner Layer
# ---------------------------------------------------------------------------

class SemanticAligner:
    """
    Aligns SourceSemanticMap against TargetSemanticMap at the paragraph and beat levels.
    Verifies Negation Parity, Actor Retention, Dialogue Continuity, and Beat Coverage.
    """

    @classmethod
    def align(
        cls,
        source_map: SourceSemanticMap,
        target_map: TargetSemanticMap,
        book_bible: Optional[Any] = None,
    ) -> SemanticAlignmentResult:
        src_paras = source_map.get_paragraphs()
        tgt_paras = target_map.get_paragraphs()

        total_src_paras = len(src_paras)
        total_tgt_paras = len(tgt_paras)

        alignments: List[ParagraphAlignment] = []
        affected_paragraphs: List[int] = []

        # If paragraph count matches exactly (ideal 1:1 case)
        if total_src_paras == total_tgt_paras:
            for p_idx in sorted(src_paras.keys()):
                s_props = src_paras.get(p_idx, [])
                t_props = tgt_paras.get(p_idx, [])
                p_align = cls._align_single_paragraph(p_idx, s_props, t_props, book_bible)
                alignments.append(p_align)
                if p_align.status in ("WARN", "FAIL"):
                    affected_paragraphs.append(p_idx)
        else:
            # Proportional mapping when paragraph counts differ
            for p_idx in sorted(src_paras.keys()):
                s_props = src_paras.get(p_idx, [])
                # Map source p_idx to corresponding target p_idx proportionally
                if total_src_paras > 0 and total_tgt_paras > 0:
                    mapped_tgt_idx = min(int(round(p_idx * (total_tgt_paras / total_src_paras))), total_tgt_paras - 1)
                else:
                    mapped_tgt_idx = 0
                t_props = tgt_paras.get(mapped_tgt_idx, [])
                p_align = cls._align_single_paragraph(p_idx, s_props, t_props, book_bible)
                alignments.append(p_align)
                if p_align.status in ("WARN", "FAIL"):
                    affected_paragraphs.append(p_idx)

        if total_src_paras == 0 and total_tgt_paras > 0:
            overall_negation = False
            avg_coverage = 0.0
            is_valid = False
        elif total_src_paras == 0 and total_tgt_paras == 0:
            overall_negation = True
            avg_coverage = 1.0
            is_valid = True
        else:
            overall_negation = all(a.negation_parity for a in alignments)
            avg_coverage = (
                sum(a.coverage_ratio for a in alignments) / len(alignments)
                if alignments else 0.0
            )
            is_valid = overall_negation and (avg_coverage >= 0.65) and len(affected_paragraphs) <= max(1, total_src_paras // 3)

        return SemanticAlignmentResult(
            scene_id=source_map.scene_id,
            total_source_paragraphs=total_src_paras,
            total_target_paragraphs=total_tgt_paras,
            paragraph_alignments=alignments,
            affected_paragraphs=sorted(list(set(affected_paragraphs))),
            overall_negation_parity=overall_negation,
            overall_coverage_ratio=round(avg_coverage, 3),
            is_valid=is_valid,
            summary={
                "aligned_paragraphs": len(alignments),
                "affected_count": len(affected_paragraphs),
                "overall_negation_parity": overall_negation,
                "average_coverage": round(avg_coverage, 3),
            },
        )

    @classmethod
    def _align_single_paragraph(
        cls,
        p_idx: int,
        source_props: List[SemanticProposition],
        target_props: List[TargetSemanticProposition],
        book_bible: Optional[Any],
    ) -> ParagraphAlignment:
        s_beat_ids = [p.beat_id for p in source_props]
        t_beat_ids = [p.beat_id for p in target_props]

        s_negs = sum(1 for p in source_props if p.has_negation)
        t_negs = sum(1 for p in target_props if p.has_negation)

        # Check negation parity: if source has negation, target must also have negation
        neg_parity = True
        issues: List[str] = []

        if s_negs > 0 and t_negs == 0:
            neg_parity = False
            issues.append(f"Paragraph {p_idx}: Source has {s_negs} negation(s) but target has 0.")

        # Actor retention
        missing_actors: List[str] = []
        for sp in source_props:
            for act in sp.actors:
                # Check if actor or their Hindi equivalent appears in target propositions
                found_in_target = False
                act_lower = act.lower()
                for tp in target_props:
                    if any(act_lower in a.lower() for a in tp.actors_hi):
                        found_in_target = True
                        break
                    # Check BookBible mapping
                    if book_bible and hasattr(book_bible, "characters"):
                        chars = book_bible.characters
                        char_items = chars.values() if isinstance(chars, dict) else chars
                        for c in char_items:
                            eng = getattr(c, "english_name", "")
                            hin = getattr(c, "hindi_name", "")
                            if eng.lower() == act_lower and hin in tp.target_sentence:
                                found_in_target = True
                                break
                    if found_in_target:
                        break
                if not found_in_target and act not in ("He", "She", "They", "It", "I", "We", "You"):
                    if act not in missing_actors:
                        missing_actors.append(act)

        # Dialogue parity
        s_has_diag = any(p.is_dialogue for p in source_props)
        t_has_diag = any(p.is_dialogue for p in target_props)
        diag_parity = (s_has_diag == t_has_diag)
        if not diag_parity and s_has_diag and not t_has_diag:
            issues.append(f"Paragraph {p_idx}: Source contains dialogue but target lacks dialogue quotation/markers.")

        # Coverage
        coverage = round(len(target_props) / max(1, len(source_props)), 2)
        if coverage < 0.5:
            issues.append(f"Paragraph {p_idx}: Low beat coverage ({coverage:.2f}). Potential omission.")

        # Status determination
        if not neg_parity or coverage < 0.5:
            status = "FAIL"
        elif missing_actors or not diag_parity or coverage < 0.7:
            status = "WARN"
        else:
            status = "PASS"

        return ParagraphAlignment(
            paragraph_idx=p_idx,
            source_beat_ids=s_beat_ids,
            target_beat_ids=t_beat_ids,
            source_negations=s_negs,
            target_negations=t_negs,
            negation_parity=neg_parity,
            missing_actors=missing_actors,
            dialogue_parity=diag_parity,
            coverage_ratio=coverage,
            status=status,
            issues=issues,
        )

# ---------------------------------------------------------------------------
# LLM Enrichment Helpers (Decision A3)
# ---------------------------------------------------------------------------

def _enrich_source_semantic_map_llm(
    propositions: List[SemanticProposition],
    call_llm_fn: Any,
) -> List[SemanticProposition]:
    """Uses Gemini JSON mode to refine slot values across propositions."""
    beats_payload = [
        {
            "beat_id": p.beat_id,
            "sentence": p.source_sentence,
            "actors": p.actors,
            "action": p.action,
            "recipients": p.recipients,
            "key_objects": p.key_objects,
            "has_negation": p.has_negation,
        }
        for p in propositions
    ]
    prompt = (
        "Refine and verify the semantic slots for these narrative beats in JSON format.\n"
        "Return a JSON object: {\"beats\": [{\"beat_id\": str, \"actors\": [str], \"action\": str, "
        "\"recipients\": [str], \"key_objects\": [str], \"has_negation\": bool, \"time_marker\": str, \"location_marker\": str}]}\n\n"
        f"Beats:\n{json.dumps(beats_payload, ensure_ascii=False)}"
    )
    raw_res = call_llm_fn(prompt, system_instruction="You are a linguistic semantic parser.", json_mode=True)
    if isinstance(raw_res, str):
        from audiobook_factory.sanitizer import strip_markdown_fences
        parsed = json.loads(strip_markdown_fences(raw_res))
    else:
        parsed = raw_res

    beats_list = parsed.get("beats", [])
    beats_by_id = {b["beat_id"]: b for b in beats_list if "beat_id" in b}

    for p in propositions:
        if p.beat_id in beats_by_id:
            b = beats_by_id[p.beat_id]
            if b.get("actors"):
                p.actors = b["actors"]
            if b.get("action"):
                p.action = b["action"]
            if b.get("recipients"):
                p.recipients = b["recipients"]
            if b.get("key_objects"):
                p.key_objects = b["key_objects"]
            if "has_negation" in b:
                p.has_negation = bool(b["has_negation"])
            if b.get("time_marker"):
                p.time_marker = b["time_marker"]
            if b.get("location_marker"):
                p.location_marker = b["location_marker"]

    return propositions


def _enrich_target_semantic_map_llm(
    propositions: List[TargetSemanticProposition],
    call_llm_fn: Any,
) -> List[TargetSemanticProposition]:
    """Uses Gemini JSON mode to refine Hindi target semantic propositions."""
    beats_payload = [
        {
            "beat_id": p.beat_id,
            "target_sentence": p.target_sentence,
            "actors_hi": p.actors_hi,
            "action_hi": p.action_hi,
            "has_negation": p.has_negation,
        }
        for p in propositions
    ]
    prompt = (
        "Refine Hindi semantic slots for these translated beats in JSON format.\n"
        "Return JSON: {\"beats\": [{\"beat_id\": str, \"actors_hi\": [str], \"action_hi\": str, "
        "\"recipients_hi\": [str], \"has_negation\": bool}]}\n\n"
        f"Beats:\n{json.dumps(beats_payload, ensure_ascii=False)}"
    )
    raw_res = call_llm_fn(prompt, system_instruction="You are a Hindi semantic auditor.", json_mode=True)
    if isinstance(raw_res, str):
        from audiobook_factory.sanitizer import strip_markdown_fences
        parsed = json.loads(strip_markdown_fences(raw_res))
    else:
        parsed = raw_res

    beats_list = parsed.get("beats", [])
    beats_by_id = {b["beat_id"]: b for b in beats_list if "beat_id" in b}

    for p in propositions:
        if p.beat_id in beats_by_id:
            b = beats_by_id[p.beat_id]
            if b.get("actors_hi"):
                p.actors_hi = b["actors_hi"]
            if b.get("action_hi"):
                p.action_hi = b["action_hi"]
            if b.get("recipients_hi"):
                p.recipients_hi = b["recipients_hi"]
            if "has_negation" in b:
                p.has_negation = bool(b["has_negation"])

    return propositions
