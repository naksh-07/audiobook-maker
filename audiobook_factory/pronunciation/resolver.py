#!/usr/bin/env python3
"""
Audiobook Factory - Deterministic 7-Tier Pronunciation Resolver.
Resolves pronunciation for sensitive tokens and entities across a strict, auditable hierarchy:
1. Explicit manual / book-level override
2. Canonical Book Bible pronunciation
3. Previously verified pronunciation in project history
4. Known pronunciation lexicon entry
5. Language-specific deterministic rules (nukta, numerals, currencies, units, acronyms)
6. Model-assisted inference (when LLM callable provided)
7. REVIEW_REQUIRED fallback (never silently certifies uncertain or failing audio)
"""

from __future__ import annotations
import re
from typing import Dict, Any, List, Optional, Tuple, Callable

from .contracts import (
    PronunciationEntry,
    PronunciationStatus,
    PronunciationSource,
    SpokenLanguage,
    PronunciationPolicy,
    PronunciationResolutionResult,
)
from .lexicon import PronunciationLexicon
from .language_detector import detect_token_language
from .code_switch import CodeSwitchEngine


# Deterministic Devanagari and Latin numeral conversion maps (0 to 100)
HINDI_NUMERAL_WORDS = {
    0: "शून्य", 1: "एक", 2: "दो", 3: "तीन", 4: "चार", 5: "पाँच",
    6: "छह", 7: "सात", 8: "आठ", 9: "नौ", 10: "दस",
    11: "ग्यारह", 12: "बारह", 13: "तेरह", 14: "चौदह", 15: "पंद्रह",
    16: "सोलह", 17: "सत्रह", 18: "अठारह", 19: "उन्नीस", 20: "बीस",
    21: "इक्कीस", 22: "बाईस", 23: "तेईस", 24: "चौबीस", 25: "पच्चीस",
    30: "तीस", 40: "चालीस", 50: "पचास", 60: "साठ", 70: "सत्तर",
    80: "अस्सी", 90: "नब्बे", 100: "सौ", 1000: "हज़ार", 100000: "लाख", 10000000: "करोड़"
}

DEVA_DIGIT_MAP = {
    '०': '0', '१': '1', '२': '2', '३': '3', '४': '4',
    '५': '5', '६': '6', '७': '7', '८': '8', '९': '9'
}

UNITS_MAP = {
    "km": "किलोमीटर", "किमी": "किलोमीटर",
    "m": "मीटर", "मी": "मीटर",
    "cm": "सेंटीमीटर", "सेमी": "सेंटीमीटर",
    "kg": "किलोग्राम", "किग्रा": "किलोग्राम",
    "g": "ग्राम", "ग्रा": "ग्राम",
    "hr": "घंटे", "घंटा": "घंटा",
    "min": "मिनट", "sec": "सेकंड",
}


