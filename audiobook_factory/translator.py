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


DEFAULT_MODEL = os.environ.get("GEMINI_TEXT_MODEL", "gemini-3.8-flash")
MODEL_CANDIDATES = ("gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash", "gemini-2.5-flash", "gemini-3.1-flash-lite")
ADULT_LITERARY_MODE = os.environ.get("ADULT_LITERARY_MODE", "true").lower() in ("true", "1", "yes")
TRANSLATOR_VERSION = "2.0"
PROMPT_VERSION = "2.0.0"


from audiobook_factory.key_manager import get_persistent_key_pool
from audiobook_factory.cadence import get_stealth_sdk_headers
from audiobook_factory.advisory_lexicon import get_advisory_db

pool = get_persistent_key_pool()


class GeminiPayloadError(RuntimeError):
    """Non-transient error indicating prompt payload issue (e.g. MAX_TOKENS or Safety Block)."""
    pass


def get_api_key() -> str:
    return pool.get_key(service="text")


def call_gemini(prompt: str, system_instruction: str = "", model: str = DEFAULT_MODEL, json_mode: bool = False, max_retries: int = 4) -> str:
    """Send request to Gemini API with automatic key rotation, retry and high-tier model fallback."""
    candidate_models = [model]
    for m in MODEL_CANDIDATES:
        if m not in candidate_models:
            candidate_models.append(m)

    last_error = None

    for curr_model in candidate_models:
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 8192,
            },
            "safetySettings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ],
        }

        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        if json_mode:
            payload["generationConfig"]["responseMimeType"] = "application/json"

        data = json.dumps(payload).encode("utf-8")

        for attempt in range(max_retries):
            api_key = get_api_key()
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{curr_model}:generateContent?key={api_key}"
            headers = get_stealth_sdk_headers(api_key)

            req = urllib.request.Request(
                url,
                data=data,
                headers=headers,
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=90.0) as resp:
                    res_data = json.loads(resp.read().decode("utf-8"))
                    candidates = res_data.get("candidates", [])
                    if not candidates:
                        prompt_fb = res_data.get("promptFeedback", {})
                        raise GeminiPayloadError(f"Gemini API returned no candidates (blocked): {prompt_fb}")
                    candidate = candidates[0]
                    if candidate.get("finishReason") == "MAX_TOKENS":
                        raise GeminiPayloadError("Gemini API output truncated: finishReason is MAX_TOKENS.")
                    parts = candidate.get("content", {}).get("parts", [])
                    if not parts or "text" not in parts[0]:
                        raise GeminiPayloadError(f"Candidate has no text parts (finishReason: {candidate.get('finishReason')})")
                    return parts[0]["text"]
            except GeminiPayloadError as gpe:
                # Deterministic payload problem: do NOT retry on identical payload
                last_error = str(gpe)
                print(f"    [FAIL-FAST] {gpe}. Breaking model retry immediately.", flush=True)
                raise gpe
            except urllib.error.HTTPError as e:
                err_msg = e.read().decode("utf-8", errors="ignore")
                last_error = f"HTTP {e.code}: {err_msg}"
                if e.code in (429, 503, 500):
                    pool.mark_temporary_backoff(api_key, 10.0, f"HTTP {e.code} in translator")
                if e.code == 503:
                    if attempt >= 1:
                        print(f"    [MODEL OVERLOAD] {curr_model} overloaded (503). Skipping to next candidate model immediately.", flush=True)
                        break
                if e.code in (503, 500, 429) and attempt < max_retries - 1:
                    wait_sec = 1.0 * (attempt + 1)
                    print(f"    [WAIT] Gemini API {curr_model} HTTP {e.code}. Key backed off, cooling off {wait_sec:.1f}s before next key/retry...", flush=True)
                    time.sleep(wait_sec)
                    continue
                break
            except Exception as e:
                last_error = str(e)
                if attempt < max_retries - 1:
                    wait_sec = 2.0 * (attempt + 1)
                    print(f"    [WAIT] Network hiccup ({e}). Retrying in {wait_sec:.1f}s (Attempt {attempt+1}/{max_retries})...", flush=True)
                    time.sleep(wait_sec)
                    continue
                break

    raise RuntimeError(f"Gemini API request failed on {candidate_models}: {last_error}")


