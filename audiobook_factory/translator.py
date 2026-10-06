#!/usr/bin/env python3
"""
Audiobook Factory - Pillar 2: Literary English-to-Hindi Translation Engine.
Translates English novels into dramatic, spoken Hindustani suitable for audiobooks.
Features Two-Pass Glossary Memory for character names, tone, and honorific consistency (Aap/Tum/Tu).
"""

import os
import re
import time
import json
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from audiobook_factory.model_manager import (
    get_model_manager,
    TaskType,
    LLMUnavailableError,
    ModelTierFloorBreachError,
)

from audiobook_factory.logger import logger
from audiobook_factory.chunking_policy import chunking_policy

ADULT_LITERARY_MODE = os.environ.get("ADULT_LITERARY_MODE", "true").lower() in ("true", "1", "yes")
TRANSLATOR_VERSION = "2.1"
PROMPT_VERSION = "2.1.0"


from audiobook_factory.key_manager import get_persistent_key_pool
from audiobook_factory.cadence import get_stealth_sdk_headers
from audiobook_factory.advisory_lexicon import get_advisory_db

pool = get_persistent_key_pool()


from audiobook_factory.safety import get_dramatic_fiction_framing
from audiobook_factory.llm_client import call_gemini as core_call_gemini, GeminiPayloadError


def get_api_key() -> str:
    return pool.get_key(service="text")


def call_gemini(
    prompt: str,
    system_instruction: str = "",
    model: Optional[str] = None,
    json_mode: bool = False,
    response_schema: Optional[Dict[str, Any]] = None,
    max_retries: int = 8,
    thinking_budget: Optional[int] = None,
    task_type: Optional[TaskType] = None,
    **kwargs,
) -> str:
    """Send request to Gemini API with automatic key rotation, retry and high-tier model fallback.
    Delegates to centralized audiobook_factory.llm_client.
    Temperature is intentionally NOT specified here — llm_client resolves it adaptively
    per TaskType.TRANSLATION (currently 0.85 for literary expressive range).
    max_output_tokens=16384 to accommodate Devanagari output (~1.4x English token expansion).
    """
    if task_type is None:
        sys_lower = (system_instruction or "").lower()
        if json_mode or any(k in sys_lower for k in ("audit", "evaluat", "parser", "detect", "review", "check")):
            resolved_task_type = TaskType.AUDITING
        else:
            resolved_task_type = TaskType.TRANSLATION
    else:
        resolved_task_type = task_type

    effective_retries = max_retries

    mime = "application/json" if json_mode else "text/plain"
    res = core_call_gemini(
        prompt=prompt,
        system_instruction=system_instruction if system_instruction else None,
        task_type=resolved_task_type,
        response_mime_type=mime,
        # temperature intentionally omitted — llm_client uses task-adaptive 0.85
        max_output_tokens=16384,
        max_retries=effective_retries,
        model=model,
        response_schema=response_schema,
        timeout_sec=kwargs.get("timeout_sec", 90.0),
        return_raw_text=True,
        thinking_budget=thinking_budget,
    )
    if isinstance(res, str):
        return res
    return json.dumps(res, ensure_ascii=False)


def normalize_translated_lexicon(text: str, glossary: Dict[str, str] | Dict[str, Any]) -> str:
    """
    Canonical Devanagari Lexicon Normalizer.
    Replaces glossary terms and character names using proper word boundaries.
    Supports both flat dictionaries and nested schema glossaries.
    """
    if not text or not glossary:
        return text

    replacements: Dict[str, str] = {}
    if isinstance(glossary, dict):
        if "characters" in glossary or "locations_and_terms" in glossary:
            # Nested glossary format
            chars = glossary.get("characters", [])
            if isinstance(chars, list):
                for item in chars:
                    if isinstance(item, dict):
                        eng = item.get("english_name")
                        hin = item.get("hindi_name")
                        if eng and hin:
                            replacements[eng] = hin
            terms = glossary.get("locations_and_terms", {})
            if isinstance(terms, dict):
                replacements.update(terms)
        else:
            # Flat dictionary format
            replacements = {k: v for k, v in glossary.items() if isinstance(k, str) and isinstance(v, str)}

    # Sort replacements by length descending to match longest phrases first
    sorted_keys = sorted(replacements.keys(), key=len, reverse=True)
    for k in sorted_keys:
        v = replacements[k]
        pattern = rf"(?<![\w\u0900-\u097F]){re.escape(k)}(?![\w\u0900-\u097F])"
        text = re.sub(pattern, v, text)

    return text


