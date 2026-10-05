#!/usr/bin/env python3
"""
Audiobook Factory - Sonic Intelligence Coordination Bridge.
Connects creative LLM sound design intent to the 61,000+ asset SQLite FTS5 Sound Bank.
Implements:
1. Dynamic Taxonomy Grounding (injects real catalog vocabulary into LLM prompts).
2. Bilingual Intent Normalization (Devanagari/Hindi -> English UCS tags).
3. Tiered FTS5 Query Relaxation (prevents premature fallback to silence).
4. Category Safety Guards (blocks fantasy combat assets in modern/domestic scenes).
5. Hit-Rate Diagnostics & Telemetry Auditing.
"""

from __future__ import annotations
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Set

from audiobook_factory.logger import logger
from audiobook_factory.sound_bank import SoundBank, get_sound_bank


# Bilingual Devanagari to English UCS and Physical Sound Token Map
BILINGUAL_SOUND_TAXONOMY = {
    # Vehicles & Transit
    "कार": "car motor vehicle engine door",
    "गाड़ी": "car vehicle engine motor",
    "मोटर": "motor engine vehicle",
    "इंजन": "engine motor hum idle",
    "हॉर्न": "horn beep car honk",
    "पहिया": "wheel tire roll gravel",
    "सड़क": "road pavement street asphalt",
    "साइकिल": "bicycle bell pedal chain",
    "रेल": "train rail track steam whistle",
    
    # Domestic & Architecture
    "दरवाजा": "door wood creak slam knob latch handle",
    "खिड़की": "window glass wood open latch shutter",
    "किवाड़": "door wood creak latch",
    "चूं": "creak squeak friction hinge",
    "धड़ाम": "slam bang heavy wooden thud impact",
    "कपाट": "door gate wooden entrance",
    "घंटी": "bell chime ring doorbell",
    "चाबी": "key metal rattle lock unlock",
    "ताला": "lock metal padlock latch click",
    "दीवार": "wall brick stone surface",
    "फर्श": "floor wood footsteps concrete",
    
    # Tableware & Liquids
    "चाय": "tea cup ceramic tableware liquid pour clink",
    "कॉफी": "coffee cup saucer liquid spoon stir",
    "प्याला": "cup ceramic porcelain mug clink dish",
    "गिलास": "glass tableware clink liquid water",
    "थाली": "plate metal ceramic dish tableware",
    "बर्तन": "dishes tableware kitchen metal ceramic",
    "चम्मच": "spoon metal stir clink cutlery",
    "पानी": "water pour splash drip liquid stream",
    "उड़ेला": "pour liquid stream fill bottle glass",
    "सुराही": "pitcher jug liquid pour ceramic",
    
    # Human Physical Acts & Paper
    "कदम": "footsteps walk shoe leather gravel pavement pavement",
    "पैर": "footsteps walk stride shuffle tread",
    "जूता": "footsteps boot shoe leather walk",
    "कागज": "paper rustle page turn sheet parchment",
    "पन्ना": "page turn paper rustle leaf document",
    "किताब": "book paper open cover close rustle",
    "खत": "letter envelope paper unfold rustle",
    "कलम": "pen paper write sketch scribble",
    "कपड़े": "cloth fabric rustle movement jacket cloak",
    "कोट": "coat jacket cloth fabric movement",
    
    # Nature & Weather
    "हवा": "wind breeze draft air rustle trees",
    "बारिश": "rain rainstorm droplets precipitation water",
    "बूंद": "raindrop water drip drop puddle",
    "बादल": "thunder rumble weather cloud dark",
    "बिजली": "thunder lightning rumble crack strike",
    "पत्ता": "leaves foliage rustle tree branch",
    "पेड़": "tree wind branch creak leaves forest",
    "बिल्ली": "cat meow purr feline kitten",
    "कुत्ता": "dog bark pant whimper canine",
    "चिड़िया": "birds chirp song outdoor nature forest",
    "उल्लू": "owl hoot nocturnal night bird",

    # Mechanical, Physical Cues & Silence
    "क्लिक": "click switch button latch lighter mechanical",
    "खट": "click tap knock wood wooden surface",
    "टक": "tick tap click clock watch pendulum",
    "सरसराहट": "rustle whisper cloth fabric paper leaves",
    "फुसफुसाहट": "whisper crowd walla murmur quiet",
    "सन्नाटा": "silence room tone quiet ambient calm",
    "कूद": "jump land leap footstep thud",
    "हंसी": "laugh chuckle giggle amused reaction",
    "रोना": "cry weep sob tears snivel",
    
    # Dramatic & Combat (strictly guarded)
    "तलवार": "sword blade metal unsheathe draw clash strike",
    "खंजर": "dagger blade knife unsheathe metal",
    "तीर": "arrow bow whoosh release flight",
    "कमान": "bow release string tension twang",
    "वार": "strike blow combat impact hit",
    "आग": "fire campfire torch crackle blaze flame",
    "मशाल": "torch fire wood flame crackle",
    "धमाका": "explosion blast boom thunder heavy impact",

    # Vernacular, Period & Rural Objects
    "हुक्का": "water pipe bubbling hookah smoke",
    "ताँगा": "horse carriage trot cobblestones wooden wheel",
    "घोड़ा": "horse trot gallop neigh whinny hooves",
    "बाँसुरी": "flute bamboo woodwind melody gentle",
    "शहनाई": "shehnai reed woodwind high melody",
    "घूँघरू": "bells anklet chime jingle metallic",
    "नाव": "boat wooden oars row water splash paddle",
    "कश्ती": "boat wood rowing splash water lake",
    "कुल्हाड़ी": "axe chop wood log strike thud impact",
    "लाठी": "stick staff wood thud blunt strike impact",
    "चरपाई": "creak rope wooden bed shift rope friction",
    "तोप": "cannon boom explosion heavy blast",
}

