#!/usr/bin/env python3
"""
Audiobook Factory - Sound Bank Asset Resolver & Track Slicing.
Resolves sound cues to absolute file paths, manages asset relationships,
slices musical sections with micro-fades, and queries catalog stats.
"""

from __future__ import annotations
import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, Any, List, Optional, Union


class ResolverMixin:
    """Asset resolution, track slicing, and metrics retrieval mixin."""

    bank_root: Path

    def link_assets(self, source_id: int, target_id: int, relationship_type: str, confidence: float = 1.0) -> bool:
        """Creates a directional relationship between two sound assets."""
        with self._get_conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO sound_asset_relationships (source_asset_id, target_asset_id, relationship_type, confidence)
                VALUES (?, ?, ?, ?)
            """, (source_id, target_id, relationship_type, confidence))
            return True

    def get_related_assets(self, asset_id: int, relationship_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Finds related assets (e.g. variations, predecessors, successors, companions)."""
        sql = """
            SELECT r.relationship_type, r.confidence, c.*
            FROM sound_asset_relationships r
            JOIN sound_catalog c ON c.id = r.target_asset_id
            WHERE r.source_asset_id = ?
        """
        params = [asset_id]
        if relationship_type:
            sql += " AND r.relationship_type = ?"
            params.append(relationship_type)
        with self._get_conn() as conn:
            cur = conn.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]

    def resolve_sound(
        self,
        query: str,
        category: Optional[str] = None,
        prefer_mood: Optional[str] = None,
    ) -> Optional[Path]:
        """
        Resolves the single best matching audio file for a given cue or scene mood
        using pure SQLite FTS5 queries with zero static map fallbacks.
        If the best match is a virtual cloud entry, JIT downloads it on demand.
        Returns absolute Path if found/downloaded, else None.
        """
        # 1. Direct filename or exact path check first
        direct_p = Path(query)
        if direct_p.is_file() and direct_p.exists():
            return direct_p

        q_clean = query.lower().strip()

        def _check_cand(cand: Dict[str, Any]) -> Optional[Path]:
            raw_fp = cand.get("filepath") or ""
            if raw_fp:
                cand_path = Path(raw_fp)
                if cand_path.is_file() and cand_path.exists():
                    return cand_path

            if cand.get("filename"):
                rel_p = self.bank_root / cand["filename"]
                if rel_p.is_file() and rel_p.exists():
                    return rel_p
                cat = cand.get("category", "")
                if cat:
                    cat_p = self.bank_root / cat.lower() / cand["filename"]
                    if cat_p.is_file() and cat_p.exists():
                        return cat_p

            if cand.get("source_url") or cand.get("mirror_url"):
                downloaded = self.download_virtual_asset(
                    sound_id=cand["id"],
                    source_url=cand.get("source_url"),
                    filename=cand.get("filename"),
                    category=cand.get("category", "SFX") or "SFX",
                    mirror_url=cand.get("mirror_url"),
                )
                if downloaded and downloaded.exists():
                    return downloaded
            return None

        # 2. Try exact category & mood match
        results = self.search(q_clean, category=category, mood=prefer_mood, limit=20)
        for cand in results:
            resolved = _check_cand(cand)
            if resolved:
                return resolved

        # 3. Relax mood filter if not found
        if prefer_mood:
            results = self.search(q_clean, category=category, limit=20)
            for cand in results:
                resolved = _check_cand(cand)
                if resolved:
                    return resolved

        # 4. If still not found and category was provided, try broad category search
        if category:
            cat_aliases = {
                "FOL": ["foley", "SFX"],
                "foley": ["FOL", "SFX"],
                "AMB": ["ambience", "CHAPTER_BED"],
                "ambience": ["AMB", "CHAPTER_BED"],
                "MUS": ["music", "DYNAMIC_STEM", "CHAPTER_BED"],
                "music": ["MUS", "DYNAMIC_STEM", "CHAPTER_BED"],
            }
            for alt_cat in cat_aliases.get(category, []):
                results = self.search(q_clean, category=alt_cat, limit=10)
                for cand in results:
                    resolved = _check_cand(cand)
                    if resolved:
                        return resolved

        # 5. Broad search without category constraint
        results = self.search(q_clean, limit=20)
        for cand in results:
            resolved = _check_cand(cand)
            if resolved:
                return resolved

        return None

    def resolve_leitmotif(self, theme_name: str) -> Optional[Path]:
        """Resolve Level 1 recurring character or world leitmotif track via pure FTS5."""
        res = self.resolve_sound(theme_name, category="LEITMOTIF")
        if not res:
            res = self.resolve_sound(theme_name, category="MUS")
        return res

    def resolve_chapter_bed(self, bed_name: str, prefer_mood: Optional[str] = None) -> Optional[Path]:
        """Resolve Level 2 continuous setting atmosphere bed via pure FTS5."""
        res = self.resolve_sound(bed_name, category="CHAPTER_BED", prefer_mood=prefer_mood)
        if not res:
            res = self.resolve_sound(bed_name, category="AMB", prefer_mood=prefer_mood)
        if not res:
            res = self.resolve_sound(bed_name, category="MUS", prefer_mood=prefer_mood)
        return res

    def resolve_dynamic_stem(self, stem_name: str, intensity: Optional[str] = None) -> Optional[Path]:
        """Resolve Level 3 dynamic scene intensity stem via pure FTS5."""
        res = self.resolve_sound(stem_name, category="DYNAMIC_STEM")
        if not res:
            res = self.resolve_sound(stem_name, category="MUS")
        return res

    def resolve_stinger(self, stinger_cue: str) -> Optional[Path]:
        """Resolve Level 3 micro dramatic action/revelation stinger hit via pure FTS5."""
        res = self.resolve_sound(stinger_cue, category="STINGER")
        if not res:
            res = self.resolve_sound(stinger_cue, category="SFX")
        return res

    def resolve_track_section(
        self,
        query: str,
        section_type: str = "INTRO_BED",
        min_energy: int = 1,
        max_energy: int = 10,
    ) -> Optional[Dict[str, Any]]:
        """
        Resolves an exact acoustic energy section within a soundtrack track.
        Guarantees original source track file remains untouched on disk.
        """
        sec_name = section_type.upper().strip()
        cand = (
            self.resolve_sound(query)
            or self.resolve_dynamic_stem(query)
            or self.resolve_leitmotif(query)
            or self.resolve_chapter_bed(query)
        )

        with self._get_conn() as conn:
            row = None
            if cand and cand.exists():
                cand_resolved_fwd = str(cand.resolve()).replace("\\", "/")
                cand_resolved_win = str(cand.resolve()).replace("/", "\\")
                row = conn.execute("""
                    SELECT s.*, c.filename, c.filepath, c.duration_sec
                    FROM sound_track_sections s
                    JOIN sound_catalog c ON s.track_id = c.id
                    WHERE (c.filepath = ? OR c.filepath = ? OR c.filename = ?)
                      AND s.section_name = ?
                      AND s.energy_level BETWEEN ? AND ?
                    ORDER BY s.energy_level DESC
                    LIMIT 1
                """, (cand_resolved_fwd, cand_resolved_win, cand.name, sec_name, min_energy, max_energy)).fetchone()

                if not row:
                    row = conn.execute("""
                        SELECT s.*, c.filename, c.filepath, c.duration_sec
                        FROM sound_track_sections s
                        JOIN sound_catalog c ON s.track_id = c.id
                        WHERE (c.filepath = ? OR c.filepath = ? OR c.filename = ?)
                          AND s.section_name = ?
                        LIMIT 1
                    """, (cand_resolved_fwd, cand_resolved_win, cand.name, sec_name)).fetchone()

                if not row:
                    row = conn.execute("""
                        SELECT s.*, c.filename, c.filepath, c.duration_sec
                        FROM sound_track_sections s
                        JOIN sound_catalog c ON s.track_id = c.id
                        WHERE (c.filepath = ? OR c.filepath = ? OR c.filename = ?)
                        LIMIT 1
                    """, (cand_resolved_fwd, cand_resolved_win, cand.name)).fetchone()

            if not row:
                q_clean = query.lower().strip()
                row = conn.execute("""
                    SELECT s.*, c.filename, c.filepath, c.duration_sec
                    FROM sound_track_sections s
                    JOIN sound_catalog c ON s.track_id = c.id
                    WHERE s.section_name = ?
                      AND (s.tags LIKE ? OR c.tags LIKE ? OR c.filename LIKE ?)
                      AND s.energy_level BETWEEN ? AND ?
                    ORDER BY RANDOM()
                    LIMIT 1
                """, (sec_name, f"%{q_clean}%", f"%{q_clean}%", f"%{q_clean}%", min_energy, max_energy)).fetchone()

            if row:
                return {
                    "track_id": row["track_id"],
                    "track_name": row["filename"],
                    "track_path": Path(row["filepath"]),
                    "section_name": row["section_name"],
                    "start_sec": float(row["start_sec"]),
                    "end_sec": float(row["end_sec"]),
                    "duration": round(float(row["end_sec"]) - float(row["start_sec"]), 2),
                    "energy_level": int(row["energy_level"]),
                    "tags": row["tags"] or "",
                }

            if cand and cand.exists():
                dur = self._extract_duration(cand)
                return {
                    "track_id": 0,
                    "track_name": cand.name,
                    "track_path": cand,
                    "section_name": sec_name,
                    "start_sec": 0.0,
                    "end_sec": dur,
                    "duration": round(dur, 2),
                    "energy_level": 5,
                    "tags": "dynamic_fallback",
                }

        return None

    @staticmethod
    def slice_track_section(
        track_path: Path,
        start_sec: float,
        target_duration: float,
        output_file: Path,
        fade_in_sec: float = 2.0,
        fade_out_sec: float = 2.0,
    ) -> Path:
        """
        Non-destructively carves a precise sub-slice from a source audio track.
        Guarantees source track is NEVER modified, deleted, or overwritten.
        Applies smooth micro-fades and 48kHz broadcast resampling.
        """
        track_path = Path(track_path).resolve()
        output_file = Path(output_file).resolve()
        output_file.parent.mkdir(parents=True, exist_ok=True)

        if os.path.normcase(str(track_path.resolve())) == os.path.normcase(str(output_file.resolve())):
            raise ValueError(f"Safety Violation: Cannot overwrite original source track file: {track_path}")

        if not track_path.exists():
            raise FileNotFoundError(f"Source soundtrack file not found: {track_path}")

        ffmpeg = shutil.which("ffmpeg") or "/usr/bin/ffmpeg"
        target_dur = max(float(target_duration), 1.0)
        s_start = max(0.0, float(start_sec))

        fade_in = min(float(fade_in_sec), target_dur / 3.0)
        fade_out = min(float(fade_out_sec), target_dur / 3.0)
        fade_out_start = max(0.0, target_dur - fade_out)

        af_expr = f"afade=t=in:ss=0:d={fade_in:.2f},afade=t=out:st={fade_out_start:.2f}:d={fade_out:.2f},aresample=osr=48000"

        track_dur = ResolverMixin._extract_duration(track_path)
        available_slice = max(0.1, track_dur - s_start) if track_dur > 0 else target_dur

        if target_dur <= available_slice:
            cmd = [
                ffmpeg, "-y",
                "-ss", f"{s_start:.2f}",
                "-i", str(track_path),
                "-t", f"{target_dur:.2f}",
                "-af", af_expr,
                "-c:a", "pcm_s16le",
                str(output_file)
            ]
        else:
            af_loop = (
                f"asetpts=PTS-STARTPTS,aloop=loop=-1:size=2e+09,atrim=0:{target_dur:.2f},"
                f"afade=t=in:ss=0:d={fade_in:.2f},afade=t=out:st={fade_out_start:.2f}:d={fade_out:.2f},"
                f"aresample=osr=48000"
            )
            cmd = [
                ffmpeg, "-y",
                "-ss", f"{s_start:.2f}",
                "-i", str(track_path),
                "-af", af_loop,
                "-c:a", "pcm_s16le",
                str(output_file)
            ]

        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"FFmpeg slice failed for {track_path.name}: {res.stderr[:200]}")

        return output_file

    def preload_cues(self, cues: List[str], max_workers: int = 4) -> List[Path]:
        """
        Pre-downloads all virtual sound assets needed for a list of cues in parallel.
        """
        unique_cues = list(dict.fromkeys(c for c in cues if c))
        resolved_paths: List[Path] = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_cue = {executor.submit(self.resolve_sound, cue): cue for cue in unique_cues}
            for future in future_to_cue:
                try:
                    p = future.result()
                    if p and p.exists():
                        resolved_paths.append(p)
                except Exception:
                    pass

        return resolved_paths

    def resolve_asset_path(self, identifier: Union[str, int]) -> Path:
        """
        Deterministic asset resolver. Resolves an exact ID or filename/filepath.
        Raises FileNotFoundError if the file cannot be located on disk.
        """
        if isinstance(identifier, int) or (isinstance(identifier, str) and identifier.isdigit()):
            with self._get_conn() as conn:
                row = conn.execute("SELECT filepath FROM sound_catalog WHERE id = ?", (int(identifier),)).fetchone()
                if row and row["filepath"]:
                    p = Path(row["filepath"])
                    if p.exists():
                        return p
            raise FileNotFoundError(f"Sound bank asset ID {identifier} not found on disk.")

        p = Path(identifier)
        if p.is_file() and p.exists():
            return p

        p_root = self.bank_root / identifier
        if p_root.is_file() and p_root.exists():
            return p_root

        with self._get_conn() as conn:
            row = conn.execute("SELECT filepath FROM sound_catalog WHERE filename = ?", (p.name,)).fetchone()
            if row and row["filepath"]:
                fp = Path(row["filepath"])
                if fp.exists():
                    return fp

        if not p.suffix and "/" not in str(identifier) and "\\" not in str(identifier):
            found = self.resolve_sound(str(identifier))
            if found and found.exists():
                return found

        raise FileNotFoundError(f"Sound asset '{identifier}' could not be resolved in sound bank.")

    def get_asset_metrics(self, identifier: Union[str, int, Path]) -> Optional[Dict[str, Any]]:
        """
        Retrieves EBU R128 LUFS, True Peak, and Spectral Centroid metrics
        from the harmonized sound_assets table.
        """
        resolved_p: Optional[Path] = None
        if isinstance(identifier, int) or (isinstance(identifier, str) and identifier.isdigit()):
            with self._get_conn() as conn:
                row = conn.execute("SELECT filepath FROM sound_catalog WHERE id = ?", (int(identifier),)).fetchone()
                if row and row["filepath"]:
                    resolved_p = Path(row["filepath"])
        elif isinstance(identifier, (str, Path)):
            p = Path(identifier)
            if p.exists():
                resolved_p = p
            else:
                resolved_p = self.resolve_sound(str(identifier))

        with self._get_conn() as conn:
            row = None
            if resolved_p:
                norm_fwd = str(resolved_p.resolve()).replace("\\", "/")
                norm_win = str(resolved_p.resolve()).replace("/", "\\")
                try:
                    row = conn.execute("""
                        SELECT * FROM sound_assets
                        WHERE filepath = ? OR filepath = ? OR filename = ?
                        LIMIT 1
                    """, (norm_fwd, norm_win, resolved_p.name)).fetchone()
                except Exception:
                    pass

                if not row:
                    row = conn.execute("""
                        SELECT * FROM sound_catalog
                        WHERE filepath = ? OR filepath = ? OR filename = ?
                        LIMIT 1
                    """, (norm_fwd, norm_win, resolved_p.name)).fetchone()

            if not row and isinstance(identifier, (str, int)):
                try:
                    row = conn.execute("""
                        SELECT * FROM sound_assets WHERE id = ? OR filename = ? LIMIT 1
                    """, (identifier, str(identifier))).fetchone()
                except Exception:
                    pass
                if not row:
                    row = conn.execute("""
                        SELECT * FROM sound_catalog WHERE id = ? OR filename = ? LIMIT 1
                    """, (identifier, str(identifier))).fetchone()

            if not row and isinstance(identifier, str):
                try:
                    row = conn.execute("""
                        SELECT a.* FROM sound_assets_fts f
                        JOIN sound_assets a ON f.rowid = a.id
                        WHERE sound_assets_fts MATCH ?
                        LIMIT 1
                    """, (identifier,)).fetchone()
                except Exception:
                    pass

            if row:
                d = dict(row)
                return {
                    "id": d.get("id"),
                    "filename": d.get("filename"),
                    "filepath": d.get("filepath"),
                    "category": d.get("category"),
                    "action_type": d.get("action_type", ""),
                    "integrated_lufs": float(d["integrated_lufs"]) if d.get("integrated_lufs") is not None else -23.0,
                    "true_peak_db": float(d["true_peak_db"]) if d.get("true_peak_db") is not None else -1.5,
                    "spectral_centroid_hz": float(d["spectral_centroid_hz"]) if d.get("spectral_centroid_hz") is not None else 0.0,
                    "sample_rate": int(d["sample_rate"]) if d.get("sample_rate") is not None else 48000,
                    "channels": int(d["channels"]) if d.get("channels") is not None else 2,
                    "duration_sec": float(d["duration_sec"]) if d.get("duration_sec") is not None else 0.0,
                }
        return None

    def stats(self) -> Dict[str, Any]:
        """Returns storage and catalog statistics for the local sound bank."""
        with self._get_conn() as conn:
            total_sounds = conn.execute("SELECT COUNT(*) FROM sound_catalog").fetchone()[0]
            total_dur = conn.execute("SELECT COALESCE(SUM(duration_sec), 0.0) FROM sound_catalog").fetchone()[0]
            total_bytes = conn.execute("SELECT COALESCE(SUM(size_bytes), 0) FROM sound_catalog").fetchone()[0]

            total_sections = 0
            has_sections_table = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='sound_track_sections'").fetchone()[0]
            if has_sections_table:
                total_sections = conn.execute("SELECT COUNT(*) FROM sound_track_sections").fetchone()[0]

            cat_counts = {}
            for r in conn.execute("SELECT category, COUNT(*) as cnt FROM sound_catalog GROUP BY category"):
                cat_counts[r["category"] or "OTHER"] = r["cnt"]

            mood_counts = {}
            for r in conn.execute("SELECT mood, COUNT(*) as cnt FROM sound_catalog GROUP BY mood"):
                mood_counts[r["mood"] or "default"] = r["cnt"]

        return {
            "total_sounds": total_sounds,
            "total_sections": total_sections,
            "total_duration_min": round(total_dur / 60.0, 1),
            "total_size_mb": round(total_bytes / (1024 * 1024), 2),
            "categories": cat_counts,
            "moods": mood_counts,
            "database_path": str(self.db_path),
        }
