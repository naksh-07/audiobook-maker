#!/usr/bin/env python3
"""
Audiobook Factory - Pillar 3.6: Linguistic Sanitizer & Defense-in-Depth Guardrail.
Prevents LLM conversational chatter, refusals, English summaries, markdown fences,
and translation notes from ever leaking into Hindi translations and screenplay scripts.
"""

import re
from typing import Dict, Any, Tuple, Optional, List


# Known LLM refusal and meta-commentary patterns (case-insensitive)
REFUSAL_AND_META_PATTERNS = [
    r"i cannot provide a direct translation",
    r"i cannot translate",
    r"i can't translate",
    r"as an ai",
    r"as a language model",
    r"here is the (?:direct )?translation",
    r"here's the (?:direct )?translation",
    r"translation\s*:\s*",
    r"translator'?s?\s+note",
    r"note\s*:\s*certain terms",
    r"would you like a summary",
    r"would you like me to",
    r"scene overview",
    r"summary of the (?:scene|chapter|excerpt)",
    r"option \d+\s*:",
    r"key vocabulary used\s*:",
    r"let me know if you",
    r"hope this helps",
    r"certainly!?\s+here",
    r"sure,?\s+here",
]

COMPILED_META_PATTERNS = [re.compile(p, re.IGNORECASE) for p in REFUSAL_AND_META_PATTERNS]

# Permitted expressive vocal tags recognized natively by Gemini 3.1 Flash TTS
SUPPORTED_TTS_TAG_PATTERNS = [
    r"whispers?",
    r"shouting",
    r"shouts?",
    r"sighs?",
    r"gasp",
    r"laughs?",
    r"giggles?",
    r"crying",
    r"trembling(?:\s+voice)?",
    r"cold\s+menace",
    r"intimate(?:,\s*breathy)?",
    r"excitedly?",
    r"bored",
    r"reluctantly",
    r"amazed",
    r"curious",
    r"mischievously",
    r"panicked",
    r"sarcastic(?:ally)?",
    r"serious",
    r"tired",
    r"pause(?:=\d+(?:\.\d+)?)?",
    r"very\s+(?:fast|slow)",
    r"growl",
    r"groan",
    r"spits?(?:\s+blood)?",
    r"bellowing\s+rage",
    r"bellowing\s+battlecry",
    r"breathless[\s_]+exhaustion",
    r"combat[\s_]+strain",
    r"diaphragm[\s_]+strain",
    r"choked\s+gasp",
    r"guttural\s+grunt(?:\s+on\s+blade\s+deflect)?",
    r"ragged\s+heaving\s+pant",
    r"slow[\s_]+motion",
    r"mocking\s+chuckle",
    r"clears?\s+throat",
    r"coughs?",
    r"snickers?",
    r"panting",
    r"(?:short|long)\s+pause",
]
COMPILED_TTS_TAG_RE = re.compile(rf"^\[\s*(?:{'|'.join(SUPPORTED_TTS_TAG_PATTERNS)})\s*\]$", re.IGNORECASE)


def filter_bracketed_tags(match: re.Match) -> str:
    """Preserve valid Gemini TTS expressive tags; strip leaked Foley and Devanagari stage cues."""
    tag_str = match.group(0).strip()
    if COMPILED_TTS_TAG_RE.match(tag_str):
        return tag_str
    return ""


def count_devanagari_chars(text: str) -> int:
    """Count number of Devanagari Unicode code points in text."""
    return len(re.findall(r"[\u0900-\u097F]", text))


def count_latin_words(text: str) -> int:
    """Count number of standalone Latin words (3+ chars) in text."""
    return len(re.findall(r"\b[a-zA-Z]{3,}\b", text))


