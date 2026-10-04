"""
Audiobook Factory - Multi-Agent Studio Directing Orchestrator (v5.0).
Coordinates the 5 specialized Hollywood Directing Agents across the 100+ key pool:
1. ShowrunnerAgent: Full-chapter macro narrative arc and dramatic act boundaries.
2. ScenographerAgent: Room geometry, materials, and Convolution IR spatial acoustic staging.
3. MicroFoleyAgent: Dense macro-actions and living-world micro-foley (mugs, cloth, hearth, chairs).
4. MusicSupervisorAgent: Scene transition stingers, thematic motifs, and dynamic underscores (>= 60% silence).
5. WallahDirectorAgent: Multi-layer background atmosphere and dynamic crowd breathing automations.
"""

from __future__ import annotations
import os
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor

from audiobook_factory.logger import logger
from audiobook_factory.sound_bank import SoundBank, get_sound_bank
from audiobook_factory.contracts.manifest import (
    CreativeManifest,
    FoleyCue,
    MusicCue,
    AmbienceScene,
    MasteringConfig,
    ConvolutionIRConfig,
    WallahAutomationPoint,
)
from audiobook_factory.director.agents import (
    ShowrunnerAgent,
    ShowrunnerPlan,
    ScenographerAgent,
    ScenographyPlan,
    MicroFoleyAgent,
    MicroFoleyPlan,
    MusicSupervisorAgent,
    MusicScoringPlan,
    WallahDirectorAgent,
    WallahEnvironmentPlan,
)