def _extract_character_lexicon_agent(sample_text: str, book_metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Agent A: Extract character names, canonical Devanagari spellings, gender, and aliases."""
    fiction_framing = get_dramatic_fiction_framing(
        title=book_metadata.get("title"), author=book_metadata.get("author")
    )
    sys_prompt = (
        fiction_framing +
        "You are an expert Literary Casting Director and Lexicographer for audiobooks.\n"
        "Identify all characters, monikers, and prominent figures in this passage and provide accurate, literary Devanagari spellings.\n\n"
        "NON-NEGOTIABLE ENTITY PARTITION & TRANSLITERATION RULES:\n"
        "1. PERSONAL GIVEN NAMES & SURNAMES (e.g. Victor -> विक्टर, Marcus -> मार्कस, Elena -> एलेना):\n"
        "   Preserve foreign proper names via phonetic transliteration into clean Devanagari. NEVER replace them with Indian village names.\n"
        "2. DESCRIPTIVE MONIKERS, OCCUPATIONS & EPITHETS (e.g. 'The Spotty-faced Man', 'The Butcher', 'The Alderman', 'The Innkeeper', 'The Blacksmith', 'The Beggar'):\n"
        "   CRITICAL: DO NOT transliterate descriptive phrases phonetically into cartoonish comic-book Hinglish (STRICTLY BANNED: 'स्पॉटी-फेस्ड मैन', 'द बुचर', 'द इनकीपर')!\n"
        "   Instead, TRANSLATE descriptive epithets and occupations into natural, evocative Hindustani:\n"
        "   - 'The Spotty-faced Man' -> 'दाग़दार चेहरे वाला आदमी' (या 'चेचक के दाग़ों वाला आदमी')\n"
        "   - 'The Butcher' -> 'कसाई'\n"
        "   - 'The Alderman' -> 'एल्डरमैन' (या 'नगर प्रमुख')\n"
        "   - 'The Barman' / 'Innkeeper' -> 'सरायवाला' (या 'मदिरालय वाला')\n"
        "   - 'The Blacksmith' -> 'लोहार'\n"
        "3. WORLD-ANCHOR RULE: For foreign/fantasy universes, NEVER use Indian rural caste/panchayat vocabulary ('पंच जी', 'लंबरदार', 'पटवारी')."
    )
    prompt = f"""Book Title: {book_metadata.get('title', 'Unknown')}
Author: {book_metadata.get('author', 'Unknown')}

Sample Passage:
\"\"\"
{sample_text[:6000]}
\"\"\"

Output JSON: A list of objects for every character or prominent figure discovered:
- "english_name": string (e.g. "Marcus", "The Butcher", "The Spotty-faced Man")
- "hindi_name": Devanagari spelling or translation adhering to the rules above (e.g. "कसाई", "दाग़दार चेहरे वाला आदमी", "मार्कस")
- "gender": "male" | "female" | "other"
- "aliases": list of strings (alternative names, titles, nicknames)
- "voice_style": brief description of speech tone (e.g. "gruff, calm, authoritative")
"""
    try:
        raw = call_gemini(prompt, system_instruction=sys_prompt, json_mode=True)
        res = json.loads(raw) if raw else []
        if isinstance(res, dict) and "characters" in res:
            res = res["characters"]
        return res if isinstance(res, list) else []
    except Exception as e:
        logger.warning(f"  [!] Character Lexicon Agent notice: {e}")
        return []


def _extract_sociolects_and_honorifics_agent(
    sample_text: str, book_metadata: Dict[str, Any], characters: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Agent B: Determine Hindustani sociolect archetypes, pronoun levels ('तू'/'तुम'/'आप'), and relational dynamics."""
    fiction_framing = get_dramatic_fiction_framing(
        title=book_metadata.get("title"), author=book_metadata.get("author")
    )
    sys_prompt = (
        fiction_framing +
        "You are an expert Hindustani Dramaturge and Dialogue Coach.\n"
        "Analyze character power hierarchies and assign authentic Hindustani sociolect archetypes, "
        "takiya-kalam speech quirks, and mutual pronoun levels ('आप', 'तुम', or 'तू')."
    )
    chars_str = json.dumps([c.get("english_name") for c in characters if isinstance(c, dict)], ensure_ascii=False)
    prompt = f"""Known Characters: {chars_str}

Sample Passage:
\"\"\"
{sample_text[:6000]}
\"\"\"

Output JSON: An object with:
1. "character_sociolects": List of objects:
   - "english_name": string
   - "recommended_pronoun_level": default how others address them ("aap", "tum", or "tu")
   - "hindustani_archetype": "COLD_CYNIC" | "CAUSTIC_ARISTOCRAT" | "THARKI_BARD" | "KHAANTI_GOON" | "MAKKAR_DALAL" | "GRUFF_SOLDIER" | "NEUTRAL"
   - "speech_quirks": brief takiya-kalam or cadence style (e.g. "dry laconic sarcasm with heavy grunts", "Lucknowi flattery")
2. "relationships": List of pairs describing who addresses whom as "aap", "tum", or "tu".
"""
    try:
        raw = call_gemini(prompt, system_instruction=sys_prompt, json_mode=True)
        res = json.loads(raw) if raw else {}
        sociolects = res.get("character_sociolects", []) if isinstance(res, dict) else []
        relationships = res.get("relationships", []) if isinstance(res, dict) else []
        return sociolects, relationships
    except Exception as e:
        logger.warning(f"  [!] Sociolects & Honorifics Agent notice: {e}")
        return [], []


def _extract_world_terminology_agent(
    sample_text: str, book_metadata: Dict[str, Any]
) -> Tuple[Dict[str, str], str]:
    """Agent C: Extract world terminology, locations, weapons, factions, and overall narrative tone."""
    fiction_framing = get_dramatic_fiction_framing(
        title=book_metadata.get("title"), author=book_metadata.get("author")
    )
    sys_prompt = (
        fiction_framing +
        "You are a Worldbuilding Lexicographer and Literary Lore Translator.\n"
        "WORLD-ANCHOR RULE: For foreign/fantasy universes, do NOT replace European currency or civic titles with Indian village terms "
        "('अशर्फी', 'पंच जी', 'लंबरदार'). Currency should be 'सिक्के/मुद्राएं', civic titles should be 'मेयर/एल्डरमैन/नगर प्रमुख'.\n"
        "SPOKEN DICTION & ANTI-SANSKRITIZATION: Translate everyday items into natural spoken Hindustani ('looking glass' -> 'आईना', 'ale/beer' -> 'मदिरा/बीयर', 'shilling' -> 'सिक्के/शिलिंग'). "
        "STRICTLY FORBIDDEN to use textbook formal Sanskrit words like 'दर्पण' for gritty tavern objects."
    )
    prompt = f"""Book Title: {book_metadata.get('title', 'Unknown')}
Author: {book_metadata.get('author', 'Unknown')}

Sample Passage:
\"\"\"
{sample_text[:6000]}
\"\"\"

Output JSON: An object with:
1. "locations_and_terms": Map of English terms to their consistent Hindi Devanagari or translated equivalent.
2. "general_tone": Description of narrative tone (e.g. "dark fantasy, dramatic, contemporary Hindustani").
"""
    try:
        raw = call_gemini(prompt, system_instruction=sys_prompt, json_mode=True)
        res = json.loads(raw) if raw else {}
        terms = res.get("locations_and_terms", {}) if isinstance(res, dict) else {}
        tone = res.get("general_tone", "Cinematic Hindustani") if isinstance(res, dict) else "Cinematic Hindustani"
        return terms, tone
    except Exception as e:
        logger.warning(f"  [!] World Terminology Agent notice: {e}")
        return {}, "Cinematic Hindustani"


def generate_book_glossary(sample_chapter_text: str, book_metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pass 1: Concurrent Multi-Agent Book Glossary Generator.
    Deconstructs pre-production into 3 parallel specialist agents across the key pool:
    - Agent A: Character & Spelling Lexicographer
    - Agent B: Sociolect & Honorific Dramaturge
    - Agent C: World Terminology & Lore Translator
    """
    from concurrent.futures import ThreadPoolExecutor
    import json_repair

    chars: List[Dict[str, Any]] = []
    sociolects: List[Dict[str, Any]] = []
    relationships: List[Dict[str, Any]] = []
    terms: Dict[str, str] = {}
    general_tone: str = "Cinematic Hindustani"

    with ThreadPoolExecutor(max_workers=3) as executor:
        f_lexicon = executor.submit(_extract_character_lexicon_agent, sample_chapter_text, book_metadata)
        f_terms = executor.submit(_extract_world_terminology_agent, sample_chapter_text, book_metadata)

        chars = f_lexicon.result()
        terms, general_tone = f_terms.result()

        # Agent B consumes known characters from Agent A
        sociolects, relationships = _extract_sociolects_and_honorifics_agent(sample_chapter_text, book_metadata, chars)

    # Merge sociolect attributes into character records
    socio_map = {s.get("english_name"): s for s in sociolects if isinstance(s, dict) and "english_name" in s}
    for c in chars:
        cname = c.get("english_name")
        if cname in socio_map:
            s_data = socio_map[cname]
            c["recommended_pronoun_level"] = s_data.get("recommended_pronoun_level", "tum")
            c["hindustani_archetype"] = s_data.get("hindustani_archetype", "NEUTRAL")
            c["speech_quirks"] = s_data.get("speech_quirks", "")

    glossary = {
        "characters": chars,
        "relationships": relationships,
        "locations_and_terms": terms,
        "general_tone": general_tone,
    }
    return glossary


def _translate_single_block(
    text_block: str,
    glossary: Dict[str, Any],
    block_title: str = "",
    preceding_context: str = "",
    model: Optional[str] = None,
    adult_mode: Optional[bool] = None,
    book_dna: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Room 2: 4-Agent Dramatic Translation Collective Coordinator.
    Coordinates LiteraryDraftTranslator, HindustaniCadenceSpecialist,
    SubtextAndIdiomDramaturge, and TranslationQualityCritic.

    Core Invariants:
    - LITERARY ANTI-BOWDLERIZATION MANDATE: NEVER sanitize, soften, or bowdlerize raw violence, visceral combat, or intimacy.
    - DUAL-RULE INVARIANT ('NOTHING ABOVE SOURCE'):
      * When source is Classical / Heritage Literature:
        Preserve sacred authorial dignity, emotional pathos, and authentic regional cadence.
        Zero modern vulgar street slang or tapori profanities.
      * When source is Raw Unrated / Visceral Fiction:
        19-TO-21 AMPLIFICATION! Faithfully preserve raw street profanities ('गांड', 'चूतड़'), visceral combat gore,
        and unvarnished somatic intimacy without sanitization or puritanical moralizing.
    - 70/30 ANTI-PARODY INVARIANT: Maintain a strict 70% Canon Sacredness / 30% Sensory Desi Amplification ratio.
    - TU <-> MAAI-BAAP DYNAMIC POWER SHIFT: Respect organic status transitions.
    - SOMATIC INTIMACY: Preserve raw physical sensory depth.
    """
    if not model:
        model = get_model_manager().resolve_active_model(TaskType.TRANSLATION)
    if adult_mode is None:
        adult_mode = os.environ.get("ADULT_LITERARY_MODE", "true").lower() in ("true", "1", "yes")

    from audiobook_factory.translation.agents import get_translation_collective

    eff_dna = book_dna or (glossary.get("book_dna") if isinstance(glossary, dict) else None)
    collective = get_translation_collective(model=model)
    return collective.translate_block(
        text_block=text_block,
        glossary=glossary,
        block_title=block_title,
        preceding_context=preceding_context,
        adult_mode=adult_mode,
        book_dna=eff_dna,
    )


def _retrieve_chapter_memory_in_translator(
    project_dir: Path,
    source_text: str,
    block_label: str,
    glossary: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Step 1 (Pre-Translation READ): Retrieves the selective 7-tier + Salience MemoryContext
    for a chapter/block BEFORE translation runs, without mutating or saving MemoryStore.
    """
    try:
        from audiobook_factory.translation.book_bible import BookBible
        from audiobook_factory.translation.memory import (
            MemoryStore,
            MemoryRetriever,
        )

        bible = BookBible.load_from_project(project_dir)
        if glossary and not bible.characters:
            bible.import_from_legacy_glossary(glossary)
            bible.save(project_dir)

        store_path = MemoryStore.default_store_path(project_dir)
        store = MemoryStore.load(store_path, book_bible=bible)

        m = re.search(r"(\d+)", block_label or "")
        seq_idx = int(m.group(1)) if m else max(1, store.memory_version + 1)
        scene_id = block_label or f"scene_{seq_idx:03d}"

        mem_ctx = MemoryRetriever.retrieve_for_scene(
            store=store,
            book_bible=bible,
            chapter=seq_idx,
            scene_id=scene_id,
            scene_text=source_text,
        )
        return mem_ctx.get_prompt_context()
    except Exception as e:
        logger.warning(f"  [!] Pre-translation memory retrieval notice for {block_label}: {e}")
        return ""


def _commit_chapter_memory_in_translator(
    project_dir: Path,
    source_text: str,
    block_label: str,
    glossary: Optional[Dict[str, Any]] = None,
    model: Optional[str] = None,
    call_llm_fn: Optional[Any] = None,
) -> None:
    """
    Step 2 (Post-Translation EXTRACT -> VALIDATE -> COMMIT): Extracts and commits scene
    events AFTER translation succeeds so mid-chapter failures never leave uncommitted state on disk.
    """
    try:
        from audiobook_factory.translation.book_bible import BookBible
        from audiobook_factory.translation.memory import (
            MemoryStore,
            MemoryRetriever,
            EventExtractor,
        )

        bible = BookBible.load_from_project(project_dir)
        if glossary and not bible.characters:
            bible.import_from_legacy_glossary(glossary)

        store_path = MemoryStore.default_store_path(project_dir)
        store = MemoryStore.load(store_path, book_bible=bible)

        m = re.search(r"(\d+)", block_label or "")
        seq_idx = int(m.group(1)) if m else max(1, store.memory_version + 1)
        scene_id = block_label or f"scene_{seq_idx:03d}"

        already_committed = any(c.scene_id == scene_id for c in store.commit_history)
        if not already_committed and source_text.strip():
            _, resolved_loc = MemoryRetriever.infer_active_entities(
                scene_text=source_text,
                store=store,
                book_bible=bible,
            )
            known_chars = (
                list(bible.characters.keys())
                if isinstance(bible.characters, dict)
                else [c.canonical_name for c in bible.characters]
            )
            eff_llm_fn = call_llm_fn or (
                lambda prompt, system_instruction="", json_mode=True, **kw: call_gemini(
                    prompt=prompt,
                    system_instruction=system_instruction,
                    model=model,
                    json_mode=json_mode,
                )
            )
            events, _ = EventExtractor.extract_scene_events(
                scene_text=source_text,
                chapter=seq_idx,
                scene_id=scene_id,
                known_characters=known_chars,
                location=resolved_loc,
                call_llm_fn=eff_llm_fn,
            )
            store.commit_scene_memory(
                scene_id=scene_id,
                chapter=seq_idx,
                events=events,
                source_text=source_text,
                book_bible=bible,
                location=resolved_loc,
            )
            store.save(store_path)
            bible.save(project_dir)
    except Exception as e:
        logger.error(f"  [!] Post-translation memory commit failed for {block_label}: {e}", exc_info=True)


def _sync_chapter_memory_in_translator(
    project_dir: Path,
    source_text: str,
    block_label: str,
    glossary: Optional[Dict[str, Any]] = None,
    commit_after: bool = True,
    call_llm_fn: Optional[Any] = None,
) -> str:
    """Backward-compatible helper retrieving prompt context and optionally committing."""
    prompt_block = _retrieve_chapter_memory_in_translator(
        project_dir=project_dir,
        source_text=source_text,
        block_label=block_label,
        glossary=glossary,
    )
    if commit_after:
        _commit_chapter_memory_in_translator(
            project_dir=project_dir,
            source_text=source_text,
            block_label=block_label,
            glossary=glossary,
            call_llm_fn=call_llm_fn,
        )
    return prompt_block


def translate_chapter(
    chapter_text: str,
    glossary: Dict[str, Any],
    chapter_title: str = "",
    preceding_context: str = "",
    model: Optional[str] = None,
    project_dir: Optional[Path] = None,
) -> str:
    """Pass 2: Sense-for-sense literary translation of a single chapter into spoken Hindustani."""
    if not model:
        model = get_model_manager().resolve_active_model(TaskType.TRANSLATION)
    from audiobook_factory.sanitizer import validate_and_sanitize_translation
    cache_dir = None
    effective_context = preceding_context
    block_label = chapter_title or "scene_001"
    if project_dir:
        cache_dir = Path(project_dir) / "translation" / ".cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        # Step 1: READ ONLY before translation
        mem_block = _retrieve_chapter_memory_in_translator(
            project_dir=Path(project_dir),
            source_text=chapter_text,
            block_label=block_label,
            glossary=glossary,
        )
        if mem_block:
            effective_context = f"{preceding_context}\n\n{mem_block}".strip() if preceding_context else mem_block

    words = chapter_text.split()
    # Enforce strict chunking policy (750 words ceiling) to prevent cognitive fatigue & lost-in-the-middle
    if len(words) <= chunking_policy.TRANSLATION_MAX_WORDS:
        cache_file = (cache_dir / f"{chapter_title}_full.txt") if cache_dir and chapter_title else None
        if cache_file and cache_file.exists() and cache_file.stat().st_size > 10:
            with open(cache_file, "r", encoding="utf-8") as f:
                cached_text = f.read().strip()
            is_valid, cleaned_cached, err = validate_and_sanitize_translation(cached_text, is_hindi=True)
            if is_valid:
                print(f"    [CACHED] Chapter loaded from cache ({len(cleaned_cached)} chars).", flush=True)
                if project_dir:
                    _commit_chapter_memory_in_translator(
                        project_dir=Path(project_dir),
                        source_text=chapter_text,
                        block_label=block_label,
                        glossary=glossary,
                        model=model,
                        call_llm_fn=None,
                    )
                return cleaned_cached
            else:
                print(f"    [INVALID CACHE] Cache failed guardrail ({err}). Re-translating...", flush=True)

        res = _translate_single_block(chapter_text, glossary, chapter_title, effective_context, model)
        if cache_file:
            with open(cache_file, "w", encoding="utf-8") as f:
                f.write(res)
        if project_dir:
            _commit_chapter_memory_in_translator(
                project_dir=Path(project_dir),
                source_text=chapter_text,
                block_label=block_label,
                glossary=glossary,
                model=model,
            )
        return res

    # For long chapters, split across paragraph boundaries using TRANSLATION_TARGET_WORDS (650 words)
    paragraphs = chapter_text.split("\n\n")
    chunks: List[str] = []
    curr_chunk: List[str] = []
    curr_words = 0

    for p in paragraphs:
        p_words = len(p.split())
        if curr_words + p_words > chunking_policy.TRANSLATION_TARGET_WORDS and curr_chunk:
            chunks.append("\n\n".join(curr_chunk))
            curr_chunk = [p]
            curr_words = p_words
        else:
            curr_chunk.append(p)
            curr_words += p_words
    if curr_chunk:
        chunks.append("\n\n".join(curr_chunk))

    translated_pieces: List[str] = []
    rolling_ctx = effective_context
    for i, chunk in enumerate(chunks, 1):
        chunk_words = len(chunk.split())
        import hashlib
        chunk_hash = hashlib.sha256(chunk.encode("utf-8")).hexdigest()[:12]
        chunk_fp = f"{chunk_hash}:{TRANSLATOR_VERSION}:{PROMPT_VERSION}:{model}"

        cache_file = (cache_dir / f"{chapter_title}_part_{i}.txt") if cache_dir and chapter_title else None
        fp_file = (cache_dir / f"{chapter_title}_part_{i}.fp") if cache_dir and chapter_title else None

        if cache_file and cache_file.exists() and cache_file.stat().st_size > 10 and fp_file and fp_file.exists():
            try:
                with open(fp_file, "r", encoding="utf-8") as f:
                    saved_fp = f.read().strip()
                if saved_fp == chunk_fp:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        trans_part = f.read().strip()
                    is_valid, cleaned_part, err = validate_and_sanitize_translation(trans_part, is_hindi=True)
                    if is_valid:
                        translated_pieces.append(cleaned_part)
                        rolling_ctx = cleaned_part[-500:]
                        print(f"    [CACHED] [Part {i}/{len(chunks)}] Loaded from cache ({len(cleaned_part)} chars).", flush=True)
                        continue
                    else:
                        print(f"    [INVALID CACHE] [Part {i}/{len(chunks)}] Cache failed guardrail ({err}). Re-translating...", flush=True)
                else:
                    print(f"    [STALE CACHE] [Part {i}/{len(chunks)}] Cache fingerprint mismatch. Re-translating...", flush=True)
            except Exception as e:
                logger.warning(f"  [!] Cache fingerprint read notice for {chapter_title}_part_{i}: {e}")


        print(f"    -> [Part {i}/{len(chunks)}] Translating {chunk_words} words...", flush=True)
        chunk_title = f"{chapter_title} (Part {i}/{len(chunks)})" if chapter_title else f"Part {i}/{len(chunks)}"
        trans_part = _translate_single_block(chunk, glossary, chunk_title, rolling_ctx, model)
        if cache_file:
            with open(cache_file, "w", encoding="utf-8") as f:
                f.write(trans_part)
            if fp_file:
                with open(fp_file, "w", encoding="utf-8") as f:
                    f.write(chunk_fp)
        translated_pieces.append(trans_part)
        rolling_ctx = trans_part[-500:]
    full_trans = "\n\n".join(translated_pieces)
    if glossary:
        full_trans = normalize_translated_lexicon(full_trans, glossary)
    if project_dir:
        _commit_chapter_memory_in_translator(
            project_dir=Path(project_dir),
            source_text=chapter_text,
            block_label=block_label,
            glossary=glossary,
            model=model,
        )
    return full_trans


def translate_book_project(
    project_dir: Path,
    model: Optional[str] = None,
    use_intelligent_pipeline: bool = True,
    force_gate: bool = False,
    chapters: Optional[List[int]] = None,
) -> Path:
    """
    Batch translates all extracted chapters in a project into Hindi.
    Defaults to IntelligentTranslationPipeline (Pillar 2 Intelligence) with
    automatic fail-safe gate certification and full artifact persistence.
    """
    if not model:
        model = get_model_manager().resolve_active_model(TaskType.TRANSLATION)
    extracted_dir = project_dir / "extracted"
    if not extracted_dir.exists() and (project_dir / "chapters").exists():
        extracted_dir = project_dir / "chapters"
    meta_file = project_dir / "metadata.json"

    if not extracted_dir.exists() or not meta_file.exists():
        raise FileNotFoundError(f"Project not found or unextracted: {project_dir}")

    with open(meta_file, "r", encoding="utf-8") as f:
        meta = json.load(f)

    trans_dir = project_dir / "translation"
    trans_dir.mkdir(parents=True, exist_ok=True)
    glossary_file = trans_dir / "glossary.json"

    # Step 1: Load or generate glossary
    if glossary_file.exists():
        print(f"[*] Loading existing translation glossary: {glossary_file}", flush=True)
        with open(glossary_file, "r", encoding="utf-8") as f:
            glossary = json.load(f)
    else:
        chap_files = sorted(extracted_dir.glob("chapter_*.md"))
        if not chap_files:
            chap_files = sorted(extracted_dir.glob("*.md"))
        if not chap_files:
            raise FileNotFoundError("No chapter markdown files found in extracted directory.")

        first_chap_file = chap_files[0]
        for cf in chap_files:
            try:
                if len(cf.read_text(encoding="utf-8").split()) > 300:
                    first_chap_file = cf
                    break
            except Exception:
                pass

        with open(first_chap_file, "r", encoding="utf-8") as f:
            first_chap_text = f.read()

        print("[*] Generating Pass-1 Character & Honorifics Glossary via Gemini...", flush=True)
        glossary = generate_book_glossary(first_chap_text, meta)
        with open(glossary_file, "w", encoding="utf-8") as f:
            json.dump(glossary, f, ensure_ascii=False, indent=2)
        print(f"[+] Saved glossary with {len(glossary.get('characters', []))} characters -> {glossary_file}", flush=True)

    # Seed BookBible & MemoryStore 2.0 from project glossary
    try:
        from audiobook_factory.translation.book_bible import BookBible
        from audiobook_factory.translation.memory import MemoryStore

        bible = BookBible.load_from_project(project_dir)
        if not bible.book_title:
            bible.book_title = str(meta.get("title", ""))
        if glossary and not bible.characters:
            bible.import_from_legacy_glossary(glossary)
        bible.save(project_dir)
        store_path = MemoryStore.default_store_path(project_dir)
        store = MemoryStore.load(store_path, book_bible=bible)
        store.save(store_path)
    except Exception:
        pass

    chapter_files = sorted(extracted_dir.glob("chapter_*.md"))
    if chapters:
        chapter_files = [
            cf for cf in chapter_files
            if any(cf.stem == f"chapter_{ch:03d}" or cf.stem == f"chapter_{ch}" or cf.stem.endswith(f"_{ch:03d}") for ch in chapters)
        ]
    total = len(chapter_files)

    # Step 2: Intelligent Pipeline Translation (Default, Decision A1)
    if use_intelligent_pipeline:
        print(f"[*] Starting Intelligent Literary Translation Pipeline for {total} chapters using {model}...", flush=True)
        from audiobook_factory.translation import IntelligentTranslationPipeline

        pipeline = IntelligentTranslationPipeline(project_dir=project_dir, model=model)

        for idx, chap_file in enumerate(chapter_files, 1):
            target_file = trans_dir / f"{chap_file.stem}_hi.md"
            with open(chap_file, "r", encoding="utf-8") as f:
                content = f.read()

            m_ch = re.search(r"chapter_(\d+)", chap_file.stem)
            ch_num = int(m_ch.group(1)) if m_ch else idx

            print(f"[*] [{idx}/{total}] Processing Intelligent Translation for {chap_file.name} (Chapter {ch_num})...", flush=True)
            pipeline.translate_chapter(
                chapter_text=content,
                chapter_num=ch_num,
                chapter_title=chap_file.stem,
                call_llm_fn=call_gemini,
                use_cache=True,
                force_gate=force_gate,
            )
            print(f"[+] [{idx}/{total}] Successfully translated and certified -> {target_file.name}", flush=True)

        print(f"[DONE] All chapters intelligently translated into Hindi successfully -> {trans_dir}")
        return trans_dir

    # Fallback: Legacy Chunk-Based Translation Loop
    print(f"[*] Starting legacy chunk translation of {total} chapters using {model}...", flush=True)
    preceding_summary = f"Novel title: {meta.get('title')}. Setting out on journey."

    for idx, chap_file in enumerate(chapter_files, 1):
        target_file = trans_dir / f"{chap_file.stem}_hi.md"
        if target_file.exists() and target_file.stat().st_size > 100:
            print(f"[-] Chapter {idx}/{total} already translated: {target_file.name} (Skipping)", flush=True)
            try:
                with open(chap_file, "r", encoding="utf-8") as src_f:
                    _sync_chapter_memory_in_translator(
                        project_dir=project_dir,
                        source_text=src_f.read(),
                        block_label=chap_file.stem,
                        glossary=glossary,
                    )
                with open(target_file, "r", encoding="utf-8") as f:
                    skipped_tail = f.read().split()[-250:]
                    if skipped_tail:
                        preceding_summary = f"Previous chapter ending: {' '.join(skipped_tail)}"
            except Exception:
                pass
            continue

        with open(chap_file, "r", encoding="utf-8") as f:
            content = f.read()
        word_count = len(content.split())

        print(f"[*] [{idx}/{total}] Translating {chap_file.name} ({word_count} words)...", flush=True)

        trans_content = translate_chapter(
            chapter_text=content,
            glossary=glossary,
            chapter_title=chap_file.stem,
            preceding_context=preceding_summary,
            model=model,
            project_dir=project_dir,
        )

        with open(target_file, "w", encoding="utf-8") as f:
            f.write(trans_content + "\n")

        # Maintain rolling narrative context across chapter boundaries
        tail_words = trans_content.split()[-250:] if trans_content else []
        if tail_words:
            preceding_summary = f"Previous chapter ending: {' '.join(tail_words)}"

        print(f"[+] [{idx}/{total}] Successfully translated -> {target_file.name}", flush=True)
        time.sleep(2.0)

    print(f"[DONE] All chapters translated into Hindi successfully -> {trans_dir}")
    return trans_dir



def translate_chapter_intelligent(
    chapter_text: str,
    project_dir: Path,
    chapter_num: int = 1,
    chapter_title: str = "Chapter",
    model: Optional[str] = None,
    use_cache: bool = True,
) -> Tuple[str, List[Any]]:
    """
    Executes Pillar 2 Literary Translation Intelligence Pipeline on a chapter.
    Integrates Book Bible, Entity Discovery, Transition-Driven Scene Planning,
    Dedicated Evaluators (Gates T0-T11), and Tiered Self-Healing Repair.
    """
    if not model:
        model = get_model_manager().resolve_active_model(TaskType.TRANSLATION)
    from audiobook_factory.translation import IntelligentTranslationPipeline
    pipeline = IntelligentTranslationPipeline(project_dir=project_dir, model=model)
    return pipeline.translate_chapter(
        chapter_text=chapter_text,
        chapter_num=chapter_num,
        chapter_title=chapter_title,
        call_llm_fn=call_gemini,
        use_cache=use_cache,
    )

