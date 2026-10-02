from __future__ import annotations
import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from audiobook_factory.logger import logger
from audiobook_factory.contracts import MusicCue

class MusicDirectorMixin:
    def _pass2_music_director(
        self,
        cues_plan: List[Dict[str, Any]],
        seg_starts_ms: Dict[int, int],
        total_duration_ms: int,
        sonic_bible: Optional[Any] = None,
    ) -> List[MusicCue]:
        """
        Pass 2: Music Director executes dynamic FTS5 queries against the sound catalog.
        Queries for mood, tempo, timbre, energy section.
        MANDATE: Graceful fallback to pure silence, NEVER hardcoded tracks.
        """
        music_cues: List[MusicCue] = []
        max_music_budget_ms = int(total_duration_ms * 0.40)
        accumulated_music_ms = 0

        for idx, cue_data in enumerate(cues_plan):
            if accumulated_music_ms >= max_music_budget_ms:
                # Timeline silence mandate reached: remaining cues omitted for silence
                break

            # 0. Check if cue is bound to a canonical Sonic Bible leitmotif
            lm_ref = cue_data.get("leitmotif_ref", "")
            resolved_motif = None
            if lm_ref and sonic_bible and hasattr(sonic_bible, "leitmotifs"):
                resolved_motif = sonic_bible.leitmotifs.get(lm_ref.lower()) or sonic_bible.leitmotifs.get(lm_ref)

            chosen_track = ""
            track_id = 0
            section_start_sec = 0.0
            results: List[Dict[str, Any]] = []

            if resolved_motif:
                chosen_track = getattr(resolved_motif, "track_name", "")
                raw_tid = getattr(resolved_motif, "track_id", 0)
                track_id = int(raw_tid) if str(raw_tid).isdigit() else 0
                section_start_sec = float(getattr(resolved_motif, "default_section_start_sec", 0.0) or 0.0)
                energy_sec = cue_data.get("energy_section", "INTRO_BED")
                # Look up track in sound bank to fetch its sonic_genome (for spectral notch & duration)
                results = self.sound_bank.search_music_catalog(chosen_track, limit=1)
            else:
                # Dynamic query formulated from narrative archetype, mood, tempo, timbre, and search query
                search_q = str(cue_data.get("search_query", "") or "").strip()
                if search_q:
                    # If an explicit search_query was requested, verify that the catalog has matching assets
                    # for the primary query before diluting with secondary mood/timbre keywords.
                    pre_check = self.sound_bank.search_music_catalog(search_q, limit=1)
                    if not pre_check:
                        pre_check = self.sound_bank.search(search_q, category="music", limit=1)
                    if not pre_check:
                        # Sonic Intelligence: Attempt query expansion and stop-word relaxation before dropping cue
                        try:
                            from audiobook_factory.sonic_intelligence_bridge import SonicIntelligenceBridge
                            bridge = SonicIntelligenceBridge(sound_bank=self.sound_bank)
                            relaxed_cands = bridge.normalize_and_expand_query(search_q, category="music")
                            for rc in relaxed_cands:
                                pre_check = self.sound_bank.search_music_catalog(rc, limit=1) or self.sound_bank.search(rc, category="music", limit=1)
                                if pre_check:
                                    search_q = rc
                                    break
                        except Exception:
                            pass

                    if not pre_check:
                        logger.info(
                            f"  [-] Music Director: No matching asset in catalog for primary query '{search_q}'. "
                            f"Falling back gracefully to pure acoustic silence (0 hardcoded tracks)."
                        )
                        continue

                q_terms = [
                    cue_data.get("narrative_archetype", ""),
                    search_q,
                    cue_data.get("mood", ""),
                    cue_data.get("timbre", ""),
                    cue_data.get("tempo", ""),
                ]
                clean_query = " ".join([t for t in q_terms if t]).strip() or "orchestral drama"
                energy_sec = cue_data.get("energy_section", "INTRO_BED")

                target_val = cue_data.get("valence")
                target_aro = cue_data.get("arousal")
                try:
                    t_val = float(target_val) if target_val is not None else None
                except (ValueError, TypeError):
                    t_val = None
                try:
                    t_aro = float(target_aro) if target_aro is not None else None
                except (ValueError, TypeError):
                    t_aro = None

                # 1. Query with energy section filter and emotional valence/arousal
                results = self.sound_bank.search_music_catalog(
                    clean_query,
                    section_type=energy_sec,
                    target_valence=t_val,
                    target_arousal=t_aro,
                    limit=3,
                )

                # 2. Relax valence/arousal filter if not found
                if not results:
                    results = self.sound_bank.search_music_catalog(clean_query, section_type=energy_sec, limit=3)

                # 3. Relax energy section filter if not found
                if not results:
                    results = self.sound_bank.search_music_catalog(clean_query, limit=3)

                # 4. Fallback to general music FTS5 search
                if not results:
                    results = self.sound_bank.search(clean_query, category="music", limit=3)

                # 5. CRITICAL RULE: GRACEFUL FALLBACK TO PURE SILENCE, NEVER HARDCODED TRACKS
                if not results:
                    logger.info(
                        f"  [-] Music Director: No matching asset in catalog for query '{clean_query}'. "
                        f"Falling back gracefully to pure acoustic silence (0 hardcoded tracks)."
                    )
                    continue

                chosen_track = results[0]["filename"]
                track_id = results[0].get("id", 0)
                section_start_sec = float(results[0].get("start_sec", 0.0) or 0.0)

            # Check Sonic Genome for vocal masking risk
            spectral_notch = False
            if results:
                g_str = results[0].get("sonic_genome", "{}")
                if g_str and g_str != "{}":
                    try:
                        g_json = json.loads(g_str)
                        if g_json.get("acoustic", {}).get("vocal_clash_risk") in ("MODERATE", "SEVERE"):
                            spectral_notch = True
                    except Exception:
                        pass

            trigger_seg = cue_data.get("trigger_segment", 1)
            start_ms = seg_starts_ms.get(trigger_seg, 0)

            # Timeline bounds and budget capping
            if start_ms >= total_duration_ms:
                continue

            dur_ms = int(float(cue_data.get("duration_sec", 30.0)) * 1000)
            until_seg = cue_data.get("until_segment")
            if until_seg:
                try:
                    u_idx = int(until_seg)
                    if u_idx in seg_starts_ms and seg_starts_ms[u_idx] > start_ms:
                        dur_ms = seg_starts_ms[u_idx] - start_ms
                except (ValueError, TypeError):
                    pass

            remaining_budget = max_music_budget_ms - accumulated_music_ms
            dur_ms = min(dur_ms, remaining_budget, total_duration_ms - start_ms)
            if dur_ms < 500:
                continue

            accumulated_music_ms += dur_ms

            music_cues.append(
                MusicCue(
                    cue_id=cue_data.get("cue_id", f"mc_{idx+1:03d}"),
                    cue_type=cue_data.get("cue_type", "TRANSITION_BRIDGE"),
                    track_name=chosen_track,
                    track_id=track_id,
                    section_name=energy_sec,
                    section_start_sec=section_start_sec,
                    start_ms=start_ms,
                    duration_ms=dur_ms,
                    fade_in_ms=int(float(cue_data.get("fade_in_sec", 3.0)) * 1000),
                    fade_out_ms=int(float(cue_data.get("fade_out_sec", 4.0)) * 1000),
                    volume_db=float(cue_data.get("volume_db", -18.0)),
                    dramatic_justification=cue_data.get("dramatic_justification", ""),
                    leitmotif_ref=lm_ref or (getattr(resolved_motif, "motif_id", "") if resolved_motif else ""),
                    spectral_notch_needed=spectral_notch,
                    target_valence=cue_data.get("valence"),
                    target_arousal=cue_data.get("arousal"),
                    narrative_archetype=cue_data.get("narrative_archetype"),
                )
            )

        return music_cues

    # =========================================================================
    # PASS 3 IMPLEMENTATION: Acoustic Foley (Dependency parsing, word alignment)
    # =========================================================================