def normalize_translated_lexicon(text: str, glossary: Dict[str, str] | Dict[str, Any]) -> str:
    """
    Meso-Tier Verification Guard:
    Enforces canonical Devanagari spellings via deterministic word-boundary regex substitutions.
    Accepts either a flat mapping {token: canonical_spelling} or a nested glossary dict.
    """
    if not text or not glossary:
        return text

    lexicon_map: Dict[str, str] = {}
    if isinstance(glossary, dict):
        if "characters" in glossary or "locations_and_terms" in glossary or "lexicon" in glossary:
            if "lexicon" in glossary and isinstance(glossary["lexicon"], dict):
                lexicon_map.update(glossary["lexicon"])
            if "locations_and_terms" in glossary and isinstance(glossary["locations_and_terms"], dict):
                lexicon_map.update(glossary["locations_and_terms"])
            if "characters" in glossary and isinstance(glossary["characters"], list):
                for char_entry in glossary["characters"]:
                    if isinstance(char_entry, dict):
                        eng = char_entry.get("english_name")
                        hi = char_entry.get("hindi_name")
                        if eng and hi:
                            lexicon_map[eng] = hi
        else:
            for k, v in glossary.items():
                if isinstance(k, str) and isinstance(v, str):
                    lexicon_map[k] = v

    if not lexicon_map:
        return text

    # Sort keys by length descending to prevent sub-string prefix collisions
    sorted_keys = sorted(lexicon_map.keys(), key=len, reverse=True)

    result = text
    for key in sorted_keys:
        canonical = lexicon_map[key]
        if not key or not canonical or key == canonical:
            continue
        # Use regex word boundaries supporting both ASCII and Unicode word chars
        pattern = rf"(?<![\w\u0900-\u097F]){re.escape(key)}(?![\w\u0900-\u097F])"
        result = re.sub(pattern, canonical, result, flags=re.UNICODE)

    return result


