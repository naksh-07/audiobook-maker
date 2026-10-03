#!/usr/bin/env python3
"""
Audiobook Factory - Sound Bank Search Operations.
FTS5 full-text search, BM25 rank scoring, multi-dimensional virtual catalog queries,
energy-level music search, and index rebuilding.
"""

from __future__ import annotations
import re
from typing import Dict, Any, List, Optional

from audiobook_factory.logger import logger


class SearchMixin:
    """FTS5 search and ranking operations mixin for SoundBank."""

    def search_virtual_catalog(
        self,
        query: str = "",
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
        wave_style: Optional[str] = None,
        exciter: Optional[str] = None,
        resonator: Optional[str] = None,
        action_type: Optional[str] = None,
        dramatic_role: Optional[str] = None,
        mood: Optional[str] = None,
        min_bpm: Optional[float] = None,
        max_bpm: Optional[float] = None,
        min_duration: Optional[float] = None,
        max_duration: Optional[float] = None,
        whisper_safe_only: bool = False,
        is_downloaded_only: bool = False,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Hybrid Sonic Intelligence Retrieval across local and virtual sound catalogs.
        Evaluates multi-dimensional criteria (physical, temporal, dramatic, mix compatibility)
        and returns explainable candidate cards with detailed scoring.
        """
        raw_words = re.findall(r"[a-zA-Z0-9]+", query.strip())
        meaningful_words = [
            w for w in raw_words
            if w.lower() not in ("wav", "mp3", "flac", "ogg", "aiff", "m4a", "and", "or", "not", "near")
        ]

        where_clauses = []
        params = []

        fts_match = False
        if meaningful_words:
            fts_query_and = " AND ".join(f'"{w}"*' for w in meaningful_words)
            where_clauses.append("c.id IN (SELECT rowid FROM sound_catalog_fts WHERE sound_catalog_fts MATCH ?)")
            params.append(fts_query_and)
            fts_match = True

        if category:
            cat_norm = category.upper()
            if cat_norm in ("FOLEY", "FOL", "SFX"):
                where_clauses.append("c.category IN ('FOL', 'SFX')")
            elif cat_norm in ("MUSIC", "MUS"):
                where_clauses.append("c.category IN ('MUS', 'LEITMOTIF', 'CHAPTER_BED', 'DYNAMIC_STEM')")
            elif cat_norm in ("AMBIENCE", "AMB"):
                where_clauses.append("c.category IN ('AMB', 'CHAPTER_BED')")
            else:
                where_clauses.append("c.category = ?")
                params.append(cat_norm)

        if subcategory:
            where_clauses.append("LOWER(c.subcategory) = LOWER(?)")
            params.append(subcategory)

        if wave_style:
            where_clauses.append("LOWER(c.wave_style) = LOWER(?)")
            params.append(wave_style)

        if exciter:
            where_clauses.append("(LOWER(c.exciter) LIKE ? OR LOWER(c.tags) LIKE ?)")
            params.extend([f"%{exciter.lower()}%", f"%{exciter.lower()}%"])

        if resonator:
            where_clauses.append("(LOWER(c.resonator) LIKE ? OR LOWER(c.tags) LIKE ?)")
            params.extend([f"%{resonator.lower()}%", f"%{resonator.lower()}%"])

        if action_type:
            where_clauses.append("(LOWER(c.action_type) LIKE ? OR LOWER(c.tags) LIKE ?)")
            params.extend([f"%{action_type.lower()}%", f"%{action_type.lower()}%"])

        if dramatic_role:
            where_clauses.append("LOWER(c.dramatic_role) = LOWER(?)")
            params.append(dramatic_role)

        if mood:
            where_clauses.append("LOWER(c.mood) = LOWER(?)")
            params.append(mood)

        if min_bpm is not None:
            where_clauses.append("c.tempo_bpm >= ?")
            params.append(min_bpm)
        if max_bpm is not None:
            where_clauses.append("c.tempo_bpm <= ?")
            params.append(max_bpm)

        if min_duration is not None:
            where_clauses.append("c.duration_sec >= ?")
            params.append(min_duration)
        if max_duration is not None:
            where_clauses.append("c.duration_sec <= ?")
            params.append(max_duration)

        if whisper_safe_only:
            where_clauses.append("c.whisper_compatibility >= 0.4 AND c.voice_masking_risk != 'SEVERE'")

        if is_downloaded_only:
            where_clauses.append("c.is_downloaded = 1")

        sql = """
            SELECT c.*,
                   a.integrated_lufs as dsp_lufs,
                   a.true_peak_db as dsp_peak,
                   a.spectral_centroid_hz as dsp_centroid
            FROM sound_catalog c
            LEFT JOIN sound_assets a ON (a.filepath = c.filepath OR a.filename = c.filename)
        """
        if where_clauses:
            sql += " WHERE " + " AND ".join(where_clauses)

        sql += " ORDER BY c.is_downloaded DESC, c.id ASC LIMIT ?"
        params.append(limit * 3)

        with self._get_conn() as conn:
            cur = conn.execute(sql, params)
            candidates = [dict(row) for row in cur.fetchall()]

        # If strict AND FTS yielded nothing, try broad recall fallback
        if not candidates and fts_match and len(meaningful_words) > 1:
            fts_query_or = " OR ".join(f"{w}*" for w in meaningful_words)
            where_clauses[0] = "c.id IN (SELECT rowid FROM sound_catalog_fts WHERE sound_catalog_fts MATCH ?)"
            params[0] = fts_query_or
            sql_fallback = """
                SELECT c.*,
                       a.integrated_lufs as dsp_lufs,
                       a.true_peak_db as dsp_peak,
                       a.spectral_centroid_hz as dsp_centroid
                FROM sound_catalog c
                LEFT JOIN sound_assets a ON (a.filepath = c.filepath OR a.filename = c.filename)
                WHERE """ + " AND ".join(where_clauses) + " ORDER BY c.is_downloaded DESC, c.id ASC LIMIT ?"
            with self._get_conn() as conn:
                cur = conn.execute(sql_fallback, params)
                candidates = [dict(row) for row in cur.fetchall()]

        scored_results = []
        for cand in candidates:
            score = 0.5
            reasons = []

            # Physical semantic alignment
            if exciter and (exciter.lower() in cand.get("exciter", "").lower() or exciter.lower() in cand.get("tags", "").lower()):
                score += 0.25
                reasons.append(f"Physical exciter '{exciter}' matched")
            if resonator and (resonator.lower() in cand.get("resonator", "").lower() or resonator.lower() in cand.get("tags", "").lower()):
                score += 0.20
                reasons.append(f"Resonator acoustic space '{resonator}' matched")
            if action_type and action_type.lower() in cand.get("action_type", "").lower():
                score += 0.20
                reasons.append(f"Physical action '{action_type}' matched")

            # Dramatic alignment
            if mood and cand.get("mood", "").lower() == mood.lower():
                score += 0.15
                reasons.append(f"Dramatic mood '{mood}' matched")
            if dramatic_role and cand.get("dramatic_role", "").lower() == dramatic_role.lower():
                score += 0.15
                reasons.append(f"Dramatic role '{dramatic_role}' matched")

            # Mix safety
            w_comp = float(cand.get("whisper_compatibility") or 0.5)
            if whisper_safe_only:
                score += (w_comp * 0.2)
                reasons.append(f"Whisper compatibility {w_comp:.2f}")

            v_risk = cand.get("voice_masking_risk", "LOW")
            if v_risk == "SEVERE":
                score -= 0.20
                reasons.append("Severe voice masking penalty applied (-0.20)")

            # Local availability bonus
            if cand.get("is_downloaded"):
                score += 0.05
                reasons.append("Locally cached asset (+0.05)")

            cand["retrieval_score"] = round(min(1.0, max(0.0, score)), 2)
            cand["why_matched"] = reasons if reasons else ["General catalog text match"]
            scored_results.append(cand)

        scored_results.sort(key=lambda x: (x["retrieval_score"], x.get("is_downloaded", 0)), reverse=True)
        return scored_results[:limit]

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        mood: Optional[str] = None,
        limit: int = 5,
        era: Optional[str] = None,
        franchise_affinity: Optional[str] = None,
        negative_tags: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Executes sub-millisecond FTS5 search against sound bank (local + virtual).
        First tries high-precision AND matching across terms; falls back to OR matching.
        Enforces optional Era and Franchise affinity filters to prioritize canon lore assets.
        """
        raw_words = re.findall(r"[a-zA-Z0-9]+", query.strip())
        if not raw_words:
            return []

        meaningful_words = [w for w in raw_words if w.lower() not in ("wav", "mp3", "flac", "ogg", "aiff", "m4a")]
        search_words = meaningful_words if meaningful_words else raw_words

        fts_query_and = " AND ".join(f"{w}*" for w in search_words)
        fts_query_or = " OR ".join(f"{w}*" for w in search_words)

        def _execute_fts(fts_term: str) -> List[Dict[str, Any]]:
            franchise_clause = ""
            order_clause = ""
            params = [fts_term]

            sql = """
                SELECT c.id, c.filename, c.filepath, c.category, c.subcategory, c.mood, c.tags,
                       c.duration_sec, c.size_bytes, c.source_url, c.is_downloaded,
                       c.franchise_affinity, c.lore_tags, rank,
                       a.integrated_lufs, a.true_peak_db, a.spectral_centroid_hz
                FROM sound_catalog_fts f
                JOIN sound_catalog c ON f.rowid = c.id
                LEFT JOIN sound_assets a ON (a.filepath = c.filepath OR a.filename = c.filename)
                WHERE sound_catalog_fts MATCH ?
            """

            if category:
                cat_norm = category.upper()
                if cat_norm in ("FOLEY", "FOL"):
                    sql += " AND c.category IN ('FOL', 'SFX') AND (c.duration_sec IS NULL OR c.duration_sec <= 4.5)"
                    sql += " AND c.filepath NOT LIKE '%/music/%' AND c.filepath NOT LIKE '%\\music\\%'"
                elif cat_norm == "SFX":
                    sql += " AND c.category IN ('SFX', 'FOL') AND (c.duration_sec IS NULL OR c.duration_sec <= 6.0)"
                    sql += " AND c.filepath NOT LIKE '%/music/%' AND c.filepath NOT LIKE '%\\music\\%'"
                elif cat_norm in ("MUSIC", "MUS"):
                    sql += " AND c.category IN ('MUS', 'LEITMOTIF', 'CHAPTER_BED', 'DYNAMIC_STEM')"
                elif cat_norm in ("AMBIENCE", "AMB"):
                    sql += " AND c.category IN ('AMB', 'CHAPTER_BED')"
                elif cat_norm in ("STINGER",):
                    sql += " AND c.category IN ('SFX', 'DYNAMIC_STEM', 'MUS')"
                else:
                    sql += " AND c.category = ?"
                    params.append(cat_norm)

            if mood:
                sql += " AND c.mood = ?"
                params.append(mood.lower())

            if franchise_affinity:
                sql += " ORDER BY (CASE WHEN LOWER(c.franchise_affinity) = LOWER(?) THEN 100 ELSE 0 END) DESC, c.is_downloaded DESC, rank LIMIT ?"
                params.extend([franchise_affinity, limit * 3 if (era or negative_tags) else limit])
            else:
                sql += " ORDER BY c.is_downloaded DESC, rank LIMIT ?"
                params.append(limit * 3 if (era or negative_tags) else limit)

            with self._get_conn() as conn:
                cur = conn.execute(sql, params)
                return [dict(row) for row in cur.fetchall()]

        # High-precision AND search first
        results = _execute_fts(fts_query_and)
        if not results and len(search_words) > 1:
            # Broad-recall OR fallback
            results = _execute_fts(fts_query_or)

        # Era & Negative Tag Filtering (only ban blatant anachronisms, never narrative props)
        banned = set(negative_tags or [])
        if era and era.upper() in ("MODERN", "MODERN_CONTEMPORARY"):
            banned.update({"catapult", "drawbridge", "trebuchet", "battering_ram"})
        elif era and era.upper() == "MEDIEVAL_FANTASY":
            banned.update({
                "car", "automobile", "engine", "traffic", "gunshot", "phone", "telephone",
                "siren", "computer", "subway", "train", "airplane", "helicopter",
                "grader", "shambling", "studded boots", "troops", "soldiers shambling",
                "santiago", "chile", "refrigerator", "office"
            })

        if banned:
            filtered = []
            for r in results:
                fname = (r.get("filename") or "").lower()
                ftags = (r.get("tags") or "").lower()
                fpath = (r.get("filepath") or "").lower()
                if not any(b in fname or b in ftags or b in fpath for b in banned):
                    filtered.append(r)
            results = filtered[:limit]

        return results

    def search_music_catalog(
        self,
        query: str,
        section_type: Optional[str] = None,
        max_energy: Optional[int] = None,
        target_valence: Optional[float] = None,
        target_arousal: Optional[float] = None,
        limit: int = 5,
        franchise_affinity: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Dynamically searches the full music soundtrack catalog and energy sections.
        Returns candidate tracks with energy levels, start/end seconds, tags, and Sonic Genome.
        Prioritizes canon franchise assets when franchise_affinity is provided.
        """
        raw_words = re.findall(r"[a-zA-Z0-9]+", query.strip())
        if not raw_words:
            return []
        fts_query = " OR ".join(f"{w}*" for w in raw_words)

        sql = """
            SELECT c.id, c.filename, c.filepath, c.mood, c.tags, c.duration_sec, c.sonic_genome,
                   c.genome_valence, c.genome_arousal, c.franchise_affinity, c.lore_tags,
                   s.id as section_id, s.section_name, s.start_sec, s.end_sec, s.energy_level, s.tempo_bpm, s.tags as section_tags,
                   rank
            FROM sound_catalog_fts f
            JOIN sound_catalog c ON f.rowid = c.id
            LEFT JOIN sound_track_sections s ON s.track_id = c.id
            WHERE sound_catalog_fts MATCH ?
              AND c.category IN ('MUS', 'CHAPTER_BED', 'LEITMOTIF', 'DYNAMIC_STEM')
        """
        params: List[Any] = [fts_query]

        if section_type and section_type != "ANY":
            sql += " AND s.section_name = ?"
            params.append(section_type)

        if max_energy is not None:
            sql += " AND (s.energy_level IS NULL OR s.energy_level <= ?)"
            params.append(max_energy)

        if target_valence is not None:
            sql += " AND (c.genome_valence IS NULL OR abs(c.genome_valence - ?) <= 0.45)"
            params.append(target_valence)

        if target_arousal is not None:
            sql += " AND (c.genome_arousal IS NULL OR abs(c.genome_arousal - ?) <= 0.45)"
            params.append(target_arousal)

        if franchise_affinity:
            sql += " GROUP BY c.id ORDER BY (CASE WHEN LOWER(c.franchise_affinity) = LOWER(?) THEN 1 ELSE 0 END) DESC, rank LIMIT ?"
            params.extend([franchise_affinity, limit])
        else:
            sql += " GROUP BY c.id ORDER BY rank LIMIT ?"
            params.append(limit)

        with self._get_conn() as conn:
            cur = conn.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]

    def rebuild_search_index(self) -> bool:
        """Rebuilds the SQLite FTS5 virtual table for sound_catalog."""
        with self._get_conn() as conn:
            try:
                conn.execute("INSERT INTO sound_catalog_fts(sound_catalog_fts) VALUES('rebuild');")
                conn.commit()
                return True
            except Exception as e:
                logger.error(f"Failed to rebuild FTS5 index: {e}")
                return False
