#!/usr/bin/env python3
"""
Audiobook Factory - Dynamic Literary Advisory Lexicon & Tone Guidance DB.
Maintains a SQLite database of cultural transposition advice, emotional registers,
and anti-robotic linguistic rules to guide translation without brittle hardcoded token replacements.
"""

import os
import json
import sqlite3
import contextlib
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "audiobooks" / "literary_advisory.db"


class LiteraryAdvisoryDB:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextlib.contextmanager
    def _connection(self):
        conn = sqlite3.connect(str(self.db_path), timeout=20.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=5000;")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_db(self):
        with self._connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS literary_advisory_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,               -- appearance, youth_sensual, salutations, beverages, profanity, combat
                    source_concept TEXT NOT NULL,         -- conceptual English phrase/trope
                    guidance_rule TEXT NOT NULL,          -- emotional/stylistic direction explaining WHY and HOW
                    recommended_vocabulary TEXT NOT NULL, -- JSON array of evocative terms/idioms
                    banned_antipatterns TEXT NOT NULL,    -- JSON array of robotic/literal/immersion-breaking terms
                    context_scope TEXT DEFAULT 'global',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()

        # Seed defaults if empty
        self.seed_default_guidelines()

    def seed_default_guidelines(self):
        """Populates the database with universal dark-fantasy Hindustani literary guidelines."""
        with self._connection() as conn:

            default_rules = [
                (
                    "appearance",
                    "blonde hair / fair complexion",
                    "Never translate 'blonde girl' literally as 'सुनहरी लड़की' (which sounds metallic or robotic). Transpose to organic Desi physical imagery such as 'गोरी-चिट्टी / गोरी-निखरी लड़की जिसके सुनहरे बाल थे'.",
                    json.dumps(["गोरी-चिट्टी", "गोरी-निखरी", "सुनहरे बालों वाली", "चाँद जैसी गोरी"], ensure_ascii=False),
                    json.dumps(["सुनहरी लड़की", "सोने की लड़की"], ensure_ascii=False),
                    "global",
                ),
                (
                    "youth_sensual",
                    "virgin's plait / maiden youth",
                    "Never use awkward literal translations like 'कुंवारी चोटी'. Transpose with cultural naturalism and poetic sensuality as 'कमसिन की चोटी', 'कुंवारी लड़की की लंबी चोटी', or 'अछूती जवानी की लटें'.",
                    json.dumps(["कमसिन की चोटी", "कुंवारी लड़की की चोटी", "अछूती जवानी की लटें", "कमसिन जवानी"], ensure_ascii=False),
                    json.dumps(["कुंवारी चोटी"], ensure_ascii=False),
                    "global",
                ),
                (
                    "salutations",
                    "greetings / hello / courtesies",
                    "Align salutations dynamically with the active novel's cultural setting and character relationships. In Indic or formal literary works, use natural honorifics ('प्रणाम', 'नमस्ते', 'नमस्कार'). In informal, Nawabi, or rustic Hindustani dialogue, use appropriate spoken greetings ('आदाब', 'सलाम', 'कहो', 'और भाई'). Never force modern telephonic robotic phrasing like 'हेलो दोस्त'.",
                    json.dumps(["प्रणाम", "नमस्ते", "नमस्कार", "आदाब", "सलाम", "कहो"], ensure_ascii=False),
                    json.dumps(["हेलो दोस्त", "हाय मित्र"], ensure_ascii=False),
                    "dialogue",
                ),
                (
                    "beverages",
                    "wine, ale, spirits, plum alcohol",
                    "Use 'शराब', 'मदिरा', 'सुराही', or 'जाम' for tavern spirits, ales, and noble plum liqueurs. The word 'दारू' feels like cheap modern country bootleg/theka and breaks classic literary weight unless deliberately describing a filthy gutter brawl.",
                    json.dumps(["शराब", "मदिरा", "सुराही", "जाम", "मद्य"], ensure_ascii=False),
                    json.dumps(["दारू"], ensure_ascii=False),
                    "global",
                ),
                (
                    "sensual_idioms",
                    "popping cherry / losing virginity",
                    "Transpose into authentic dramatic spoken idioms: 'अपनी सील तुड़वाना / सील तोड़ना', 'कौमार्य गंवाना', or 'अछूता न रहना', capturing the earthy comedic or sensual tone without clinical medical words.",
                    json.dumps(["सील तुड़वाना", "सील तोड़ना", "कौमार्य गंवाना", "बिस्तर का जोश"], ensure_ascii=False),
                    json.dumps(["चेरी फोड़ना", "चेरी तोड़ना"], ensure_ascii=False),
                    "global",
                ),
                (
                    "profanity_grit",
                    "dialogue conflict & insult translation",
                    "Translate insults and conflict dialogue with authentic spoken cadence matching the source author's intensity. If the source is visceral or vulgar, preserve that raw intensity without artificial bowdlerization; if the source is mild or dignified, preserve its exact level without injecting gratuitous street profanity.",
                    json.dumps(["कमीने", "हरामी", "बदमाश", "नालायक", "गांड", "चूतड़"], ensure_ascii=False),
                    json.dumps(["हे दुराचारी मानव", "ओ पापी व्यक्ति"], ensure_ascii=False),
                    "dialogue",
                ),
                (
                    "anatomy_somatics",
                    "hips / bottom / waist / buttocks / thighs",
                    "Translate descriptive anatomical references and posture with natural living spoken somatic terms: 'कमर', 'कूल्हे', 'पुट्ठे', 'जांघें'. Strictly ban archaic Sanskrit dictionary roots ('नितंब', 'कटि', 'उरु').",
                    json.dumps(["कमर", "कूल्हे", "पुट्ठे", "जांघें"], ensure_ascii=False),
                    json.dumps(["नितंब", "कटि", "उरु"], ensure_ascii=False),
                    "global",
                ),
                (
                    "social_transactions",
                    "deal / proposal / agreement / bargain",
                    "Translate character negotiations and deals with living spoken conversational terms: 'सौदा', 'बात', 'तय होना', 'जुबान'. Strictly ban corporate or bureaucratic terms like 'प्रस्ताव' or 'समझौता-पत्र'.",
                    json.dumps(["सौदा", "बात", "तय होना", "जुबान"], ensure_ascii=False),
                    json.dumps(["प्रस्ताव", "समझौता-पत्र"], ensure_ascii=False),
                    "dialogue",
                ),
                (
                    "warfare_archetypes",
                    "warrior women / sellsword / cutthroat / insignia",
                    "Translate combat archetypes and insignia with grounded dramatic descriptions: 'लड़ाकू औरतें / लड़ाकू महिलाएं', 'किराए के लड़ाके', 'कातिल', 'शाही मुहर / निशान'. Strictly ban textbook poetry cliches like 'वीरांगनाएं' or 'राजचिह्न'.",
                    json.dumps(["लड़ाकू औरतें", "महिला योद्धा", "किराए के लड़ाके", "कातिल", "शाही मुहर"], ensure_ascii=False),
                    json.dumps(["वीरांगनाएं", "राजचिह्न"], ensure_ascii=False),
                    "global",
                ),
                (
                    "intimacy_somatics",
                    "somatic passion & dirty talk",
                    "Depict physical intimacy through somatic friction and breathing ('तपती कमर', 'भीगी प्यास', 'बेकाबू सांसें', 'कांपती उंगलियां', 'सीने पर नाखूनों का धंसना'). Strictly ban sterile clinical biology-textbook jargon.",
                    json.dumps(["तपती कमर", "भीगी प्यास", "बेकाबू सांसें", "कांपती उंगलियां", "मसलना"], ensure_ascii=False),
                    json.dumps(["योनि", "लिंग का संभोग"], ensure_ascii=False),
                    "intimacy",
                ),
                (
                    "universal_idioms",
                    "figurative tropes / certainty / mortality / conflict (Category A)",
                    "Never translate figurative English expressions literally. Transpose them sense-for-sense into Universal Spoken Hindustani Idioms (Category A: 'लिख के ले लो', 'मौत को दावत देना', 'हाथ साफ़ करना', 'खाल उधेड़ना', 'टांग अड़ाना'). Strictly ban culturally bound Indian village/panchayat tropes (Category B: 'गंगा नहाना', 'पंचों का फैसला', 'अशर्फी', 'नाच न जाने आँगन टेढ़ा').",
                    json.dumps(["लिख के ले लो", "मौत को दावत देना", "मौत के मुँह में कूदना", "हाथ साफ़ करना", "खाल उधेड़ना", "टांग अड़ाना", "पीठ में छुरा घोंपना"], ensure_ascii=False),
                    json.dumps(["गंगा नहाना", "पंचों का फैसला", "नाच न जाने आँगन टेढ़ा", "दूध का दूध पानी का पानी"], ensure_ascii=False),
                    "dialogue",
                ),
                (
                    "anti_calque_defense",
                    "English idioms (as sure as eggs is eggs / kick the bucket / keep your nose out)",
                    "Robotic literal calques destroy dramatic immersion. If an English speaker uses a colloquial idiom, map the underlying emotional meaning directly to organic spoken Hindustani dialogue punchlines rather than translating words literally.",
                    json.dumps(["सूरज का ढलना तय है", "पत्थर की लकीर", "जान गंवाना", "दखलंदाजी मत कर"], ensure_ascii=False),
                    json.dumps(["अंडे अंडे हैं", "बाल्टी को लात मारना", "अपनी नाक बाहर रखो"], ensure_ascii=False),
                    "global",
                ),
            ]

            for r in default_rules:
                exists = conn.execute(
                    "SELECT id FROM literary_advisory_rules WHERE category = ? AND source_concept = ?;",
                    (r[0], r[1])
                ).fetchone()
                if not exists:
                    conn.execute("""
                        INSERT INTO literary_advisory_rules 
                        (category, source_concept, guidance_rule, recommended_vocabulary, banned_antipatterns, context_scope)
                        VALUES (?, ?, ?, ?, ?, ?);
                    """, r)
            conn.commit()

    def get_formatted_prompt_guidelines(self) -> str:
        """Formats active rules into an authoritative instructional block for LLM system prompts."""
        with self._connection() as conn:
            rows = conn.execute("""
                SELECT category, source_concept, guidance_rule, recommended_vocabulary, banned_antipatterns
                FROM literary_advisory_rules
                ORDER BY id ASC;
            """).fetchall()

        if not rows:
            return ""

        lines = [
            "DYNAMIC LITERARY ADVISORY & SOMATIC TRANSPOSITION GUIDELINES (KNOWLEDGE BASE):"
        ]
        for row in rows:
            rec = ", ".join(f"'{w}'" for w in json.loads(row["recommended_vocabulary"]))
            banned = ", ".join(f"'{w}'" for w in json.loads(row["banned_antipatterns"]))
            lines.append(
                f"- [{row['category'].upper()} - {row['source_concept']}]: {row['guidance_rule']}\n"
                f"  * Recommended Authentic Vocabulary: {rec}\n"
                f"  * Banned Robotic Antipatterns (DO NOT USE): {banned}"
            )
        return "\n".join(lines)

    def get_banned_antipatterns_map(self) -> Dict[str, str]:
        """Returns mapping of banned antipattern tokens to recommended replacement hints."""
        with self._connection() as conn:
            rows = conn.execute("""
                SELECT banned_antipatterns, recommended_vocabulary
                FROM literary_advisory_rules;
            """).fetchall()

        mapping: Dict[str, str] = {}
        for row in rows:
            banned_list = json.loads(row["banned_antipatterns"])
            rec_list = json.loads(row["recommended_vocabulary"])
            rec_hint = rec_list[0] if rec_list else ""
            for banned in banned_list:
                mapping[banned] = rec_hint
        return mapping

    def get_candidates_for_concept(self, source_concept: str) -> List[str]:
        """Returns contextual candidate alternatives for a given English concept."""
        with self._connection() as conn:
            row = conn.execute("""
                SELECT recommended_vocabulary FROM literary_advisory_rules
                WHERE LOWER(source_concept) LIKE LOWER(?) OR LOWER(?) LIKE '%' || LOWER(source_concept) || '%'
                LIMIT 1;
            """, (f"%{source_concept}%", source_concept)).fetchone()
            if row:
                return json.loads(row["recommended_vocabulary"])
        return []

    def list_rules(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns all literary rules or rules filtered by category."""
        with self._connection() as conn:
            if category:
                rows = conn.execute(
                    "SELECT * FROM literary_advisory_rules WHERE category = ? ORDER BY id ASC;",
                    (category,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM literary_advisory_rules ORDER BY id ASC;"
                ).fetchall()
            return [dict(r) for r in rows]


_advisory_db_singleton: Optional[LiteraryAdvisoryDB] = None


def get_advisory_db(db_path: Optional[Path] = None) -> LiteraryAdvisoryDB:
    global _advisory_db_singleton
    if _advisory_db_singleton is None:
        _advisory_db_singleton = LiteraryAdvisoryDB(db_path)
    return _advisory_db_singleton
