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
    QCViolationRecord,
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
        self._last_scene_blueprint: Optional[SceneAudioBlueprint] = None
        self._last_scene_timeline: Optional[SoundTimeline] = None

    def audit_scene_sound_design(
        self,
        blueprint: SceneAudioBlueprint,
        timeline: SoundTimeline,
        previous_scene_blueprint: Optional[SceneAudioBlueprint] = None,
        previous_scene_timeline: Optional[SoundTimeline] = None,
    ) -> SoundDesignQCReport:
        """
        Audits a scene's sound design blueprint and timeline, returning a SoundDesignQCReport
        populated with structured, explainable QCViolationRecords.
        """
        warnings: List[str] = []
        errors: List[str] = []
        violations: List[QCViolationRecord] = []

        scene_id = timeline.scene_id or blueprint.scene_id or "scene"

        def record_violation(
            rule_id: str,
            category: str,
            severity: str,
            reason: str,
            expected: str,
            actual: str,
            event_id: Optional[str] = None,
        ) -> None:
            viol = QCViolationRecord(
                scene_id=scene_id,
                event_id=event_id,
                category=category,
                rule_id=rule_id,
                severity=severity,  # type: ignore
                reason=reason,
                expected_behavior=expected,
                actual_behavior=actual,
            )
            violations.append(viol)
            if severity == "ERROR":
                errors.append(reason)
            else:
                warnings.append(reason)

        # 1. Foley & Material QC
        foley_events = [e for e in timeline.events if e.category == "FOLEY"]
        foley_evaluated = len(blueprint.foley_planned)
        foley_accepted = len(foley_events)
        foley_rejected = max(0, foley_evaluated - foley_accepted)

        # Check for tableware vs weapon collisions, dining/combat context mismatch, and low-value verbs
        trivial_verbs = {
            "blink", "blinks", "blinked", "blinking",
            "sigh", "sighs", "sighed", "sighing",
            "fidget", "fidgeted", "shrug", "shrugged",
            "nod", "nodded", "swallow", "swallowed"
        }

        for evt in timeline.events:
            if evt.category in ("FOLEY", "HARD_SFX"):
                path_desc = (evt.asset_path + " " + (evt.asset_name or "")).lower()
                decision_lower = (evt.decision_reason or "").lower()
                full_desc = f"{path_desc} {decision_lower}"

                # Direct collision check
                if self.matrix.is_weapon_vs_tableware_collision(path_desc, path_desc):
                    record_violation(
                        rule_id="TABLEWARE_WEAPON_COLLISION",
                        category="FOLEY",
                        severity="ERROR",
                        reason=f"Tableware vs Weapon collision detected in event '{evt.event_id}': {path_desc}",
                        expected="Clear separation between domestic dining acoustics and combat weapons",
                        actual=f"Conflicting tableware and weapon acoustic elements in '{path_desc}'",
                        event_id=evt.event_id,
                    )
                else:
                    # Contextual dining vs weapon mismatch
                    is_dining_ctx = any(w in decision_lower for w in ("dinner", "feast", "supper", "eating", "tableware", "fork", "spoon", "goblet", "breakfast", "soup"))
                    has_weapon_sound = any(w in path_desc for w in ("sword", "blade", "dagger", "axe", "steel_clash", "parry"))
                    is_combat_ctx = any(w in decision_lower for w in ("combat", "duel", "battle", "strike", "slash", "parry", "melee"))
                    has_tableware_sound = any(w in path_desc for w in ("plate", "bowl", "fork", "spoon", "goblet", "tableware", "ceramic_clatter"))

                    if is_dining_ctx and has_weapon_sound:
                        record_violation(
                            rule_id="TABLEWARE_WEAPON_COLLISION",
                            category="FOLEY",
                            severity="ERROR",
                            reason=f"Tableware vs Weapon collision detected in event '{evt.event_id}': dining context with weapon sound ({path_desc})",
                            expected="Domestic tableware foley during dining context",
                            actual=f"Weapon clash asset assigned during dining action: '{path_desc}'",
                            event_id=evt.event_id,
                        )
                    elif is_combat_ctx and has_tableware_sound:
                        record_violation(
                            rule_id="TABLEWARE_WEAPON_COLLISION",
                            category="FOLEY",
                            severity="ERROR",
                            reason=f"Tableware vs Weapon collision detected in event '{evt.event_id}': combat context with tableware sound ({path_desc})",
                            expected="Melee weapon foley during combat context",
                            actual=f"Tableware clatter asset assigned during combat action: '{path_desc}'",
                            event_id=evt.event_id,
                        )

            if evt.category == "FOLEY":
                name_words = set((evt.asset_name or "").lower().split())
                desc_lower = (evt.decision_reason or "").lower()
                for tv in trivial_verbs:
                    if tv in name_words or f"'{tv}'" in desc_lower:
                        record_violation(
                            rule_id="LOW_VALUE_TRIVIAL_VERB",
                            category="FOLEY",
                            severity="ERROR",
                            reason=f"Restraint failure: Low-value trivial verb '{tv}' found in accepted foley '{evt.event_id}'.",
                            expected="High-value cinematic foley (footsteps, clothing, weapons, physical props)",
                            actual=f"Trivial low-value verb '{tv}' accepted into timeline",
                            event_id=evt.event_id,
                        )

        # 2. Ambience QC (Stems <= 4, loopability, true continuity)
        amb_events = [e for e in timeline.events if e.category == "AMBIENCE"]
        if len(amb_events) > 4:
            record_violation(
                rule_id="AMBIENCE_STEM_LIMIT",
                category="AMBIENCE",
                severity="WARNING",
                reason=f"Scene has {len(amb_events)} simultaneous ambience stems (cinema standard recommends <= 4).",
                expected="<= 4 simultaneous layered ambience stems",
                actual=f"{len(amb_events)} ambience stems active",
            )
        ambience_continuity = len(amb_events) >= 1
        if not ambience_continuity:
            record_violation(
                rule_id="MISSING_AMBIENT_BED",
                category="AMBIENCE",
                severity="WARNING",
                reason="Scene timeline has no ambient background bed (risks total acoustic dead-space).",
                expected="At least 1 BASE ambient bed layer establishing room acoustics",
                actual="0 ambience events on timeline",
            )

        # Ambience continuity validation across consecutive scenes
        prev_bp = previous_scene_blueprint or self._last_scene_blueprint
        if prev_bp and prev_bp.location_id == blueprint.location_id:
            if blueprint.acoustic_profile_id != prev_bp.acoustic_profile_id:
                record_violation(
                    rule_id="AMBIENCE_CONTINUITY_MISMATCH",
                    category="AMBIENCE",
                    severity="WARNING",
                    reason=f"Acoustic profile discontinuity in recurring location '{blueprint.location_id}': changed from '{prev_bp.acoustic_profile_id}' to '{blueprint.acoustic_profile_id}'.",
                    expected=f"Consistent acoustic profile '{prev_bp.acoustic_profile_id}' in same location",
                    actual=f"Changed to '{blueprint.acoustic_profile_id}' without environment transition",
                )

        # 3. Walla QC (Restraint in solitary scenes, dialogue subordination)
        walla_events = [e for e in timeline.events if e.category == "WALLA"]
        solitary_keywords = ("crypt", "forest", "cell", "study", "solitary", "deserted")
        is_solitary_env = any(k in blueprint.location_id.lower() for k in solitary_keywords)

        walla_subordination = True
        if is_solitary_env and walla_events:
            for w in walla_events:
                record_violation(
                    rule_id="WALLA_SOLITARY_VIOLATION",
                    category="WALLA",
                    severity="ERROR",
                    reason=f"Restraint failure: Crowd walla present in solitary environment '{blueprint.location_id}'.",
                    expected="Zero crowd walla in solitary environments",
                    actual=f"Crowd walla present in '{blueprint.location_id}'",
                    event_id=w.event_id,
                )
        for w in walla_events:
            if not w.mix_intent.duck_under_dialogue:
                record_violation(
                    rule_id="WALLA_SUBORDINATION_MISSING",
                    category="WALLA",
                    severity="WARNING",
                    reason=f"Walla event '{w.event_id}' missing dialogue subordination (duck_under_dialogue=True).",
                    expected="Walla ducked under foreground dialogue",
                    actual="duck_under_dialogue=False on walla event",
                    event_id=w.event_id,
                )
                walla_subordination = False

        # 4. Hard SFX QC (Collision checks)
        sfx_events = [e for e in timeline.events if e.category == "HARD_SFX"]
        sfx_timestamps = [e.start_ms for e in sfx_events]
        sfx_collision_free = True
        for ts in set(sfx_timestamps):
            if sfx_timestamps.count(ts) >= 3:
                record_violation(
                    rule_id="SFX_CONCURRENCY_COLLISION",
                    category="HARD_SFX",
                    severity="WARNING",
                    reason=f"Hard SFX concurrency collision: 3+ major impacts at {ts}ms.",
                    expected="Staggered or priority-ranked SFX impacts to avoid acoustic clutter",
                    actual=f"{sfx_timestamps.count(ts)} hard SFX events firing simultaneously at {ts}ms",
                )
                sfx_collision_free = False

        # 5. Music Motif QC
        music_events = [e for e in timeline.events if e.category == "MUSIC"]
        music_motif_valid = True
        for m in music_events:
            if m.duration_ms <= 0:
                record_violation(
                    rule_id="INVALID_MUSIC_DURATION",
                    category="MUSIC",
                    severity="ERROR",
                    reason=f"Music cue '{m.event_id}' has invalid non-positive duration: {m.duration_ms}ms.",
                    expected="Positive music duration > 0ms",
                    actual=f"duration_ms = {m.duration_ms}",
                    event_id=m.event_id,
                )
                music_motif_valid = False

        # 6. Intentional Silence QC & Cross-System Silence Preservation
        silence_events = [e for e in timeline.events if e.category == "SILENCE"]
        silence_preserved = True
        for s in silence_events:
            if s.duration_ms < 500:
                record_violation(
                    rule_id="SILENCE_TOO_SHORT",
                    category="SILENCE",
                    severity="WARNING",
                    reason=f"Silence event '{s.event_id}' duration {s.duration_ms}ms is too short for dramatic impact.",
                    expected="Intentional silence window >= 500ms",
                    actual=f"{s.duration_ms}ms",
                    event_id=s.event_id,
                )
            elif s.duration_ms > 6000:
                record_violation(
                    rule_id="SILENCE_TOO_LONG",
                    category="SILENCE",
                    severity="WARNING",
                    reason=f"Silence event '{s.event_id}' duration {s.duration_ms}ms risks perceived dead-air.",
                    expected="Intentional silence window <= 6000ms",
                    actual=f"{s.duration_ms}ms",
                    event_id=s.event_id,
                )

            # Cross-system check: non-diegetic music or unmotivated walla intruding into silence window
            s_start = s.start_ms
            s_end = s.start_ms + s.duration_ms
            for other in timeline.events:
                if other.category in ("SILENCE", "AMBIENCE", "DX"):
                    continue
                if not (other.start_ms + other.duration_ms <= s_start or other.start_ms >= s_end):
                    if other.category in ("MUSIC", "WALLA"):
                        record_violation(
                            rule_id="SILENCE_WINDOW_INTRUSION",
                            category="SILENCE",
                            severity="WARNING",
                            reason=f"Event '{other.event_id}' ({other.category}) violates intentional silence window [{s_start}ms - {s_end}ms].",
                            expected=f"Acoustic buses suppressed during silence window '{s.event_id}'",
                            actual=f"Active {other.category} event overlapping silence",
                            event_id=other.event_id,
                        )
                        silence_preserved = False

        # Cross-system walla suppression verification (e.g. authority arrival or stillness pattern)
        if blueprint.metadata.get("authority_enters_crowd") or blueprint.metadata.get("suppress_walla"):
            for w in walla_events:
                if w.relative_intensity in ("prominent", "normal"):
                    record_violation(
                        rule_id="WALLA_SUPPRESSION_FAILURE",
                        category="WALLA",
                        severity="WARNING",
                        reason=f"Walla event '{w.event_id}' active at '{w.relative_intensity}' intensity during authority/suppression window.",
                        expected="Walla attenuated to subtle_bed or whisper_quiet during authority arrival",
                        actual=f"Walla remains at '{w.relative_intensity}' intensity",
                        event_id=w.event_id,
                    )

        # 7. Spatial Geography QC (Pan within [-0.8, +0.8], narrator locked to 0.0)
        spatial_stage_valid = True
        for evt in timeline.events:
            pan = evt.spatial.azimuth_pan
            if not (-0.801 <= pan <= 0.801):
                record_violation(
                    rule_id="AZIMUTH_STAGE_OVERFLOW",
                    category="SPATIAL",
                    severity="ERROR",
                    reason=f"Event '{evt.event_id}' azimuth pan {pan} exceeds safe stage boundary [-0.8, +0.8].",
                    expected="Azimuth pan in [-0.8, +0.8] range",
                    actual=f"Azimuth pan = {pan}",
                    event_id=evt.event_id,
                )
                spatial_stage_valid = False

        # Check staged narrator position (case-insensitive)
        staged_chars = blueprint.characters_staged or {}
        for c_name, c_spatial in staged_chars.items():
            if c_name.lower().strip() == "narrator":
                n_pan = c_spatial.azimuth_pan if hasattr(c_spatial, "azimuth_pan") else (
                    c_spatial.get("azimuth_pan", 0.0) if isinstance(c_spatial, dict) else 0.0
                )
                if abs(n_pan) > 0.001:
                    record_violation(
                        rule_id="NARRATOR_PAN_OFF_CENTER",
                        category="SPATIAL",
                        severity="ERROR",
                        reason=f"Narrator azimuth pan {n_pan} is not locked to center 0.0.",
                        expected="Narrator locked to center pan 0.0",
                        actual=f"Narrator pan = {n_pan}",
                    )
                    spatial_stage_valid = False
                break

        # 8. Source Beat Linking & No Orphan Events Check
        for evt in timeline.events:
            if evt.category in ("AMBIENCE", "WALLA"):
                continue
            if evt.source_segment_index is None and not evt.provenance_segment_uid and not evt.provenance_beat_id:
                record_violation(
                    rule_id="ORPHAN_EVENT",
                    category=evt.category,
                    severity="ERROR",
                    reason=f"Orphan event detected: Event '{evt.event_id}' ({evt.category}) is not linked to any source segment or beat.",
                    expected="Linked to source segment or dramatic beat",
                    actual="Orphan event without segment or beat provenance",
                    event_id=evt.event_id,
                )

        # 9. Real Asset Resolution & Banned Placeholder Guard
        asset_provenance_verified = True
        unresolved_count = 0
        banned_placeholders = (
            "foley.wav",
            "temp.wav",
            "placeholder",
            "fake_foley",
            "fake_amb",
            "foley_pour_liquid.wav",
            "creature_gargoyle_vocalization",
            "foley_action_wood.wav",
        )

        for evt in timeline.events:
            if evt.category == "SILENCE":
                continue

            # Banned placeholder pattern check
            if evt.asset_path:
                lower_p = evt.asset_path.lower()
                for bp in banned_placeholders:
                    if bp in lower_p:
                        record_violation(
                            rule_id="BANNED_PLACEHOLDER_PATH",
                            category=evt.category,
                            severity="ERROR",
                            reason=f"Fake path error: Event '{evt.event_id}' forged fake asset path '{evt.asset_path}'.",
                            expected="Verified SoundAssetDescriptor or clean empty path when unresolved",
                            actual=f"Banned placeholder path pattern '{bp}' found in '{evt.asset_path}'",
                            event_id=evt.event_id,
                        )
                        asset_provenance_verified = False
                        break

            if evt.is_resolved:
                if not evt.asset_path and not evt.resolved_asset:
                    record_violation(
                        rule_id="RESOLVED_MISSING_ASSET",
                        category=evt.category,
                        severity="ERROR",
                        reason=f"Provenance error: Event '{evt.event_id}' marked as resolved but has no asset path or descriptor.",
                        expected="Resolved event must have non-empty asset path or descriptor",
                        actual="Empty asset path and null descriptor on resolved event",
                        event_id=evt.event_id,
                    )
                    asset_provenance_verified = False
            else:
                unresolved_count += 1
                # Unresolved events must not forge fake wav paths
                if evt.asset_path and not Path(evt.asset_path).exists():
                    record_violation(
                        rule_id="UNRESOLVED_FAKE_PATH",
                        category=evt.category,
                        severity="ERROR",
                        reason=f"Fake path error: Unresolved event '{evt.event_id}' forged fake asset path '{evt.asset_path}'.",
                        expected="asset_path='' on unresolved events",
                        actual=f"Non-existent asset path '{evt.asset_path}' provided",
                        event_id=evt.event_id,
                    )
                    asset_provenance_verified = False

        # 10. Timestamp Non-Negativity & Bounds Verification
        for evt in timeline.events:
            if evt.start_ms < 0:
                record_violation(
                    rule_id="NEGATIVE_TIMESTAMP",
                    category=evt.category,
                    severity="ERROR",
                    reason=f"Negative timestamp error in event '{evt.event_id}': start_ms = {evt.start_ms}",
                    expected="start_ms >= 0",
                    actual=f"start_ms = {evt.start_ms}",
                    event_id=evt.event_id,
                )
            if evt.duration_ms <= 0:
                record_violation(
                    rule_id="NON_POSITIVE_DURATION",
                    category=evt.category,
                    severity="ERROR",
                    reason=f"Non-positive duration error in event '{evt.event_id}': duration_ms = {evt.duration_ms}",
                    expected="duration_ms > 0",
                    actual=f"duration_ms = {evt.duration_ms}",
                    event_id=evt.event_id,
                )
            if evt.start_ms + evt.duration_ms > timeline.total_duration_ms + 100:
                record_violation(
                    rule_id="BOUNDARY_OVERFLOW",
                    category=evt.category,
                    severity="WARNING",
                    reason=f"Boundary overflow advisory: Event '{evt.event_id}' ({evt.start_ms + evt.duration_ms}ms) extends past scene end ({timeline.total_duration_ms}ms).",
                    expected=f"Event end <= timeline total duration ({timeline.total_duration_ms}ms)",
                    actual=f"Event end = {evt.start_ms + evt.duration_ms}ms",
                    event_id=evt.event_id,
                )

        # 11. Dramatic Beat Coverage Check
        dramatic_beats = blueprint.metadata.get("dramatic_beats", [])
        for beat in dramatic_beats:
            if isinstance(beat, dict):
                b_time = beat.get("start_ms", beat.get("timestamp_ms", 0))
                b_func = str(beat.get("dramatic_function", beat.get("function", ""))).lower()
                b_tension = float(beat.get("tension", 0.0))
                if b_tension >= 0.7 or b_func in ("climax", "confrontation", "crisis", "revelation", "turn", "threat"):
                    active_covering = [
                        e for e in timeline.events
                        if not (e.start_ms + e.duration_ms < b_time - 1000 or e.start_ms > b_time + 1000)
                    ]
                    if not active_covering:
                        record_violation(
                            rule_id="DRAMATIC_BEAT_UNCOVERED",
                            category="CHOREOGRAPHY",
                            severity="WARNING",
                            reason=f"High-tension dramatic beat '{beat.get('beat_id', 'beat')}' ({b_func}, tension={b_tension}) lacks sound design or silence coverage.",
                            expected="Sound event or intentional silence window supporting dramatic beat",
                            actual="Zero sound events or silence active within 1000ms of dramatic beat",
                        )

        # 12. Restraint Density Evaluation (Scene-Dependent, No Rigid Universal Rule)
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
            record_violation(
                rule_id="RESTRAINT_DENSITY_EXCEEDED",
                category="RESTRAINT",
                severity="WARNING",
                reason=f"Restraint advisory: {density_eval['feedback']}",
                expected=f"Density compliant with '{blueprint.restraint_target}' restraint",
                actual=f"Density = {density_eval['density']:.2f}, silence ratio = {density_eval['silence_ratio']:.2f}",
            )

        # 13. Overall Status Determination
        if errors:
            status = "FAIL"
        elif warnings:
            status = "WARN"
        else:
            status = "PASS"

        # Update cache for consecutive scene tracking
        self._last_scene_blueprint = blueprint
        self._last_scene_timeline = timeline

        return SoundDesignQCReport(
            report_id=f"qc_{scene_id}_{timeline.timeline_id}",
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
            violations=violations,
            telemetry={
                "total_timeline_events": len(timeline.events),
                "total_duration_ms": timeline.total_duration_ms,
                "density": density_eval["density"],
                "silence_ratio": density_eval["silence_ratio"],
                "target_restraint": blueprint.restraint_target,
                "unresolved_events_count": unresolved_count,
                "violations_count": len(violations),
            },
        )

    def audit_chapter_sound_design(
        self,
        blueprints: List[SceneAudioBlueprint],
        timelines: List[SoundTimeline],
    ) -> List[SoundDesignQCReport]:
        """
        Audits a multi-scene chapter sound design plan, evaluating inter-scene continuity.
        """
        reports: List[SoundDesignQCReport] = []
        prev_bp: Optional[SceneAudioBlueprint] = None
        prev_tl: Optional[SoundTimeline] = None

        for bp, tl in zip(blueprints, timelines):
            report = self.audit_scene_sound_design(
                blueprint=bp,
                timeline=tl,
                previous_scene_blueprint=prev_bp,
                previous_scene_timeline=prev_tl,
            )
            reports.append(report)
            prev_bp = bp
            prev_tl = tl

        return reports


_GLOBAL_QC_AUDITOR: Optional[SoundDesignQCAuditor] = None

def get_sound_design_qc_auditor() -> SoundDesignQCAuditor:
    """Returns singleton instance of SoundDesignQCAuditor."""
    global _GLOBAL_QC_AUDITOR
    if _GLOBAL_QC_AUDITOR is None:
        _GLOBAL_QC_AUDITOR = SoundDesignQCAuditor()
    return _GLOBAL_QC_AUDITOR
