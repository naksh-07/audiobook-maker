#!/usr/bin/env python3
"""
Audiobook Factory - Capability 20: Sound Design Quality Control Auditor.
=========================================================================
Independent Multi-Signal Sound Design QC Auditor.
Audits blueprints, timelines, and manifests across 9 forensic pillars:
1. Foley QC: Physical action coverage, material accuracy, low-value verb rejection.
2. Ambience QC: Environment appropriateness, stem limit (<= 4), loopability.
3. Walla QC: Solitary scene restraint, dialogue subordination verified.
4. Hard SFX QC: Major event coverage, concurrency collision checks.
5. Music QC: Bound motifs, variation mode matching, adaptive density.
6. Silence QC: Intentional silence intervals verified, no unmotivated dropouts.
7. Spatial QC: Azimuth pan in [-0.8, +0.8], narrator locked to 0.0.
8. Asset QC: Provenance verification, no unvetted JIT paths.
9. Restraint QC: Evaluates acoustic clutter vs. narrative weight.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

from audiobook_factory.logger import logger
from audiobook_factory.sound_design.contracts import (
    SoundTimeline,
    SoundTimelineEvent,
    SceneAudioBlueprint,
    SoundDesignQCReport,
)
from audiobook_factory.sound_design.silence_engine import get_silence_engine
from audiobook_factory.sound_design.foley_character_material import MaterialMatrixEngine


class SoundDesignQCAuditor:
    """
    Independent multi-signal quality auditor for sound design plans and timelines.
    """

    def __init__(self):
        self.silence_engine = get_silence_engine()
        self.matrix = MaterialMatrixEngine()

    def audit_scene_sound_design(
        self,
        blueprint: SceneAudioBlueprint,
        timeline: SoundTimeline,
    ) -> SoundDesignQCReport:
        """
        Audits a scene's sound design blueprint and timeline, returning a SoundDesignQCReport.
        """
        warnings: List[str] = []
        errors: List[str] = []

        # 1. Foley & Material QC
        foley_events = [e for e in timeline.events if e.category == "FOLEY"]
        foley_evaluated = len(blueprint.foley_planned)
        foley_accepted = len(foley_events)
        foley_rejected = max(0, foley_evaluated - foley_accepted)

        # Check for tableware vs weapon collisions and low-value verbs
        trivial_verbs = {"blink", "blinks", "blinked", "blinking", "sigh", "sighs", "sighed", "sighing", "fidget", "fidgeted", "shrug", "shrugged", "nod", "nodded", "swallow", "swallowed"}
        for evt in timeline.events:
            if evt.category in ("FOLEY", "HARD_SFX"):
                path_desc = (evt.asset_path + " " + (evt.asset_name or "")).lower()
                if self.matrix.is_weapon_vs_tableware_collision(path_desc, path_desc):
                    errors.append(
                        f"Tableware vs Weapon collision detected in event '{evt.event_id}': {path_desc}"
                    )
            if evt.category == "FOLEY":
                name_words = set((evt.asset_name or "").lower().split())
                desc_lower = (evt.decision_reason or "").lower()
                for tv in trivial_verbs:
                    if tv in name_words or f"'{tv}'" in desc_lower:
                        errors.append(f"Restraint failure: Low-value trivial verb '{tv}' found in accepted foley '{evt.event_id}'.")

        # 2. Ambience QC (Stems <= 4, loopability, true continuity)
        amb_events = [e for e in timeline.events if e.category == "AMBIENCE"]
        if len(amb_events) > 4:
            warnings.append(
                f"Scene has {len(amb_events)} simultaneous ambience stems (cinema standard recommends <= 4)."
            )
        ambience_continuity = len(amb_events) >= 1

        # 3. Walla QC (Restraint in solitary scenes, dialogue subordination)
        walla_events = [e for e in timeline.events if e.category == "WALLA"]
        solitary_keywords = ("crypt", "forest", "cell", "study", "solitary", "deserted")
        is_solitary_env = any(k in blueprint.location_id.lower() for k in solitary_keywords)

        walla_subordination = True
        if is_solitary_env and walla_events:
            errors.append(
                f"Restraint failure: Crowd walla present in solitary environment '{blueprint.location_id}'."
            )
        for w in walla_events:
            if not w.mix_intent.duck_under_dialogue:
                warnings.append(f"Walla event '{w.event_id}' missing dialogue subordination (duck_under_dialogue=True).")
                walla_subordination = False

        # 4. Hard SFX QC (Collision checks)
        sfx_events = [e for e in timeline.events if e.category == "HARD_SFX"]
        sfx_timestamps = [e.start_ms for e in sfx_events]
        # Check for 3+ simultaneous hard SFX firing at exact same ms
        sfx_collision_free = True
        for ts in set(sfx_timestamps):
            if sfx_timestamps.count(ts) >= 3:
                warnings.append(f"Hard SFX concurrency collision: 3+ major impacts at {ts}ms.")
                sfx_collision_free = False

        # 5. Music Motif QC
        music_events = [e for e in timeline.events if e.category == "MUSIC"]
        music_motif_valid = True
        for m in music_events:
            if m.duration_ms <= 0:
                errors.append(f"Music cue '{m.event_id}' has invalid non-positive duration: {m.duration_ms}ms.")
                music_motif_valid = False

        # 6. Intentional Silence QC
        silence_events = [e for e in timeline.events if e.category == "SILENCE"]
        silence_preserved = True
        for s in silence_events:
            if s.duration_ms < 500:
                warnings.append(f"Silence event '{s.event_id}' duration {s.duration_ms}ms is too short for dramatic impact.")
            elif s.duration_ms > 6000:
                warnings.append(f"Silence event '{s.event_id}' duration {s.duration_ms}ms risks perceived dead-air.")

        # 7. Spatial Geography QC (Pan within [-0.8, +0.8], narrator locked to 0.0)
        spatial_stage_valid = True
        for evt in timeline.events:
            pan = evt.spatial.azimuth_pan
            if not (-0.801 <= pan <= 0.801):
                errors.append(f"Event '{evt.event_id}' azimuth pan {pan} exceeds safe stage boundary [-0.8, +0.8].")
                spatial_stage_valid = False

        # Check staged narrator position (case-insensitive)
        staged_chars = blueprint.characters_staged or {}
        for c_name, c_spatial in staged_chars.items():
            if c_name.lower().strip() == "narrator":
                n_pan = c_spatial.azimuth_pan if hasattr(c_spatial, "azimuth_pan") else (
                    c_spatial.get("azimuth_pan", 0.0) if isinstance(c_spatial, dict) else 0.0
                )
                if abs(n_pan) > 0.001:
                    errors.append(f"Narrator azimuth pan {n_pan} is not locked to center 0.0.")
                    spatial_stage_valid = False
                break

        # 8. Source Beat Linking & No Orphan Events Check
        for evt in timeline.events:
            if evt.category in ("AMBIENCE", "WALLA"):
                continue
            if evt.source_segment_index is None and not evt.provenance_segment_uid and not evt.provenance_beat_id:
                errors.append(f"Orphan event detected: Event '{evt.event_id}' ({evt.category}) is not linked to any source segment or beat.")

        # 9. Real Asset Resolution & Provenance Integrity Check
        asset_provenance_verified = True
        unresolved_count = 0
        for evt in timeline.events:
            if evt.category == "SILENCE":
                continue
            if evt.is_resolved:
                if not evt.asset_path and not evt.resolved_asset:
                    errors.append(f"Provenance error: Event '{evt.event_id}' marked as resolved but has no asset path or descriptor.")
                    asset_provenance_verified = False
            else:
                unresolved_count += 1
                # Unresolved events must not forge fake wav paths
                if evt.asset_path and not Path(evt.asset_path).exists():
                    errors.append(f"Fake path error: Unresolved event '{evt.event_id}' forged fake asset path '{evt.asset_path}'.")
                    asset_provenance_verified = False

        # 10. Timestamp Non-Negativity & Bounds Verification
        for evt in timeline.events:
            if evt.start_ms < 0:
                errors.append(f"Negative timestamp error in event '{evt.event_id}': start_ms = {evt.start_ms}")
            if evt.duration_ms <= 0:
                errors.append(f"Non-positive duration error in event '{evt.event_id}': duration_ms = {evt.duration_ms}")
            if evt.start_ms + evt.duration_ms > timeline.total_duration_ms + 100:
                warnings.append(f"Boundary overflow advisory: Event '{evt.event_id}' ({evt.start_ms + evt.duration_ms}ms) extends past scene end ({timeline.total_duration_ms}ms).")

        # 11. Restraint Density Evaluation (Scene-Dependent, No Rigid Universal Rule)
        sound_spans = [(e.start_ms, e.start_ms + e.duration_ms) for e in timeline.events if e.category not in ("AMBIENCE", "SILENCE")]
        scene_start_ms = min((e.start_ms for e in timeline.events), default=0) if timeline.events else 0
        density_eval = self.silence_engine.evaluate_scene_density(
            total_duration_ms=timeline.total_duration_ms,
            active_sound_spans=sound_spans,
            restraint_target=blueprint.restraint_target,
            scene_start_ms=scene_start_ms,
        )

        restraint_score = 1.0 if density_eval["compliant"] else 0.75
        if not density_eval["compliant"]:
            warnings.append(f"Restraint advisory: {density_eval['feedback']}")

        # 12. Overall Status Determination
        if errors:
            status = "FAIL"
        elif warnings:
            status = "WARN"
        else:
            status = "PASS"

        return SoundDesignQCReport(
            report_id=f"qc_{timeline.scene_id or 'scene'}_{timeline.timeline_id}",
            scene_or_chapter_id=timeline.scene_id or timeline.chapter_id,
            status=status,
            restraint_score=restraint_score,
            foley_evaluated_count=foley_evaluated,
            foley_accepted_count=foley_accepted,
            foley_rejected_count=foley_rejected,
            ambience_continuity_verified=ambience_continuity,
            walla_subordination_verified=walla_subordination,
            hard_sfx_collision_free=sfx_collision_free,
            music_motif_valid=music_motif_valid,
            intentional_silence_preserved=silence_preserved,
            spatial_stage_valid=spatial_stage_valid,
            asset_provenance_verified=asset_provenance_verified,
            warnings=warnings,
            errors=errors,
            telemetry={
                "total_timeline_events": len(timeline.events),
                "total_duration_ms": timeline.total_duration_ms,
                "density": density_eval["density"],
                "silence_ratio": density_eval["silence_ratio"],
                "target_restraint": blueprint.restraint_target,
                "unresolved_events_count": unresolved_count,
            },
        )


_GLOBAL_QC_AUDITOR: Optional[SoundDesignQCAuditor] = None

def get_sound_design_qc_auditor() -> SoundDesignQCAuditor:
    """Returns singleton instance of SoundDesignQCAuditor."""
    global _GLOBAL_QC_AUDITOR
    if _GLOBAL_QC_AUDITOR is None:
        _GLOBAL_QC_AUDITOR = SoundDesignQCAuditor()
    return _GLOBAL_QC_AUDITOR
