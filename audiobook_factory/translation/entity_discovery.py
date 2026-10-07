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
                    category="location" if any(w in name.lower() for w in ("mountain", "valley", "city", "river")) else "character",
                    frequency=count,
                    confidence=conf,
                ))

        # Refine candidate classification and Devanagari transliteration using LLM
        import os
        is_mock_offline = os.environ.get("MOCK_OFFLINE", "").lower() in ("true", "1")
        if candidates and not is_mock_offline:
            try:
                candidate_names = [c.name for c in candidates]
                prompt = (
                    f"Book Chapter Context (excerpt):\n\"\"\"\n{text[:4000]}\n\"\"\"\n\n"
                    f"Candidate Entities to Classify and Transliterate into Devanagari Hindi:\n"
                    f"{json.dumps(candidate_names, ensure_ascii=False)}\n\n"
                    "For each candidate entity, output a JSON array of objects:\n"
                    "- \"name\": string (exact match to input candidate)\n"
                    "- \"category\": 'character' | 'location' | 'faction' | 'creature' | 'artifact'\n"
                    "- \"suggested_devanagari\": string (phonetically accurate Hindi Devanagari spelling)\n"
                    "- \"confidence\": float (0.5 to 1.0)\n"
                )
                sys_prompt = (
                    "You are a Master Literary Lexicographer and Translation Director. "
                    "Classify discovered entities into accurate categories (character, location, faction, creature, artifact) "
                    "and provide standard phonetically faithful Devanagari Hindi transliterations."
                )

                if call_llm_fn:
                    llm_results = call_llm_fn(prompt, sys_prompt)
                else:
                    from audiobook_factory.llm_client import call_gemini
                    from audiobook_factory.model_manager import TaskType
                    llm_results = call_gemini(
                        prompt=prompt,
                        system_instruction=sys_prompt,
                        task_type=TaskType.TRANSLATION,
                        response_mime_type="application/json",
                        temperature=0.1,
                        max_retries=3,
                    )

                if isinstance(llm_results, list):
                    res_map = {item.get("name"): item for item in llm_results if isinstance(item, dict) and "name" in item}
                    for cand in candidates:
                        if cand.name in res_map:
                            entry = res_map[cand.name]
                            if entry.get("category"):
                                cand.category = entry["category"]
                            if entry.get("suggested_devanagari"):
                                cand.suggested_devanagari = entry["suggested_devanagari"]
                            if entry.get("confidence") is not None:
                                cand.confidence = float(entry["confidence"])
            except Exception as e:
                from audiobook_factory.logger import logger
                logger.warning(f"  [!] Entity discovery LLM refinement notice: {e}")

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