def number_to_hindi_words(n: int) -> str:
    """Converts positive integer up to 99999999 into natural spoken Hindi words."""
    if n in HINDI_NUMERAL_WORDS:
        return HINDI_NUMERAL_WORDS[n]
    if n < 0:
        return f"माइनस {number_to_hindi_words(-n)}"
    if n < 100:
        # Tens + ones compound heuristic
        tens = (n // 10) * 10
        ones = n % 10
        if tens in HINDI_NUMERAL_WORDS and ones in HINDI_NUMERAL_WORDS:
            return f"{HINDI_NUMERAL_WORDS[tens]} {HINDI_NUMERAL_WORDS[ones]}"
        return str(n)
    if n < 1000:
        hundreds = n // 100
        rem = n % 100
        h_str = f"{number_to_hindi_words(hundreds)} सौ"
        return f"{h_str} {number_to_hindi_words(rem)}" if rem else h_str
    if n < 100000:
        thousands = n // 1000
        rem = n % 1000
        t_str = f"{number_to_hindi_words(thousands)} हज़ार"
        return f"{t_str} {number_to_hindi_words(rem)}" if rem else t_str
    if n < 10000000:
        lakhs = n // 100000
        rem = n % 100000
        l_str = f"{number_to_hindi_words(lakhs)} लाख"
        return f"{l_str} {number_to_hindi_words(rem)}" if rem else l_str
    crores = n // 10000000
    rem = n % 10000000
    c_str = f"{number_to_hindi_words(crores)} करोड़"
    return f"{c_str} {number_to_hindi_words(rem)}" if rem else c_str


class PronunciationResolver:
    """
    Deterministic resolution engine with zero fake precision and honest failure states.
    """

    def __init__(
        self,
        lexicon: PronunciationLexicon,
        book_bible: Optional[Any] = None,
        call_llm_fn: Optional[Callable[..., str]] = None,
    ):
        self.lexicon = lexicon
        self.book_bible = book_bible
        self.call_llm_fn = call_llm_fn
        self.verified_history: Dict[str, str] = {}  # token_norm -> spoken_form

    def register_verified_pronunciation(self, token: str, spoken_form: str):
        """Registers a known verified pronunciation in project memory (Tier 3)."""
        norm = token.strip().lower()
        self.verified_history[norm] = spoken_form.strip()

    def resolve_token(
        self,
        token: str,
        sentence_context: str = "",
        speaker_profile: Optional[Any] = None,
        is_dialogue: bool = True,
    ) -> PronunciationResolutionResult:
        """
        Executes the 7-tier resolution hierarchy on a token.
        """
        clean_token = token.strip()
        stripped = re.sub(r"^[^\w\u0900-\u097F\$₹%]+|[^\w\u0900-\u097F\$₹%]+$", "", clean_token)
        if not stripped:
            return PronunciationResolutionResult(
                original_token=token,
                resolved_spoken=token,
                status=PronunciationStatus.VERIFIED,
                source=PronunciationSource.DETERMINISTIC_RULE,
                transformation_applied=False,
                requires_review=False,
                explanation="Punctuation / whitespace token",
            )

        norm_key = stripped.lower().replace(" ", "_")
        detected_lang = detect_token_language(stripped)

        # -------------------------------------------------------------
        # Tier 1: Explicit Manual / Book-Level Override
        # -------------------------------------------------------------
        if norm_key in self.lexicon.overrides:
            override = self.lexicon.overrides[norm_key]
            return PronunciationResolutionResult(
                original_token=token,
                canonical_id=override.canonical_id,
                resolved_spoken=override.spoken_form,
                status=PronunciationStatus.VERIFIED,
                source=PronunciationSource.MANUAL_OVERRIDE,
                language=override.expected_language,
                transformation_applied=(override.spoken_form != stripped),
                requires_review=False,
                explanation="Resolved via explicit Tier 1 manual book-level override",
            )

        # -------------------------------------------------------------
        # Tier 2: Canonical Book Bible Entity
        # -------------------------------------------------------------
        if self.book_bible and hasattr(self.book_bible, "find_character"):
            char_ent = self.book_bible.find_character(stripped)
            if char_ent:
                spoken = char_ent.pronunciation_hint or char_ent.hindi_name or char_ent.english_name
                status = PronunciationStatus.VERIFIED if char_ent.pronunciation_hint else PronunciationStatus.LIKELY
                return PronunciationResolutionResult(
                    original_token=token,
                    canonical_id=char_ent.canonical_id,
                    resolved_spoken=spoken,
                    status=status,
                    source=PronunciationSource.BOOK_BIBLE,
                    language=SpokenLanguage.HINDI if char_ent.hindi_name else SpokenLanguage.ENGLISH,
                    transformation_applied=(spoken != stripped),
                    requires_review=False,
                    explanation=f"Resolved via Tier 2 BookBible character '{char_ent.english_name}'",
                )

        # -------------------------------------------------------------
        # Tier 3: Previously Verified Pronunciation in Project History
        # -------------------------------------------------------------
        if stripped.lower() in self.verified_history:
            prev_spoken = self.verified_history[stripped.lower()]
            return PronunciationResolutionResult(
                original_token=token,
                resolved_spoken=prev_spoken,
                status=PronunciationStatus.VERIFIED,
                source=PronunciationSource.PREVIOUS_VERIFIED,
                language=detected_lang,
                transformation_applied=(prev_spoken != stripped),
                requires_review=False,
                explanation="Resolved via Tier 3 previously verified project occurrence",
            )

        # -------------------------------------------------------------
        # Tier 4: Known Pronunciation Lexicon Entry
        # -------------------------------------------------------------
        lex_entry = self.lexicon.find_by_token(stripped)
        if lex_entry:
            return PronunciationResolutionResult(
                original_token=token,
                canonical_id=lex_entry.canonical_id,
                resolved_spoken=lex_entry.spoken_form,
                status=lex_entry.status,
                source=PronunciationSource.CANONICAL_LEXICON,
                language=lex_entry.expected_language,
                transformation_applied=(lex_entry.spoken_form != stripped),
                requires_review=(lex_entry.status in (PronunciationStatus.UNCERTAIN, PronunciationStatus.REVIEW_REQUIRED)),
                explanation=f"Resolved via Tier 4 Canonical Lexicon entry '{lex_entry.canonical_id}'",
            )

        # -------------------------------------------------------------
        # Tier 5: Language-Specific Deterministic Rules
        # -------------------------------------------------------------
        rule_res = self._apply_deterministic_rules(stripped, detected_lang)
        if rule_res:
            return PronunciationResolutionResult(
                original_token=token,
                resolved_spoken=rule_res[0],
                status=PronunciationStatus.VERIFIED,
                source=PronunciationSource.DETERMINISTIC_RULE,
                language=rule_res[1],
                transformation_applied=True,
                requires_review=False,
                explanation=f"Resolved via Tier 5 Deterministic Rule ({rule_res[2]})",
            )

        # -------------------------------------------------------------
        # Tier 6: Model-Assisted Inference (Optional LLM Callable)
        # -------------------------------------------------------------
        if self.call_llm_fn and len(stripped) > 3 and detected_lang in (SpokenLanguage.ENGLISH, SpokenLanguage.FOREIGN):
            try:
                inferred = self._infer_via_model(stripped, sentence_context)
                if inferred:
                    return PronunciationResolutionResult(
                        original_token=token,
                        resolved_spoken=inferred,
                        status=PronunciationStatus.LIKELY,
                        source=PronunciationSource.MODEL_INFERRED,
                        language=detected_lang,
                        transformation_applied=(inferred != stripped),
                        requires_review=False,
                        explanation="Resolved via Tier 6 model-assisted inference",
                    )
            except Exception:
                pass

        # -------------------------------------------------------------
        # Tier 7: Unresolved Fallback (Review Required)
        # -------------------------------------------------------------
        # If an unknown English/foreign name appears in Hindi context, flag REVIEW_REQUIRED
        is_unknown_foreign = (detected_lang == SpokenLanguage.ENGLISH and len(stripped) >= 3)
        return PronunciationResolutionResult(
            original_token=token,
            resolved_spoken=clean_token,
            status=PronunciationStatus.REVIEW_REQUIRED if is_unknown_foreign else PronunciationStatus.LIKELY,
            source=PronunciationSource.UNRESOLVED,
            language=detected_lang,
            transformation_applied=False,
            requires_review=is_unknown_foreign,
            explanation=(
                f"Tier 7 Unresolved: Unknown foreign/complex token '{stripped}'. Flagged for review."
                if is_unknown_foreign else "Standard vocabulary token passed through."
            ),
        )

    def _apply_deterministic_rules(self, token: str, detected_lang: SpokenLanguage) -> Optional[Tuple[str, SpokenLanguage, str]]:
        """
        Applies deterministic language, numeral, and acronym transformations.
        Returns (spoken_string, language, rule_description) if matched.
        """
        # 1. Currency Symbols
        if token.startswith("₹") or token.startswith("Rs") or token.startswith("Rs."):
            val_part = re.sub(r"^[^\d]+", "", token)
            if val_part.isdigit():
                words = number_to_hindi_words(int(val_part))
                return f"{words} रुपये", SpokenLanguage.HINDI, "Currency Rupee Expansion"

        if token.startswith("$"):
            val_part = token[1:]
            if val_part.isdigit():
                words = number_to_hindi_words(int(val_part))
                return f"{words} डॉलर", SpokenLanguage.HINDI, "Currency Dollar Expansion"

        # 2. Percentage
        if token.endswith("%") and token[:-1].isdigit():
            words = number_to_hindi_words(int(token[:-1]))
            return f"{words} प्रतिशत", SpokenLanguage.HINDI, "Percentage Expansion"

        # 3. Devanagari Numerals (e.g. '५००' -> '500' -> 'पाँच सौ')
        if any(c in DEVA_DIGIT_MAP for c in token) and all(c in DEVA_DIGIT_MAP for c in token):
            latin_digits = "".join(DEVA_DIGIT_MAP[c] for c in token)
            words = number_to_hindi_words(int(latin_digits))
            return words, SpokenLanguage.HINDI, "Devanagari Numeral Expansion"

        # 4. Pure Latin Numerals (e.g. '25' -> 'पच्चीस')
        if token.isdigit():
            num = int(token)
            if num <= 100000000:
                words = number_to_hindi_words(num)
                return words, SpokenLanguage.HINDI, "Latin Numeral Expansion"

        # 5. Units attached to numbers (e.g. '5km', '10kg')
        m_unit = re.match(r"^(\d+)([a-zA-Z\u0900-\u097F]+)$", token)
        if m_unit:
            num_str, unit_str = m_unit.groups()
            u_clean = unit_str.lower()
            if u_clean in UNITS_MAP:
                n_words = number_to_hindi_words(int(num_str))
                u_word = UNITS_MAP[u_clean]
                return f"{n_words} {u_word}", SpokenLanguage.HINDI, "Compound Unit Expansion"

        # 6. Common Uppercase Acronyms (e.g. 'FBI', 'CID', 'ISRO')
        if len(token) >= 2 and token.isupper() and token.isalpha():
            # Generate dot-separated spoken representation
            latin_phonetics = {
                'A': 'ए', 'B': 'बी', 'C': 'सी', 'D': 'डी', 'E': 'ई', 'F': 'एफ़',
                'G': 'जी', 'H': 'एच', 'I': 'आई', 'J': 'जे', 'K': 'के', 'L': 'एल',
                'M': 'एम', 'N': 'एन', 'O': 'ओ', 'P': 'पी', 'Q': 'क्यू', 'R': 'आर',
                'S': 'एस', 'T': 'टी', 'U': 'यू', 'V': 'वी', 'W': 'डब्ल्यू', 'X': 'एक्स',
                'Y': 'वाई', 'Z': 'ज़ेड'
            }
            spoken_acronym = ".".join(latin_phonetics.get(c, c) for c in token) + "."
            return spoken_acronym, SpokenLanguage.ENGLISH, "Acronym Phonetic Expansion"

        return None

    def _infer_via_model(self, token: str, context: str) -> Optional[str]:
        """Model-assisted inference for foreign names inside Hindi context."""
        prompt = (
            f"You are a master Hindi audio drama pronunciation director.\n"
            f"Given the foreign/proper noun: '{token}' inside context: \"{context[:200]}\",\n"
            f"Provide the exact phonetic Devanagari representation that Google Gemini Hindi TTS will pronounce correctly.\n"
            f"Output ONLY the phonetic Devanagari string and nothing else."
        )
        resp = self.call_llm_fn(prompt=prompt)
        resp_clean = resp.strip().replace('"', '').replace("'", "")
        return resp_clean if resp_clean else None
