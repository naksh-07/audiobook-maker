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
            count = conn.execute("SELECT COUNT(*) AS cnt FROM literary_advisory_rules;").fetchone()["cnt"]
            if count > 0:
                return

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
                    "In dark-fantasy Hindustani audio drama, textbook Hindi 'नमस्ते' or religious 'राम-राम' completely destroys medieval grit and immersion. Use universe-grounded Hindustani: 'सलाम, [नाम]', 'कहो, [नाम]', 'आदाब', or 'और भाई [नाम]'.",
                    json.dumps(["सलाम", "कहो", "आदाब", "और भाई"], ensure_ascii=False),
                    json.dumps(["नमस्ते", "राम-राम", "नमस्कार"], ensure_ascii=False),
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
                    "tavern banter & gritty insult amplification",
                    "Translate medieval insults with earthy rustic Hindustani grit ('बकचोदी बंद करो', 'हरामी', 'कमीने', 'गांड', 'अंडकोष बधिया करना', 'सूअर का पेशाब'). Maintain organic raw emotion while avoiding textbook TV-serial softening.",
                    json.dumps(["बकचोदी", "गांड", "अंडकोष बधिया करना", "सूअर का पेशाब", "हरामी", "कमीने"], ensure_ascii=False),
                    json.dumps(["दुष्ट", "बुरी स्त्री", "नितंब", "चूतड़"], ensure_ascii=False),
                    "dialogue",
                ),
                (
                    "intimacy_somatics",
                    "somatic passion & dirty talk",
                    "Depict physical intimacy through somatic friction and breathing ('तपती कमर', 'भीगी प्यास', 'बेकाबू सांसें', 'कांपती उंगलियां', 'सीने पर नाखूनों का धंसना'). Strictly ban sterile clinical biology-textbook jargon.",
                    json.dumps(["तपती कमर", "भीगी प्यास", "बेकाबू सांसें", "कांपती उंगलियां", "मसलना"], ensure_ascii=False),
                    json.dumps(["योनि", "लिंग का संभोग"], ensure_ascii=False),
                    "intimacy",
                ),
            ]

            conn.executemany("""
                INSERT INTO literary_advisory_rules 
                (category, source_concept, guidance_rule, recommended_vocabulary, banned_antipatterns, context_scope)
                VALUES (?, ?, ?, ?, ?, ?);
            """, default_rules)
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