# Stop words and filler poetic adjectives that break strict FTS5 search
STOP_WORDS_FTS = {
    "a", "an", "the", "and", "or", "of", "in", "on", "at", "to", "for", "with", "by",
    "from", "into", "onto", "under", "over", "very", "somber", "subtle", "deep",
    "extremely", "gentle", "rich", "resonant", "reverberant", "distant", "pure",
    "haunting", "beautiful", "intense", "soft", "loud", "atmospheric", "cinematic",
    "sound", "sfx", "audio", "effect", "cue", "bed", "track"
}

# Combat terms to prohibit when the scene is non-combat
COMBAT_TERMS = {
    "sword", "blade", "scabbard", "parry", "axe", "dagger", "drawbridge", "armor",
    "clash", "spear", "shield", "mace", "crossbow", "warrior", "combat", "blood",
    "slashing", "monster", "beast", "battle"
}


class SonicIntelligenceBridge:
    """Coordinates LLM sound design intent with the physical SQLite FTS5 Sound Bank."""

    def __init__(self, sound_bank: Optional[SoundBank] = None):
        self.sound_bank = sound_bank or get_sound_bank()

    def ground_prompt_with_catalog_taxonomy(self) -> Dict[str, Any]:
        """
        Returns a compact taxonomy snippet to inject into LLM directing prompts.
        Informs the LLM of real, existing catalog UCS tags and environment IDs.
        """
        return {
            "environments": [
                "domestic_room", "rural_courtyard_open", "suburban_street_day",
                "suburban_street_night", "office_commercial", "quiet_chamber",
                "wooden_cottage_interior", "dense_forest_night", "open_road"
            ],
            "foley_verbs": [
                "door_creak", "door_slam", "door_open", "door_close",
                "footsteps_pavement", "footsteps_wood", "footsteps_gravel",
                "cup_clink", "tableware_stir", "plate_slide", "liquid_pour",
                "paper_rustle", "page_turn", "chair_scrape", "clock_tick",
                "car_door", "car_engine", "car_passby", "cat_purr", "cat_meow"
            ],
            "music_archetypes": [
                "MYSTERY_PROLOGUE", "INVESTIGATION_TENSION", "NOCTURNAL_VIGIL",
                "DRAMATIC_CONFRONTATION", "BITTERSWEET_PARTING", "CONTEMPLATIVE_SOLITUDE",
                "URGENT_PURSUIT", "WARM_DOMESTICITY"
            ],
            "musical_timbre_tags": [
                "solo cello", "subtle strings", "woodwinds", "soft piano",
                "atmospheric drone", "low brass swell", "bansuri / flute", "acoustic guitar"
            ]
        }

    def normalize_and_expand_query(self, raw_query: str, category: str = "sfx") -> List[str]:
        """
        Transforms raw LLM queries or Hindi phrases into a ranked list of FTS5 search candidates:
        Tier 1: Exact cleaned phrase.
        Tier 2: Bilingual mapped terms.
        Tier 3: Stop-word stripped core keywords.
        Tier 4: OR-disjunctive broad query.
        """
        if not raw_query or not isinstance(raw_query, str):
            return ["orchestral"] if category == "music" else ["rustle"]

        raw_lower = raw_query.lower().strip()
        candidates: List[str] = []

        # 1. Check for bilingual Hindi mappings
        bilingual_tokens: List[str] = []
        for hindi_word, eng_tokens in BILINGUAL_SOUND_TAXONOMY.items():
            if hindi_word in raw_lower:
                bilingual_tokens.extend(eng_tokens.split())

        # 2. Clean punctuation
        cleaned = re.sub(r"['\":*()^~_/-]", " ", raw_lower)
        raw_tokens = [w for w in cleaned.split() if len(w) > 1]

        # 3. Filter stop words
        core_tokens = [w for w in raw_tokens if w not in STOP_WORDS_FTS]

        # Combine core tokens with any bilingual tokens found
        all_tokens = list(dict.fromkeys(core_tokens + bilingual_tokens))

        if not all_tokens:
            all_tokens = raw_tokens[:3] or ["ambient"]

        # Candidate 1: Primary conjunction (top 2-3 most specific tokens)
        primary = " ".join(all_tokens[:3])
        if primary:
            candidates.append(primary)

        # Candidate 2: High-specificity pair
        if len(all_tokens) >= 2:
            candidates.append(f"{all_tokens[0]} {all_tokens[1]}")

        # Candidate 3: Broad OR disjunction
        if len(all_tokens) >= 2:
            disjunction = " OR ".join(all_tokens[:4])
            candidates.append(disjunction)

        # Candidate 4: Single most salient token
        if all_tokens:
            candidates.append(all_tokens[0])

        return list(dict.fromkeys(candidates))

    def resolve_asset_with_fallback(
        self,
        query: str,
        category: str = "sfx",
        is_combat_scene: bool = False,
        limit: int = 3,
    ) -> Tuple[Optional[Path], str, float]:
        """
        Executes tiered search against SQLite FTS5 with category safety guards.
        Returns: (resolved_path, resolution_tier, match_score)
        """
        candidate_queries = self.normalize_and_expand_query(query, category=category)
        
        # Guard list against non-combat scenes
        banned_stems = COMBAT_TERMS if not is_combat_scene else set()

        # Tier 1 & 2: Direct FTS5 candidate checks
        for tier_idx, c_query in enumerate(candidate_queries, 1):
            try:
                if category == "music":
                    results = self.sound_bank.search_music_catalog(c_query, limit=limit)
                    if not results:
                        results = self.sound_bank.search(c_query, category="music", limit=limit)
                else:
                    results = self.sound_bank.search(c_query, category=category, limit=limit)

                if results:
                    for item in results:
                        fpath_str = item.get("filepath") or item.get("filename")
                        if not fpath_str:
                            continue
                        fpath = Path(fpath_str)
                        if not fpath.is_absolute():
                            fpath = self.sound_bank.bank_root / fpath

                        # Check combat safety
                        fpath_name_lower = fpath.name.lower()
                        if any(b in fpath_name_lower for b in banned_stems):
                            continue

                        if fpath.exists():
                            tier_name = "exact_fts" if tier_idx == 1 else "relaxed_fts"
                            score = 1.0 if tier_idx == 1 else 0.85
                            return fpath, tier_name, score

                        # Virtual asset available for Stage 4.5 download-on-demand
                        if item.get("source_url") or not item.get("is_downloaded", 1):
                            cat_folder = (item.get("category") or category or "SFX").upper()
                            fname = item.get("filename") or Path(fpath_str).name
                            expected_path = self.sound_bank.cache_dir / cat_folder / Path(fname).name
                            tier_name = "exact_fts_virtual" if tier_idx == 1 else "relaxed_fts_virtual"
                            score = 0.95 if tier_idx == 1 else 0.80
                            return expected_path, tier_name, score
            except Exception as e:
                logger.debug(f"FTS5 candidate search error on '{c_query}': {e}")

        # Tier 3: Hybrid Sonic Intelligence Engine search
        try:
            result = self.sound_bank.search_intelligence(intent=query, limit=limit)
            if result and hasattr(result, "ranked_cards") and result.ranked_cards:
                for card in result.ranked_cards:
                    if card and getattr(card, "file_path", None):
                        cand = Path(card.file_path)
                        if not cand.is_absolute():
                            cand = self.sound_bank.bank_root / cand
                        cand_name_lower = cand.name.lower()
                        if any(b in cand_name_lower for b in banned_stems):
                            continue
                        if cand.exists():
                            return cand, "vector_intelligence", 0.75
                        # Virtual candidate in vector intelligence
                        cat_folder = (category or "SFX").upper()
                        expected_path = self.sound_bank.cache_dir / cat_folder / cand.name
                        return expected_path, "vector_intelligence_virtual", 0.70
        except Exception as e:
            logger.debug(f"Sonic intelligence search error: {e}")

        # Tier 4: Graceful acoustic silence (0 hardcoded tracks)
        return None, "graceful_silence", 0.0

    def audit_catalog_hit_rate(
        self,
        queries: List[Dict[str, Any]],
        category: str = "sfx",
        is_combat_scene: bool = False,
    ) -> Dict[str, Any]:
        """
        Audits a list of LLM-generated sound queries against the active Sound Bank.
        Measures exact hit rate, relaxed hit rate, and fallback frequency.
        """
        total = len(queries)
        if total == 0:
            return {
                "total_queries": 0,
                "hit_rate_pct": 100.0,
                "exact_hits": 0,
                "relaxed_hits": 0,
                "silence_fallbacks": 0,
                "status": "PASS",
            }

        exact_hits = 0
        relaxed_hits = 0
        silence_fallbacks = 0
        details = []

        for q_item in queries:
            raw_q = q_item.get("query") or q_item.get("search_query") or q_item.get("tag", "")
            cat = q_item.get("category", category)
            path, tier, score = self.resolve_asset_with_fallback(
                query=raw_q,
                category=cat,
                is_combat_scene=is_combat_scene,
            )
            if tier in ("exact_fts", "exact_fts_virtual"):
                exact_hits += 1
            elif tier in ("relaxed_fts", "relaxed_fts_virtual", "vector_intelligence", "vector_intelligence_virtual"):
                relaxed_hits += 1
            else:
                silence_fallbacks += 1

            details.append({
                "raw_query": raw_q,
                "category": cat,
                "resolved_tier": tier,
                "resolved_asset": path.name if path else None,
                "score": score,
            })

        resolved_count = exact_hits + relaxed_hits
        hit_rate = (resolved_count / total) * 100.0

        return {
            "total_queries": total,
            "resolved_count": resolved_count,
            "hit_rate_pct": round(hit_rate, 2),
            "exact_hits": exact_hits,
            "relaxed_hits": relaxed_hits,
            "silence_fallbacks": silence_fallbacks,
            "status": "PASS" if hit_rate >= 75.0 else "WARN" if hit_rate >= 50.0 else "FAIL",
            "details": details,
        }