def strip_markdown_fences(text: str) -> str:
    """Strip ```markdown ... ``` and ``` ... ``` code blocks cleanly."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:markdown|text|json)?\s*\n?", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def strip_preamble_and_postamble(text: str) -> str:
    """Remove conversational opening/closing lines from LLM responses."""
    lines = text.splitlines()
    clean_lines: List[str] = []

    # Strip opening lines that are pure conversational chatter
    skipping_preamble = True
    for line in lines:
        s = line.strip()
        if skipping_preamble:
            if not s:
                continue
            is_meta = any(pat.search(s) for pat in COMPILED_META_PATTERNS)
            is_pure_latin_header = count_latin_words(s) > 3 and count_devanagari_chars(s) == 0
            if is_meta or is_pure_latin_header:
                continue
            skipping_preamble = False
        clean_lines.append(line)

    # Strip trailing lines that are pure conversational chatter
    while clean_lines:
        last = clean_lines[-1].strip()
        if not last:
            clean_lines.pop()
            continue
        is_meta = any(pat.search(last) for pat in COMPILED_META_PATTERNS)
        is_pure_latin_footer = count_latin_words(last) > 3 and count_devanagari_chars(last) == 0
        if is_meta or is_pure_latin_footer:
            clean_lines.pop()
        else:
            break

    return "\n".join(clean_lines).strip()


def validate_and_sanitize_translation(text: str, is_hindi: bool = True) -> Tuple[bool, str, str]:
    """
    Validate and clean translation text before writing to disk cache or chapter markdown.

    Returns:
        (is_valid: bool, cleaned_text: str, failure_reason: str)
    """
    if not text or not text.strip():
        return False, "", "Empty translation output received."

    # 1. Strip markdown fences
    cleaned = strip_markdown_fences(text)

    # 2. Check for explicit LLM refusal / commentary
    for pat in COMPILED_META_PATTERNS:
        match = pat.search(cleaned)
        if match:
            # If the refusal pattern occurs in pure English context
            matched_str = match.group(0)
            return False, "", f"LLM refusal/meta-commentary detected: '{matched_str}'"

    # 3. Strip preamble / postamble chatter
    cleaned = strip_preamble_and_postamble(cleaned)

    # 4. Devanagari purity guardrail for Hindi translations
    if is_hindi:
        dev_count = count_devanagari_chars(cleaned)
        latin_words = count_latin_words(cleaned)

        if dev_count < 20 and len(cleaned.split()) > 15:
            return False, "", f"Devanagari character density too low ({dev_count} devanagari characters for {len(cleaned.split())} words)."

        # Reject if heavy English text without proportional Devanagari
        if latin_words > 30 and dev_count < (latin_words * 2):
            return False, "", f"Excessive English vocabulary detected ({latin_words} words vs {dev_count} Devanagari characters)."

    return True, cleaned, ""


def sanitize_screenplay_segment(segment: Dict[str, Any], is_hindi: bool = True) -> Optional[Dict[str, Any]]:
    """
    Filter and sanitize a screenplay script segment before inclusion in screenplay JSON.
    Returns None if segment should be dropped (e.g. meta commentary, leaked English refusals).
    """
    if not isinstance(segment, dict):
        return None

    if segment.get("type") == "action":
        cleaned_seg = dict(segment)
        cleaned_seg["speaker"] = cleaned_seg.get("speaker") or "Foley"
        cleaned_seg["text"] = cleaned_seg.get("text") or "[ACTION]"
        return cleaned_seg

    text = segment.get("text", "").strip()
    if not text:
        return None

    # Strip leading/trailing markdown headers
    text = re.sub(r"^#+\s*", "", text)
    # Strip XML / HTML / SSML tags (e.g. <break.../>, <whisper>...</whisper>)
    text = re.sub(r"<[^>]+>", "", text)
    # Selectively preserve Gemini TTS vocal tags ([whispers], [shouting]); strip leaked non-vocal stage directions
    text = re.sub(r"\[[^\]]+\]", filter_bracketed_tags, text)
    # Strip inline markdown bold/italic asterisks and underscores (**word**, *word*, __word__, _word_)
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,3}([^_]+)_{1,3}", r"\1", text)
    text = re.sub(r"[*_~`#]+", "", text)
    # Collapse excessive character repeats to max 2 (e.g. "आहhhhh" -> "आहhh", "हूँ...." -> "हूँ..")
    text = re.sub(r"([a-zA-Z\u0900-\u097F])\1{2,}", r"\1\1", text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return None

    # Drop segment if it matches refusal / commentary patterns
    for pat in COMPILED_META_PATTERNS:
        if pat.search(text):
            return None

    # Strip bracketed tags temporarily for linguistic checks
    # (vocal tags like [whispers] or [bellowing battlecry] must not count as Latin words)
    text_no_tags = re.sub(r"\[[^\]]+\]", "", text).strip()
    if not text_no_tags:
        return None

    # If Hindi screenplay, drop pure English conversational sentences
    if is_hindi:
        eng_words = count_latin_words(text_no_tags)
        dev_chars = count_devanagari_chars(text_no_tags)

        # Drop segments that are pure English paragraphs
        if eng_words >= 6 and dev_chars < 5:
            return None

    cleaned_seg = dict(segment)
    cleaned_seg["text"] = text
    return cleaned_seg


# Unambiguous robotic literalisms and clinical loanwords eligible for deterministic normalization
UNAMBIGUOUS_CALQUE_REPAIRS = {
    r"सुनहरी\s+लड़की": "गोरी-चिट्टी लड़की",
    r"क[ुंँ]+वारी\s+चोटी": "कमसिन लड़की की चोटी",
    r"(?<![\u0900-\u097F])डिप्रेशन(?![\u0900-\u097F])": "उदासी का साया",
    r"(?<![\u0900-\u097F])ट्रॉमा(?![\u0900-\u097F])": "गहरा सदमा",
    r"(?<![\u0900-\u097F])स्ट्रेस(?![\u0900-\u097F])": "तनाव",
}

# Contextual dialectal / register expressions: valid in rustic/tavern/folklore dialogue, NEVER auto-replaced!
CONTEXTUAL_REGISTER_ADVISORIES = {
    r"सोने\s+की\s+लड़की": "Contextual poetic descriptor (सोने की लड़की) - preserved",
    r"(?<![\u0900-\u097F])नमस्ते(?![\u0900-\u097F])": "Contextual greeting (नमस्ते) - preserved for character voice",
    r"(?<![\u0900-\u097F])राम-राम(?![\u0900-\u097F])": "Contextual rustic greeting (राम-राम) - preserved for character voice",
    r"(?<![\u0900-\u097F])नमस्कार(?![\u0900-\u097F])": "Contextual greeting (नमस्कार) - preserved for character voice",
    r"(?<![\u0900-\u097F])दारू(?![\u0900-\u097F])": "Contextual rustic term (दारू) - preserved for peasant/tavern register",
}


def audit_literary_register(
    text: str,
    apply_substitutions: bool = False,
) -> Tuple[bool, str, List[str]]:
    """
    Meso-Tier Literary Register Guard:
    Scans generated Hindi text for robotic literalisms, clinical English loanwords,
    or immersion-breaking vocabulary.
    By default (apply_substitutions=False), it acts as a non-destructive diagnostic auditor.
    When apply_substitutions=True is explicitly requested, only UNAMBIGUOUS calques are replaced.
    Legitimate literary and dialectal choices ('नमस्ते', 'राम-राम', 'नमस्कार', 'दारू', 'सोने की लड़की')
    are NEVER automatically overwritten.
    Returns (is_clean, cleaned_text, detected_warnings).
    """
    if not text:
        return True, text, []

    warnings: List[str] = []
    cleaned_text = text

    # Check unambiguous calques (auto-repaired only if apply_substitutions is True)
    for pattern, replacement in UNAMBIGUOUS_CALQUE_REPAIRS.items():
        if re.search(pattern, cleaned_text):
            matches = re.findall(pattern, cleaned_text)
            warnings.append(f"Antipattern detected: {matches[0]} -> normalized to '{replacement}'")
            if apply_substitutions:
                cleaned_text = re.sub(pattern, replacement, cleaned_text)

    # Check contextual register advisories (never mutated, informative note only)
    for pattern, advisory_desc in CONTEXTUAL_REGISTER_ADVISORIES.items():
        if re.search(pattern, cleaned_text):
            matches = re.findall(pattern, cleaned_text)
            warnings.append(f"Advisory register observation: {matches[0]} ({advisory_desc})")

    is_clean = len(warnings) == 0
    return is_clean, cleaned_text, warnings