class MultiAgentDirector:
    """Master orchestrator for the 5 specialized Hollywood Directing Agents."""

    def __init__(
        self,
        sound_bank: Optional[SoundBank] = None,
        model: Optional[str] = None,
        project_dir: Optional[Path] = None,
    ):
        self.sound_bank = sound_bank or get_sound_bank()
        self.model = model
        self.project_dir = Path(project_dir) if project_dir else None

        # Instantiate the 5 specialized agents
        self.showrunner = ShowrunnerAgent(model=model)
        self.scenographer = ScenographerAgent(model=model)
        self.foley_artist = MicroFoleyAgent(model=model)
        self.music_supervisor = MusicSupervisorAgent(model=model)
        self.wallah_director = WallahDirectorAgent(model=model)

    def direct_chapter(
        self,
        chapter_id: str,
        script_segments: List[Dict[str, Any]],
        segment_durations_sec: Dict[int, float],
        seg_starts_ms: Dict[int, int],
        total_duration_sec: float,
        era: str = "MEDIEVAL_FANTASY",
        franchise_affinity: Optional[str] = None,
        dramatic_theme: str = "Cinematic Audio Drama",
        title: str = "",
        author: str = "",
        sonic_bible: Optional[Dict[str, Any]] = None,
        book_dna: Optional[Dict[str, Any]] = None,
    ) -> CreativeManifest:
        """
        Executes end-to-end multi-agent directing pass and returns a broadcast-standard CreativeManifest.
        """
        total_segs = len(script_segments)
        total_duration_ms = int(total_duration_sec * 1000)

        # Auto-load project sonic_bible.json and book_dna.json if available
        if sonic_bible is None and self.project_dir:
            sb_path = self.project_dir / "sonic_bible.json"
            if sb_path.exists():
                try:
                    with open(sb_path, "r", encoding="utf-8") as f:
                        sonic_bible = json.load(f)
                except Exception:
                    pass

        if book_dna is None and self.project_dir:
            dna_path = self.project_dir / "book_dna.json"
            if dna_path.exists():
                try:
                    with open(dna_path, "r", encoding="utf-8") as f:
                        book_dna = json.load(f)
                except Exception:
                    pass

        logger.info(
            f"[*] MultiAgentDirector: Initiating Hollywood Directing Room for {chapter_id} "
            f"({total_segs} segments, {total_duration_sec/60:.1f}m duration)..."
        )

        # ---------------------------------------------------------------------
        # STEP 1: The Showrunner (Macro Arc & Act Partitioning)
        # ---------------------------------------------------------------------
        showrunner_plan = self.showrunner.analyze_chapter(
            chapter_id=chapter_id,
            script_segments=script_segments,
            total_duration_sec=total_duration_sec,
            era=era,
            dramatic_theme=dramatic_theme,
            title=title,
            author=author,
        )

        # ---------------------------------------------------------------------
        # STEP 2: Scenographer (Spatial Room Physics & Convolution IR)
        # ---------------------------------------------------------------------
        scenography_plan = self.scenographer.design_acoustic_spaces(
            showrunner_plan=showrunner_plan,
            era=era,
            title=title,
            author=author,
            sonic_bible=sonic_bible,
            book_dna=book_dna,
        )

        # ---------------------------------------------------------------------
        # STEP 3: Concurrent Execution of Foley, Music, and Wallah Agents
        # ---------------------------------------------------------------------
        logger.info("[*] MultiAgentDirector: Dispatching Foley, Music, and Wallah specialists concurrently across key pool...")

        with ThreadPoolExecutor(max_workers=3) as executor:
            future_foley = executor.submit(
                self.foley_artist.spot_foley_events,
                showrunner_plan=showrunner_plan,
                script_segments=script_segments,
                era=era,
                title=title,
                author=author,
                sonic_bible=sonic_bible,
                book_dna=book_dna,
            )
            future_music = executor.submit(
                self.music_supervisor.score_chapter,
                showrunner_plan=showrunner_plan,
                script_segments=script_segments,
                total_duration_sec=total_duration_sec,
                era=era,
                title=title,
                author=author,
            )
            future_wallah = executor.submit(
                self.wallah_director.direct_world_ambience,
                showrunner_plan=showrunner_plan,
                scenography_plan=scenography_plan,
                script_segments=script_segments,
                seg_starts_ms=seg_starts_ms,
                segment_durations_sec=segment_durations_sec,
                era=era,
                title=title,
                author=author,
            )

            foley_plan = future_foley.result(timeout=300.0)
            music_plan = future_music.result(timeout=300.0)
            wallah_plan = future_wallah.result(timeout=300.0)

        # ---------------------------------------------------------------------
        # STEP 4: Asset Resolution against Sound Bank (44,900+ sounds)
        # ---------------------------------------------------------------------
        logger.info(
            f"[*] MultiAgentDirector: Resolving {len(foley_plan.events)} foley cues, "
            f"{len(music_plan.cues)} music cues, and {len(wallah_plan.act_blueprints)} ambience acts against Sound Bank..."
        )

        resolved_foley = self._resolve_foley_cues(
            foley_plan=foley_plan,
            script_segments=script_segments,
            seg_starts_ms=seg_starts_ms,
            segment_durations_sec=segment_durations_sec,
            franchise_affinity=franchise_affinity,
        )

        resolved_music = self._resolve_music_cues(
            music_plan=music_plan,
            seg_starts_ms=seg_starts_ms,
            total_duration_ms=total_duration_ms,
            franchise_affinity=franchise_affinity,
        )

        resolved_ambience = self._resolve_ambience_scenes(
            showrunner_plan=showrunner_plan,
            scenography_plan=scenography_plan,
            wallah_plan=wallah_plan,
            seg_starts_ms=seg_starts_ms,
            segment_durations_sec=segment_durations_sec,
            total_duration_ms=total_duration_ms,
            franchise_affinity=franchise_affinity,
        )

        # Build Convolution IR Staging map
        acoustic_staging: Dict[str, ConvolutionIRConfig] = {}
        for bp in scenography_plan.blueprints:
            staging_config = ConvolutionIRConfig(
                preset_name=bp.ir_preset,
                wet_dry_ratio=bp.dx_reverb_wet_ratio,
                early_reflections_decay_ms=bp.early_reflections_decay_ms,
                high_cut_hz=bp.high_frequency_damping_hz,
                enabled=True,
            )
            acoustic_staging[f"act_{bp.act_index:03d}"] = staging_config

        # ---------------------------------------------------------------------
        # STEP 5: Silence Verification & Creative Manifest Assembly
        # ---------------------------------------------------------------------
        total_music_ms = sum(c.duration_ms for c in resolved_music)
        calc_silence = max(60.0, 100.0 * (1.0 - (total_music_ms / max(1.0, float(total_duration_ms)))))

        manifest = CreativeManifest(
            manifest_version="3.0",
            chapter_id=chapter_id,
            silence_percentage=round(calc_silence, 2),
            mastering=MasteringConfig(
                target_lufs=-19.0,
                true_peak_dbtp=-1.5,
                ducking_attenuation_db=-16.0,
                ducking_attack_ms=15,
                ducking_release_ms=350,
                ducking_ratio=3.2,
                ducking_knee=2.8,
                spectral_carve_hz=2200,
                spectral_carve_gain_db=-5.5,
            ),
            ambience_scenes=resolved_ambience,
            music_cues=resolved_music,
            foley_cues=resolved_foley,
            acoustic_staging=acoustic_staging,
            wallah_automations=wallah_plan.wallah_automations,
            total_duration_ms=total_duration_ms,
            metadata={
                "director_engine": "MultiAgentDirector v5.0 (Hollywood-Grade)",
                "dramatic_theme": dramatic_theme,
                "era": era,
                "franchise_affinity": franchise_affinity,
                "total_foley_cues": len(resolved_foley),
                "total_music_cues": len(resolved_music),
                "total_ambience_scenes": len(resolved_ambience),
                "acts_count": len(showrunner_plan.acts),
            },
        )

        logger.info(
            f"[+] MultiAgentDirector: Hollywood Creative Manifest directed successfully! "
            f"({len(resolved_foley)} foley cues, {len(resolved_music)} music cues, {len(resolved_ambience)} ambience acts, "
            f"{manifest.silence_percentage}% silence)."
        )
        return manifest

    # -------------------------------------------------------------------------
    # Resolution Helpers
    # -------------------------------------------------------------------------
    @staticmethod
    def _extract_asset_path(raw: Any) -> Optional[Path]:
        """Safely extracts a Path object whether raw is a Path, str, or dict."""
        if not raw:
            return None
        if isinstance(raw, Path):
            return raw
        if isinstance(raw, str):
            return Path(raw)
        if isinstance(raw, dict):
            p_val = raw.get("path") or raw.get("filepath")
            if p_val:
                return Path(p_val)
        return None

    def _resolve_foley_cues(
        self,
        foley_plan: MicroFoleyPlan,
        script_segments: List[Dict[str, Any]],
        seg_starts_ms: Dict[int, int],
        segment_durations_sec: Dict[int, float],
        franchise_affinity: Optional[str] = None,
    ) -> List[FoleyCue]:
        """Resolves foley directives to audio assets in the Sound Bank."""
        seg_by_idx = {s.get("index", i + 1): s for i, s in enumerate(script_segments)}
        resolved: List[FoleyCue] = []

        for idx, event in enumerate(foley_plan.events):
            s_idx = event.segment_index
            seg = seg_by_idx.get(s_idx)
            if not seg:
                continue

            query = f"{event.action_verb} {event.object_material}".strip()
            # If is_micro_foley is True, try FOL first, then SFX
            res = self.sound_bank.resolve_sound(
                query,
                category="FOL" if event.is_micro_foley else "SFX",
                franchise_affinity=franchise_affinity,
            )
            asset_path = self._extract_asset_path(res)

            # Fallback to broader search if exact resolution fails
            if not asset_path:
                res = self.sound_bank.resolve_sound(
                    event.action_verb.replace("_", " "),
                    category="FOL" if event.is_micro_foley else "SFX",
                    franchise_affinity=franchise_affinity,
                )
                asset_path = self._extract_asset_path(res)

            if not asset_path:
                res = self.sound_bank.resolve_sound(
                    event.action_verb.replace("_", " "),
                    category="SFX",
                    franchise_affinity=franchise_affinity,
                )
                asset_path = self._extract_asset_path(res)

            if not asset_path:
                continue

            s_start = seg_starts_ms.get(s_idx, 0)
            dur_ms = int(segment_durations_sec.get(s_idx, 4.0) * 1000)

            # Determine cue placement timing based on beat_timing and trigger_mode
            beat_timing = getattr(event, "beat_timing", "post_speech")
            trigger_mode = getattr(event, "trigger_mode", "implicit_scene_physics")
            rel_pos = getattr(event, "relative_position", 0.5)

            anchor = (event.anchor_word or "").strip()
            text = (seg.get("text") or "").lower()

            if trigger_mode == "explicit_anchor" and anchor and anchor.lower() in text:
                # Explicit anchor aligned to word position in segment text
                char_pos = text.find(anchor.lower())
                ratio = max(0.0, min(1.0, char_pos / max(1, len(text))))
                cue_start_ms = max(0, s_start + int(dur_ms * ratio) - 50)
            elif beat_timing == "pre_speech":
                # Fires right before dialogue line (e.g. setting down drink, chair creak, sharp inhale)
                cue_start_ms = max(0, s_start - 200)
            elif beat_timing == "post_speech":
                # Fires right after speech ends (e.g. taking a drink, sighing, coin drop, sheath click)
                cue_start_ms = max(0, s_start + max(100, dur_ms - 80))
            elif beat_timing == "mid_speech_pause":
                # Fires during mid-sentence pause or hesitation
                pause_ratio = rel_pos
                for punct in ("...", "—", "--", ",", ";", ":", "?", "!"):
                    if punct in text:
                        p_pos = text.find(punct)
                        pause_ratio = max(0.2, min(0.8, p_pos / max(1, len(text))))
                        break
                cue_start_ms = max(0, s_start + int(dur_ms * pause_ratio))
            elif beat_timing == "under_speech":
                # Continuous subtle texture under speech (e.g. gentle hearth crackle, rain, subtle cloth)
                cue_start_ms = max(0, s_start + int(dur_ms * max(0.1, min(0.4, rel_pos))))
            else:
                cue_start_ms = max(0, s_start + int(dur_ms * max(0.0, min(1.0, rel_pos))))

            # Calibrate gain: under_speech must never mask spoken dialogue
            effective_gain = event.gain_dbfs
            if beat_timing == "under_speech":
                effective_gain = min(effective_gain, -22.0)

            cue = FoleyCue(
                cue_id=f"fc_{s_idx:04d}_{idx:03d}",
                segment_index=s_idx,
                anchor_word=anchor or event.action_verb,
                trigger_mode=trigger_mode,
                beat_timing=beat_timing,
                relative_position=rel_pos,
                pre_roll_ms=50,
                asset_id=res.get("id", 0) if isinstance(res, dict) else 0,
                asset_path=str(asset_path).replace("\\", "/"),
                asset_name=asset_path.name,
                gain_dbfs=effective_gain,
                azimuth_pan=event.pan,
                reverb_send=0.15,
                start_ms=cue_start_ms,
                duration_ms=int(event.duration_sec * 1000) if event.duration_sec else 0,
                ucs_category="FOLEMov" if event.is_micro_foley else "MISCGnl",
                is_micro_foley=event.is_micro_foley,
                foley_type="tableware" if any(w in query for w in ("mug", "tankard", "pour", "drink", "cup", "bowl", "fork", "knife")) else (
                    "clothing" if any(w in query for w in ("cloth", "leather", "armor", "cloak", "scabbard")) else (
                        "furniture" if any(w in query for w in ("chair", "stool", "table", "bench", "door")) else "prop"
                    )
                ),
                dramatic_justification=getattr(event, "dramatic_justification", "") or getattr(event, "description", ""),
            )
            resolved.append(cue)

        return resolved

    def _resolve_music_cues(
        self,
        music_plan: MusicScoringPlan,
        seg_starts_ms: Dict[int, int],
        total_duration_ms: int,
        franchise_affinity: Optional[str] = None,
    ) -> List[MusicCue]:
        """Resolves music directives to tracks in the Sound Bank."""
        resolved: List[MusicCue] = []

        for idx, m_dir in enumerate(music_plan.cues):
            s_idx = m_dir.trigger_segment
            s_start = seg_starts_ms.get(s_idx, 0)

            # Query sound bank music library
            query = m_dir.search_query or f"{m_dir.mood} {m_dir.timbre}"
            res = self.sound_bank.resolve_sound(
                query,
                category="MUS",
                franchise_affinity=franchise_affinity,
            )
            asset_path = self._extract_asset_path(res)

            if not asset_path:
                res = self.sound_bank.resolve_sound(
                    m_dir.mood,
                    category="MUS",
                    franchise_affinity=franchise_affinity,
                )
                asset_path = self._extract_asset_path(res)

            if not asset_path:
                continue

            dur_ms = int(m_dir.duration_sec * 1000)
            if s_start + dur_ms > total_duration_ms:
                dur_ms = max(5000, total_duration_ms - s_start)

            # Map LLM cue_type to allowed MusicCueType
            cue_type = m_dir.cue_type
            if cue_type not in (
                "TRANSITION_BRIDGE",
                "EMOTIONAL_UNDERSCORE",
                "TENSION_RISER",
                "CLIMACTIC_ACTION_CUE",
                "AFTERMATH_FADE",
                "DRAMATIC_PUNCTUATION",
                "THEMATIC_MOTIF",
            ):
                if "PUNCTUATION" in cue_type or "STAB" in cue_type:
                    cue_type = "DRAMATIC_PUNCTUATION"
                elif "BRIDGE" in cue_type or "TRANSITION" in cue_type:
                    cue_type = "TRANSITION_BRIDGE"
                elif "ACTION" in cue_type:
                    cue_type = "CLIMACTIC_ACTION_CUE"
                elif "MOTIF" in cue_type or "THEME" in cue_type:
                    cue_type = "THEMATIC_MOTIF"
                else:
                    cue_type = "EMOTIONAL_UNDERSCORE"

            # Dynamic Vocal Protection: Ensure music volume stays at broadcast background bed level
            vol_db = max(-34.0, min(-21.0, float(m_dir.volume_db)))

            cue = MusicCue(
                cue_id=f"mc_{s_idx:04d}_{idx:02d}",
                cue_type=cue_type,
                track_id=res.get("id", 0) if isinstance(res, dict) else 0,
                track_name=str(asset_path).replace("\\", "/"),
                section_name=m_dir.energy_section,
                section_start_sec=0.0,
                start_ms=s_start,
                duration_ms=dur_ms,
                fade_in_ms=int(m_dir.fade_in_sec * 1000),
                fade_out_ms=int(m_dir.fade_out_sec * 1000),
                volume_db=vol_db,
                dramatic_justification=m_dir.dramatic_justification,
                spectral_notch_needed=True,
                narrative_archetype=m_dir.narrative_archetype,
            )
            resolved.append(cue)

        return resolved

    def _resolve_ambience_scenes(
        self,
        showrunner_plan: ShowrunnerPlan,
        scenography_plan: ScenographyPlan,
        wallah_plan: WallahEnvironmentPlan,
        seg_starts_ms: Dict[int, int],
        segment_durations_sec: Dict[int, float],
        total_duration_ms: int,
        franchise_affinity: Optional[str] = None,
    ) -> List[AmbienceScene]:
        """Constructs continuous AmbienceScene objects spanning all acts."""
        resolved: List[AmbienceScene] = []
        blueprints_by_act = {b.act_index: b for b in scenography_plan.blueprints}
        wallah_by_act = {w.act_index: w for w in wallah_plan.act_blueprints}

        for act in showrunner_plan.acts:
            s_start = seg_starts_ms.get(act.start_segment, 0)
            end_dur = int(segment_durations_sec.get(act.end_segment, 4.0) * 1000)
            s_end = seg_starts_ms.get(act.end_segment, s_start) + end_dur

            # If final act, stretch to total chapter duration
            if act.act_index == showrunner_plan.acts[-1].act_index:
                s_end = max(s_end, total_duration_ms)

            bp = blueprints_by_act.get(act.act_index)
            w_env = wallah_by_act.get(act.act_index)

            # Determine optimal search query
            search_q = "room tone"
            if w_env and w_env.layers:
                search_q = w_env.layers[0].search_query
            else:
                search_q = act.environment_type

            res = self.sound_bank.resolve_sound(
                search_q,
                category="AMB",
                franchise_affinity=franchise_affinity,
            )
            asset_path = self._extract_asset_path(res)
            if not asset_path:
                res = self.sound_bank.resolve_sound(
                    act.environment_type,
                    category="AMB",
                    franchise_affinity=franchise_affinity,
                )
                asset_path = self._extract_asset_path(res)

            asset_p = "audiobooks/sound_bank/cache/AMB/07039068.mp3"
            if asset_path:
                asset_p = str(asset_path).replace("\\", "/")

            sc = AmbienceScene(
                scene_id=act.act_index,
                start_ms=s_start,
                end_ms=max(s_start + 1000, s_end),
                asset_path=asset_p,
                target_lufs=-32.0,
                reverb_preset=bp.ir_preset if bp else "room",
                asset_name=Path(asset_p).name,
            )
            resolved.append(sc)

        return resolved