class ChapterEntityHarvester:
    """
    Room 1.5: Per-Chapter Autonomous Entity, Moniker & Alias Harvester.
    Runs before translating or scripting ANY chapter.
    Enforces Tri-Partite Taxonomy:
      1. PROPER_NAME: Phonetically transliterate to Devanagari (Edward -> एडवर्ड, Corwin -> कॉरविन, Elena -> एलेना, Valerius -> वालेरियस).
      2. HERALDIC_MONIKER: Heraldic nicknames/titles that act as personal names (Silver Falcon -> सिल्वर फाल्कन, Night Raven -> नाइट रेवेन).
         STRICT BAN: Never literally translate heraldic monikers to Hindi (e.g. BANNED: 'चांदी का बाज़', 'रात का कौवा' as names).
      3. OCCUPATIONAL_ROLE / EPITHET: Spoken descriptive roles (The Stranger -> अजनबी, The Butcher -> कसाई).
      4. ALIAS UNIFICATION: Unify aliases referring to the same person (e.g. Lord Corwin == Silver Falcon == The Stranger)
         so voice casting and screenplay attribution never split actor personas.
    """

    @classmethod
    def harvest_and_sync(
        cls,
        chapter_text: str,
        project_dir: Optional[Any] = None,
        chapter_num: int = 1,
        global_glossary: Optional[Dict[str, Any]] = None,
        call_llm_fn: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Discovers entities and heraldic monikers in chapter text, resolves aliases,
        and synchronizes with BookBible, glossary.json, and character_roster.json.
        """
        from pathlib import Path
        from audiobook_factory.logger import logger
        from audiobook_factory.translation.book_bible import BookBible, BookEntity

        p_dir = Path(project_dir) if project_dir else None
        bible: Optional[BookBible] = None
        if p_dir:
            try:
                bible = BookBible.load_from_project(p_dir)
            except Exception as e:
                logger.warning(f"  [!] ChapterEntityHarvester BookBible load notice: {e}")

        if bible is None:
            bible = BookBible()
            if global_glossary:
                bible.import_from_legacy_glossary(global_glossary)

        # Skip LLM if offline or text is empty
        import os
        is_mock_offline = os.environ.get("MOCK_OFFLINE", "").lower() in ("true", "1")
        if not chapter_text.strip() or is_mock_offline:
            return bible.export_legacy_glossary()

        # Prepare excerpt: first 8000 chars + middle 4000 chars if long
        sample_excerpt = chapter_text[:8000]
        if len(chapter_text) > 12000:
            mid_start = len(chapter_text) // 2
            sample_excerpt += "\n\n[...]\n\n" + chapter_text[mid_start : mid_start + 4000]

        sys_prompt = (
            "You are an Expert Literary Lexicographer, Voice Casting Director, and Translation Dramaturge for prestige audiobooks.\n"
            "Analyze this chapter passage and extract all characters, heraldic monikers, roles, factions, locations, and lore terms.\n\n"
            "CRITICAL TRI-PARTITE ENTITY TAXONOMY:\n"
            "1. PROPER_NAME (Personal Names, Surnames, Given Names):\n"
            "   - Phonetically transliterate into clean Devanagari Hindi (e.g. 'Edward' -> 'एडवर्ड', 'Corwin' -> 'कॉरविन', 'Elena' -> 'एलेना', 'Valerius' -> 'वालेरियस').\n"
            "   - NEVER substitute foreign fantasy names with Indian village names.\n"
            "2. HERALDIC_MONIKER / COGNOMEN (Heraldic Nicknames, Formal Titles, Epithets used as Names):\n"
            "   - Treat heraldic monikers as PROPER NAMES! Phonetically transliterate into Devanagari.\n"
            "   - GOLD STANDARD: 'Silver Falcon' -> 'सिल्वर फाल्कन', 'Night Raven' -> 'नाइट रेवेन', 'Gold-Tooth' -> 'गोल्ड-टूथ'.\n"
            "   - STRICTLY FORBIDDEN: NEVER translate heraldic personal monikers literally word-for-word into Hindi (STRICTLY BANNED: 'चांदी का बाज़', 'रात का कौवा' as character names)!\n"
            "3. OCCUPATIONAL_ROLE / DESCRIPTIVE EPITHET (Generic situational roles or initial descriptors):\n"
            "   - Translate into natural spoken Hindustani (e.g. 'The Stranger' -> 'अजनबी', 'The Butcher' -> 'कसाई', 'The Alderman' -> 'एल्डरमैन', 'The Innkeeper' -> 'सरायवाला', 'The Scarred Sailor' -> 'दाग़ी नाविक').\n"
            "4. ALIAS UNIFICATION & LINKING (CRITICAL FOR AUDIO DRAMA CASTING):\n"
            "   - If a character is introduced by a descriptive role or moniker before revealing their true name (e.g. 'The Stranger' is revealed to be 'Lord Corwin' / 'Silver Falcon', or 'The Scarred Sailor' is 'Captain Drake'), "
            "explicitly group them under the SAME canonical character record with aliases!\n"
            "   - This prevents the screenplay engine from splitting one character across multiple voice actors."
        )

        existing_chars = list(bible.characters.keys())
        prompt = f"""Known Book Characters so far: {json.dumps(existing_chars, ensure_ascii=False)}

Chapter {chapter_num} Passage:
\"\"\"
{sample_excerpt}
\"\"\"

Output JSON: An object with:
1. "characters": List of character objects discovered in this chapter:
   - "english_name": string (canonical name, e.g. "Corwin", "Drake", "Elena")
   - "hindi_name": Devanagari transliteration or translation (e.g. "कॉरविन", "ड्रेक", "एलेना")
   - "entity_type": "PROPER_NAME" | "HERALDIC_MONIKER" | "OCCUPATIONAL_ROLE"
   - "aliases": List of strings (all alternative names, nicknames, and descriptive roles in this chapter, e.g. ["Silver Falcon", "सिल्वर फाल्कन", "The Stranger", "अजनबी"])
   - "gender": "male" | "female" | "other"
   - "voice_style": brief description of vocal tone
   - "hindustani_archetype": sociolect archetype
2. "locations_and_terms": Map of English terms/locations/monikers to Devanagari (e.g. {{"Valyria": "वलेरिया", "Silver Falcon": "सिल्वर फाल्कन"}})
"""
        try:
            if call_llm_fn:
                raw = call_llm_fn(prompt=prompt, system_instruction=sys_prompt, json_mode=True)
            else:
                from audiobook_factory.llm_client import call_gemini
                from audiobook_factory.model_manager import TaskType
                raw = call_gemini(
                    prompt=prompt,
                    system_instruction=sys_prompt,
                    task_type=TaskType.TRANSLATION,
                    response_mime_type="application/json",
                    temperature=0.1,
                    max_retries=3,
                )

            res = raw if isinstance(raw, dict) else (json.loads(raw) if isinstance(raw, str) and raw.strip() else {})
            chars_data = res.get("characters", []) if isinstance(res, dict) else []
            terms_data = res.get("locations_and_terms", {}) if isinstance(res, dict) else {}

            # Process discovered characters
            for c in chars_data:
                if not isinstance(c, dict) or not c.get("english_name"):
                    continue
                eng_name = c["english_name"].strip()
                hin_name = c.get("hindi_name", "").strip() or eng_name
                aliases = [a.strip() for a in c.get("aliases", []) if isinstance(a, str) and a.strip()]

                # Check if matches existing character
                matched_key = None
                for ex_name, ex_ent in bible.characters.items():
                    if ex_name.lower() == eng_name.lower() or eng_name.lower() in [a.lower() for a in ex_ent.aliases]:
                        matched_key = ex_name
                        break
                    for alias in aliases:
                        if alias.lower() == ex_name.lower() or alias.lower() in [a.lower() for a in ex_ent.aliases]:
                            matched_key = ex_name
                            break

                if matched_key:
                    # Update aliases
                    target_ent = bible.characters[matched_key]
                    current_aliases = set(target_ent.aliases)
                    for a in aliases:
                        current_aliases.add(a)
                    if eng_name != matched_key:
                        current_aliases.add(eng_name)
                    if hin_name and hin_name != target_ent.hindi_name:
                        current_aliases.add(hin_name)
                    target_ent.aliases = sorted(list(current_aliases))
                else:
                    new_ent = BookEntity(
                        canonical_id=eng_name.lower().replace(" ", "_"),
                        english_name=eng_name,
                        hindi_name=hin_name,
                        aliases=aliases,
                        category="character",
                        gender=c.get("gender", "male"),
                        description=c.get("voice_style", ""),
                        first_appearance_chapter=chapter_num,
                        sociolect_archetype=c.get("hindustani_archetype", "NEUTRAL"),
                        is_canonical=True,
                        confidence=0.95,
                    )
                    bible.characters[eng_name] = new_ent

            # Process locations and terms
            if isinstance(terms_data, dict):
                for eng_term, hi_term in terms_data.items():
                    if isinstance(eng_term, str) and isinstance(hi_term, str) and eng_term.strip():
                        t_clean = eng_term.strip()
                        h_clean = hi_term.strip()
                        if any(w in t_clean.lower() for w in ("mountain", "valley", "city", "river", "kingdom", "inn", "tavern", "zerrikania")):
                            bible.locations[t_clean] = h_clean
                        else:
                            bible.terminology[t_clean] = h_clean

            # Save updated Bible and export glossary
            if p_dir:
                bible.save(p_dir)
                # Also update character_roster.json if present
                roster_file = p_dir / "character_roster.json"
                roster_data = {"characters": {}}
                if roster_file.exists():
                    try:
                        with open(roster_file, "r", encoding="utf-8") as rf:
                            roster_data = json.load(rf)
                    except Exception:
                        pass
                if "characters" not in roster_data:
                    roster_data["characters"] = {}
                for c_name, c_ent in bible.characters.items():
                    h_name = c_ent.hindi_name or c_name
                    roster_data["characters"][h_name] = {
                        "english_name": c_name,
                        "gender": c_ent.gender or "male",
                        "aliases": list(set(c_ent.aliases + [c_name, h_name])),
                    }
                    if c_name not in roster_data["characters"]:
                        roster_data["characters"][c_name] = roster_data["characters"][h_name]
                try:
                    with open(roster_file, "w", encoding="utf-8") as rf:
                        json.dump(roster_data, rf, ensure_ascii=False, indent=2)
                except Exception as e:
                    logger.warning(f"  [!] Failed to update character_roster.json: {e}")

            logger.info(f"  [+] ChapterEntityHarvester synced {len(chars_data)} characters for Chapter {chapter_num}")
        except Exception as e:
            logger.warning(f"  [!] ChapterEntityHarvester extraction notice: {e}")

        return bible.export_legacy_glossary()