def generate_book_glossary(sample_chapter_text: str, book_metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Pass 1: Extract character names, Hindi spellings, honorific relationships, and terms."""
    system_prompt = (
        "You are an expert literary translation director and casting dramaturge for dark-fantasy audiobooks. "
        "Analyze this opening book passage and output a comprehensive JSON glossary for English-to-Hindi translation.\n"
        "Assign each major character a subtle Hindustani sociolect archetype to drive vocal variety without cartoonish caricature."
    )

    prompt = f"""Book Title: {book_metadata.get('title', 'Unknown')}
Author: {book_metadata.get('author', 'Unknown')}

Sample Chapter Text:
\"\"\"
{sample_chapter_text[:6000]}
\"\"\"

Produce a JSON object with:
1. "characters": List of objects with:
   - "english_name": string
   - "hindi_name": Devanagari spelling (e.g. "नायक")
   - "gender": "male" | "female" | "other"
   - "voice_style": brief description of speech tone (e.g. "gruff, calm, authoritative")
   - "recommended_pronoun_level": default how others address them ("aap", "tum", or "tu")
   - "hindustani_archetype": "COLD_CYNIC" | "CAUSTIC_ARISTOCRAT" | "THARKI_BARD" | "KHAANTI_GOON" | "MAKKAR_DALAL" | "GRUFF_SOLDIER" | "NEUTRAL"
   - "speech_quirks": brief takiya-kalam or cadence style (e.g. "dry laconic sarcasm with heavy grunts", "theatrical Lucknowi flattery", "foul-mouthed Purvanchal street threats")
2. "relationships": List of pairs describing who addresses whom as "aap", "tum", or "tu".
3. "locations_and_terms": Map of English terms to their consistent Hindi Devanagari or translated equivalent.
4. "general_tone": Description of narrative tone (e.g. "dark fantasy, dramatic, contemporary Hindustani").
"""

    response_text = call_gemini(prompt, system_instruction=system_prompt, json_mode=True)
    try:
        glossary = json.loads(response_text)
    except Exception:
        glossary = {
            "characters": [],
            "relationships": [],
            "locations_and_terms": {},
            "general_tone": "Cinematic Hindustani",
        }
    return glossary


def _translate_single_block(
    text_block: str,
    glossary: Dict[str, Any],
    block_title: str = "",
    preceding_context: str = "",
    model: str = DEFAULT_MODEL,
    adult_mode: Optional[bool] = None,
) -> str:
    if adult_mode is None:
        adult_mode = os.environ.get("ADULT_LITERARY_MODE", "true").lower() in ("true", "1", "yes")

    if adult_mode:
        advisory_guidance = get_advisory_db().get_formatted_prompt_guidelines()
        system_prompt = (
            "You are a master literary translator and audio drama director adapting mature, grimdark fantasy "
            "and adult literature (in the unapologetic tradition of Andrzej Sapkowski, George R.R. Martin, Anurag Kashyap, and Saadat Hasan Manto) "
            "into cinematic, spoken Hindustani (Hindi in Devanagari script).\n\n"
            "Strict Translation Invariants:\n"
            "1. LITERARY ANTI-BOWDLERIZATION MANDATE: NEVER sanitize, soften, or bowdlerize raw violence, visceral combat, "
            "dark tavern banter, gritty curses, or mature sensual/erotic intimacy. The source material is gritty adult literature, "
            "not a sanitized children's broadcast. Bowdlerization destroys dramatic truth.\n"
            "2. THE 70/30 ANTI-PARODY INVARIANT: Maintain a strict 70% Canon Sacredness / 30% Sensory Desi Amplification ratio. "
            "Never replace European dark-fantasy lore, proper nouns, monster classifications (demons, cursed beasts, mythical specters), or "
            "geographic names (ancient keeps, empires, border realms) with Indian mythology or tapori spoofs. "
            "Restrict Desi/Hindustani adaptation strictly to organic tavern grit, authentic rustic profanity, dynamic honorific power shifts, "
            "and Manto-grade somatic physical descriptions.\n"
            "3. PERIOD TAVERN GRIT & RAW PROFANITY: Translate medieval insults and curses into authentic, earthy Hindustani equivalents. "
            "Use 'गांड' (never 'चूतड़' or 'नितंब'), 'बकचोदी', 'सूअर का पेशाब', 'हरामी', 'कमीने', 'रंडी की औलाद', "
            "'अंडकोष बधिया करना'. NEVER replace them with polite TV-serial substitutions (do NOT turn 'bastard' into 'दुष्ट' or 'whore' into 'बुरी स्त्री').\n"
            "4. THE 19-TO-21 AMPLIFICATION RULE: When source English dialogue is mild or toned down (19), elevate it to authentic Desi 21 "
            "for visceral gut-punch impact (e.g. 'plough yourself' -> 'गांड मरा' / 'जा अपनी मां चुदा', 'damn you' -> 'तेरी मां की...').\n"
            "5. DESI MUHAVARE & IDIOMS: Transpose English idioms into organic UP/Bihar/Chambal street idioms rather than literal word-for-word "
            "(e.g. 'bite off more than you can chew' -> 'गांड में दम नहीं और चले आसमान चीरने', 'playing with fire' -> 'सांप के बिल में हाथ डालना').\n"
            "6. TU <-> MAAI-BAAP DYNAMIC POWER SHIFT: Honorific dynamics must reflect power shifts. Arrogant thugs start with dismissive "
            "'तू / अबे', but when physically intimidated, their speech collapses into groveling 'माई-बाप / सरकार / हुज़ूर'.\n"
            "7. URDU KA TARKA ('Aate me Namak'): Infuse a calibrated 10-15% of atmospheric, noir, and sensual Urdu "
            "('जिस्म', 'हवस', 'क़यामत', 'वहशी', 'रूह', 'सन्नाटा', 'ख़ंजर', 'ख़ौफ़', 'ज़ख़्म', 'दस्तक', 'सलाम', 'शराब', 'कमसिन') to give dark-fantasy existential weight.\n"
            "8. SOMATIC INTIMACY & PASSION (UNFILTERED HBO / MANTO STANDARD): "
            "Render passionate, sensual, intimate, or erotic scenes with visceral realism and authentic passion:\n"
            "- STRICTLY BANNED: Sterile, clinical biology-textbook words ('योनि', 'लिंग') that sound like high-school exams or hospital autopsies.\n"
            "- MANDATED & AUTHORIZED: Visceral romantic and sensual friction ('मसलना', 'तपती कमर', 'भीगी प्यास', 'बेकाबू सांसें', 'कांपती उंगलियां', 'होंठों की तपिश', 'चमड़े की तंग पेटी खोलना', 'सीने पर नाखूनों का धंसना') "
            "whenever the scene presents passionate encounters, bedroom dialogue, or sexual intimacy.\n"
            "- THE 'NOTHING ABOVE SOURCE' INVARIANT: Strictly respect narrative truth. Never invent penetrative intercourse out of thin air if characters "
            "are merely conversing or brushing shoulders. But whenever the source novel contains sexual tension, nudity, physical passion, or intimacy, "
            "elevate it with the 19-to-21 Amplification Rule into full, unapologetic Desi passion without prudish TV-serial censorship.\n"
            "9. VISCERAL COMBAT, GORE & STACCATO RHYTHM: Depict blade strikes, bone fractures, blood spray, and wounds with visceral realism "
            "('लोहा हंसली की हड्डी चीरता हुआ सीने में धंस गया', 'गले से खून का फव्वारा फूटा', 'दांतों के टूटने और तालू के फटने की खट्टी नमकीन बदबू'). "
            "During intense fight scenes, fracture narrative into rapid STACCATO clauses (2-4 words per beat: 'कदम पीछे। तलवार का पैंतरा। वार। चूक गया!'). "
            "Capture adrenaline tunnel vision, muscle strain, and raw battlefield profanity.\n"
            "10. SENSE-FOR-SENSE SPOKEN DIALOGUE: Never do literal word-for-word translation. Translate sense-for-sense, preserving drama, "
            "subtext, humor, and emotional depth for professional voice actors. Use flowing, cinematic Hindustani.\n"
            "11. ADHERE TO GLOSSARY & ZERO CHATTER: Strictly adhere to the provided Character Glossary for proper noun spellings. "
            "Output ONLY the translated passage in Devanagari Markdown without any meta-commentary, notes, disclaimers, or conversational introductions.\n\n"
            f"{advisory_guidance}"
        )
    else:
        system_prompt = (
            "You are a master literary translator and audio drama director adapting classic literature "
            "into cinematic, spoken Hindustani (Hindi in Devanagari script).\n\n"
            "Strict Translation Invariants:\n"
            "1. SENSE-FOR-SENSE SPOKEN DIALOGUE: Translate sense-for-sense, preserving drama, subtext, humor, "
            "and emotional depth for professional voice actors. Use flowing, natural Hindustani.\n"
            "2. ADHERE TO GLOSSARY & PRONOUNS: Strictly adhere to the provided Character Glossary for proper noun spellings "
            "and honorific dynamics ('Aap' vs 'Tum' vs 'Tu').\n"
            "3. PRESERVE FORMATTING & ZERO CHATTER: Keep headings and dialogue quotation marks intact. Output ONLY the translated "
            "passage in Devanagari Markdown without any meta-commentary, notes, disclaimers, or conversational introductions."
        )

    glossary_str = json.dumps(glossary, ensure_ascii=False, indent=2)

    prompt = f"""### PERSISTENT TRANSLATION GLOSSARY:
{glossary_str}

### PRECEDING STORY CONTEXT:
{preceding_context if preceding_context else "Beginning of novel."}

### ENGLISH TEXT TO TRANSLATE ({block_title}):
\"\"\"
{text_block}
\"\"\"
"""
    raw = call_gemini(prompt, system_instruction=system_prompt, model=model, json_mode=False).strip()
    from audiobook_factory.sanitizer import validate_and_sanitize_translation, audit_literary_register
    is_valid, cleaned, reason = validate_and_sanitize_translation(raw, is_hindi=True)
    if not is_valid:
        raise RuntimeError(f"Translation guardrail triggered for {block_title}: {reason}")
    _, cleaned, warnings = audit_literary_register(cleaned)
    if warnings:
        from audiobook_factory.logger import logger
        for w in warnings:
            logger.info(f"    [LITERARY LINTER] {w}")
    return cleaned


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
    except Exception:
        return ""


def _commit_chapter_memory_in_translator(
    project_dir: Path,
    source_text: str,
    block_label: str,
    glossary: Optional[Dict[str, Any]] = None,
    model: str = DEFAULT_MODEL,
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
    except Exception:
        pass


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
    model: str = DEFAULT_MODEL,
    project_dir: Optional[Path] = None,
) -> str:
    """Pass 2: Sense-for-sense literary translation of a single chapter into spoken Hindustani."""
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
    # Chapters under 2,200 words fit comfortably within the 8,192 token limit
    if len(words) <= 2200:
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

    # For long chapters, split across paragraph boundaries to avoid hitting MAX_TOKENS
    paragraphs = chapter_text.split("\n\n")
    chunks: List[str] = []
    curr_chunk: List[str] = []
    curr_words = 0

    for p in paragraphs:
        p_words = len(p.split())
        if curr_words + p_words > 1800 and curr_chunk:
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
            except Exception:
                pass

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
    model: str = DEFAULT_MODEL,
    use_intelligent_pipeline: bool = True,
    force_gate: bool = False,
) -> Path:
    """
    Batch translates all extracted chapters in a project into Hindi.
    Defaults to IntelligentTranslationPipeline (Pillar 2 Intelligence) with
    automatic fail-safe gate certification and full artifact persistence.
    """
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
        first_chap_file = extracted_dir / "chapter_001.md"
        if not first_chap_file.exists():
            chap_files = sorted(extracted_dir.glob("*.md"))
            if not chap_files:
                raise FileNotFoundError("No chapter markdown files found in extracted directory.")
            first_chap_file = chap_files[0]

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

            print(f"[*] [{idx}/{total}] Processing Intelligent Translation for {chap_file.name}...", flush=True)
            pipeline.translate_chapter(
                chapter_text=content,
                chapter_num=idx,
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
    model: str = DEFAULT_MODEL,
    use_cache: bool = True,
) -> Tuple[str, List[Any]]:
    """
    Executes Pillar 2 Literary Translation Intelligence Pipeline on a chapter.
    Integrates Book Bible, Entity Discovery, Transition-Driven Scene Planning,
    Dedicated Evaluators (Gates T0-T11), and Tiered Self-Healing Repair.
    """
    from audiobook_factory.translation import IntelligentTranslationPipeline
    pipeline = IntelligentTranslationPipeline(project_dir=project_dir, model=model)
    return pipeline.translate_chapter(
        chapter_text=chapter_text,
        chapter_num=chapter_num,
        chapter_title=chapter_title,
        call_llm_fn=call_gemini,
        use_cache=use_cache,
    )

