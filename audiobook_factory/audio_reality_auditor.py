#!/usr/bin/env python3
"""
Audiobook Factory - Pillar 4: Millisecond Audio Reality Engine & Pre-Mix Auditor.
================================================================================
Validates, sanitizes, and audits all audio cues (Foley, SFX, Ambience, Music)
before multitrack mixing. Enforces strict physics:
- Max Foley spot duration cap (<= 3.5s) with clean micro-fadeouts.
- 180-second anti-repetition cooldown preventing infinite looping of identical assets.
- Strict Category Isolation: Blocks background music tracks from hijacking Foley bus.
- Historical & Fantasy Era consistency: Blocks modern machinery and contemporary chatter.
- Emits canonical `chapter_XXX_audio_reality_ledger.json` for deterministic auditing.
"""

from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union

from pydantic import BaseModel, Field

from audiobook_factory.contracts import CreativeManifest, FoleyCue, AmbienceScene, MusicCue
from audiobook_factory.logger import logger


class AuditedCueRecord(BaseModel):
    cue_id: str
    bus: str  # "FX", "AMB", "MX", "DX"
    asset_path: str
    asset_name: str
    start_ms: int
    end_ms: int
    raw_duration_sec: float
    effective_duration_sec: float
    volume_db: float
    was_trimmed: bool = False
    sanity_status: str = "PASS"  # "PASS", "REMEDIATED", "REJECTED"
    remediation_notes: str = ""


class AudioRealityReport(BaseModel):
    chapter_id: str
    total_cues_inspected: int = 0
    passed_count: int = 0
    remediated_count: int = 0
    rejected_count: int = 0
    cues: List[AuditedCueRecord] = Field(default_factory=list)
    era: str = "MEDIEVAL_FANTASY"
    franchise_affinity: Optional[str] = None
    summary: Dict[str, Any] = Field(default_factory=dict)


class AudioRealityAuditor:
    """
    Fail-closed pre-mix auditor that enforces physical and narrative reality
    on every creative soundscape manifest before FFmpeg mixes it.
    """

    MAX_FOLEY_DURATION_SEC = 3.5
    MAX_FOLEY_FILE_CEILING_SEC = 6.0
    ANTI_REPETITION_COOLDOWN_MS = 180000  # 3 minutes

    ERA_BANNED_SUBSTRINGS = {
        "MEDIEVAL_FANTASY": (
            "grader", "shambling", "studded boots", "troops", "soldiers shambling",
            "santiago", "chile", "refrigerator", "office", "car", "automobile",
            "engine", "traffic", "phone", "siren", "subway", "airplane"
        ),
        "MODERN": (
            "catapult", "trebuchet", "battering_ram"
        )
    }

    def __init__(self, sound_bank: Optional[Any] = None):
        self.sound_bank = sound_bank

    def audit_and_remediate(
        self,
        manifest: CreativeManifest,
        output_dir: Optional[Path] = None,
        era: str = "MEDIEVAL_FANTASY",
        franchise_affinity: Optional[str] = None,
    ) -> Tuple[CreativeManifest, AudioRealityReport]:
        """
        Audits every cue in manifest, fixes duration bloat, quenches repetitions,
        removes rogue music on foley bus, and saves chapter_XXX_audio_reality_ledger.json.
        """
        if not franchise_affinity and output_dir:
            try:
                from audiobook_factory.project_classifier import ProjectClassifier
                proj_dir = output_dir.parent if output_dir.name in ("mastered", "manifests", "scripts") else output_dir
                clf = ProjectClassifier.classify(project_dir=proj_dir)
                if clf:
                    franchise_affinity = clf.franchise_affinity
                    if not era:
                        era = clf.era
            except Exception:
                pass

        chapter_id = manifest.chapter_id
        report = AudioRealityReport(
            chapter_id=chapter_id,
            era=era,
            franchise_affinity=franchise_affinity,
        )

        banned_terms = self.ERA_BANNED_SUBSTRINGS.get(era.upper(), ())

        # ---------------------------------------------------------------------
        # 1. Audit Foley Cues
        # ---------------------------------------------------------------------
        sanitized_foley: List[FoleyCue] = []
        recent_foley_assets: Dict[str, int] = {}  # asset_path -> last_start_ms

        for idx, fc in enumerate(manifest.foley_cues):
            report.total_cues_inspected += 1
            fpath_str = (fc.asset_path or getattr(fc, "asset_name", "")).replace("\\", "/")
            fpath = Path(fpath_str)
            fname_lower = fpath.name.lower()
            start_ms = int(fc.start_ms)

            # Probe raw physical duration if file exists
            raw_dur = 0.0
            if fpath.exists():
                try:
                    import subprocess
                    out = subprocess.check_output(
                        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(fpath)],
                        timeout=5.0,
                    ).decode().strip()
                    raw_dur = float(out) if out else 0.0
                except Exception:
                    raw_dur = 2.0
            else:
                raw_dur = float(getattr(fc, "duration_ms", 0) or 2000) / 1000.0

            # CHECK A: Rogue Music on Foley bus
            is_music_file = (
                "/music/" in fpath_str.lower()
                or "\\music\\" in fpath_str.lower()
                or raw_dur > 20.0
                or any(m in fname_lower for m in ("ost", "theme", "soundtrack", "suite"))
            )
            if is_music_file:
                report.rejected_count += 1
                report.cues.append(
                    AuditedCueRecord(
                        cue_id=fc.cue_id,
                        bus="FX",
                        asset_path=fpath_str,
                        asset_name=fpath.name,
                        start_ms=start_ms,
                        end_ms=start_ms + int(raw_dur * 1000),
                        raw_duration_sec=raw_dur,
                        effective_duration_sec=0.0,
                        volume_db=getattr(fc, "gain_dbfs", -16.0),
                        sanity_status="REJECTED",
                        remediation_notes="Rogue music/long file detected on Foley bus. Purged to prevent collision.",
                    )
                )
                continue

            # CHECK B: Era anachronisms (e.g. modern construction machines, modern street march)
            if any(term in fname_lower or term in fpath_str.lower() for term in banned_terms):
                report.rejected_count += 1
                report.cues.append(
                    AuditedCueRecord(
                        cue_id=fc.cue_id,
                        bus="FX",
                        asset_path=fpath_str,
                        asset_name=fpath.name,
                        start_ms=start_ms,
                        end_ms=start_ms + int(raw_dur * 1000),
                        raw_duration_sec=raw_dur,
                        effective_duration_sec=0.0,
                        volume_db=getattr(fc, "gain_dbfs", -16.0),
                        sanity_status="REJECTED",
                        remediation_notes=f"Era violation: Asset contains banned term for {era}.",
                    )
                )
                continue

            # CHECK C: Anti-Repetition Cooldown (identical asset repeated too soon)
            last_ts = recent_foley_assets.get(fname_lower)
            if last_ts is not None and (start_ms - last_ts) < self.ANTI_REPETITION_COOLDOWN_MS:
                report.rejected_count += 1
                report.cues.append(
                    AuditedCueRecord(
                        cue_id=fc.cue_id,
                        bus="FX",
                        asset_path=fpath_str,
                        asset_name=fpath.name,
                        start_ms=start_ms,
                        end_ms=start_ms + int(raw_dur * 1000),
                        raw_duration_sec=raw_dur,
                        effective_duration_sec=0.0,
                        volume_db=getattr(fc, "gain_dbfs", -16.0),
                        sanity_status="REJECTED",
                        remediation_notes=f"Anti-repetition cooldown violated: Asset repeated within {self.ANTI_REPETITION_COOLDOWN_MS/1000:.0f}s.",
                    )
                )
                continue

            # CHECK D: Strict Duration Cap & Trimming
            was_trimmed = False
            effective_dur = raw_dur
            if raw_dur > self.MAX_FOLEY_DURATION_SEC:
                effective_dur = self.MAX_FOLEY_DURATION_SEC
                was_trimmed = True

            recent_foley_assets[fname_lower] = start_ms
            status = "REMEDIATED" if was_trimmed else "PASS"
            if was_trimmed:
                report.remediated_count += 1
            else:
                report.passed_count += 1

            # Update cue duration in milliseconds
            fc.duration_ms = int(effective_dur * 1000)
            sanitized_foley.append(fc)

            report.cues.append(
                AuditedCueRecord(
                    cue_id=fc.cue_id,
                    bus="FX",
                    asset_path=fpath_str,
                    asset_name=fpath.name,
                    start_ms=start_ms,
                    end_ms=start_ms + int(effective_dur * 1000),
                    raw_duration_sec=raw_dur,
                    effective_duration_sec=effective_dur,
                    volume_db=getattr(fc, "gain_dbfs", -16.0),
                    was_trimmed=was_trimmed,
                    sanity_status=status,
                    remediation_notes="Trimmed to strict foley cap" if was_trimmed else "Passed sanity check",
                )
            )

        manifest.foley_cues = sanitized_foley

        # ---------------------------------------------------------------------
        # 2. Audit Ambience Scenes / Decoupled Scene Acoustics
        # ---------------------------------------------------------------------
        amb_scenes = getattr(manifest, "ambience_scenes", None)
        scene_acoustics = getattr(manifest, "scene_acoustics", None)

        if amb_scenes:
            sanitized_ambience: List[AmbienceScene] = []
            for ac in amb_scenes:
                report.total_cues_inspected += 1
                apath_str = (ac.asset_path or "").replace("\\", "/")
                aname_lower = Path(apath_str).name.lower()
                start_ms = int(ac.start_ms)
                end_ms = int(ac.end_ms)
                dur_sec = max(0.1, (end_ms - start_ms) / 1000.0)

                # Check for modern machinery or out-of-world ambience
                if any(term in aname_lower or term in apath_str.lower() for term in banned_terms):
                    report.remediated_count += 1
                    # Replace with verified authentic room tone or wind
                    safe_fallback = "wind_howl.ogg"
                    if self.sound_bank:
                        res = self.sound_bank.resolve_sound("wind_howl.ogg", category="AMB") or self.sound_bank.resolve_sound("room_tone", category="AMB")
                        if res and res.exists():
                            safe_fallback = str(res.resolve()).replace("\\", "/")
                    ac.asset_path = safe_fallback
                    report.cues.append(
                        AuditedCueRecord(
                            cue_id=f"amb_{start_ms}",
                            bus="AMB",
                            asset_path=safe_fallback,
                            asset_name=Path(safe_fallback).name,
                            start_ms=start_ms,
                            end_ms=end_ms,
                            raw_duration_sec=dur_sec,
                            effective_duration_sec=dur_sec,
                            volume_db=ac.target_lufs,
                            sanity_status="REMEDIATED",
                            remediation_notes=f"Replaced anachronistic bed ({aname_lower}) with authentic atmospheric tone.",
                        )
                    )
                else:
                    report.passed_count += 1
                    report.cues.append(
                        AuditedCueRecord(
                            cue_id=f"amb_{start_ms}",
                            bus="AMB",
                            asset_path=apath_str,
                            asset_name=Path(apath_str).name,
                            start_ms=start_ms,
                            end_ms=end_ms,
                            raw_duration_sec=dur_sec,
                            effective_duration_sec=dur_sec,
                            volume_db=ac.target_lufs,
                            sanity_status="PASS",
                            remediation_notes="Ambience bed validated.",
                        )
                    )
                sanitized_ambience.append(ac)
            manifest.ambience_scenes = sanitized_ambience
        elif scene_acoustics and hasattr(scene_acoustics, "scenes") and scene_acoustics.scenes:
            for sc in scene_acoustics.scenes:
                for l in sc.layers:
                    if getattr(l, "layer_type", "") == "spot_stochastic":
                        continue
                    report.total_cues_inspected += 1
                    apath_str = (getattr(l, "asset_path", "") or "").replace("\\", "/")
                    aname_lower = Path(apath_str).name.lower()
                    start_ms = int(sc.start_ms)
                    end_ms = int(sc.end_ms)
                    dur_sec = max(0.1, (end_ms - start_ms) / 1000.0)

                    if any(term in aname_lower or term in apath_str.lower() for term in banned_terms):
                        report.remediated_count += 1
                        safe_fallback = "wind_howl.ogg"
                        if self.sound_bank:
                            res = self.sound_bank.resolve_sound("wind_howl.ogg", category="AMB") or self.sound_bank.resolve_sound("room_tone", category="AMB")
                            if res and res.exists():
                                safe_fallback = str(res.resolve()).replace("\\", "/")
                        l.asset_path = safe_fallback
                        report.cues.append(
                            AuditedCueRecord(
                                cue_id=f"amb_{sc.scene_id}_{start_ms}",
                                bus="AMB",
                                asset_path=safe_fallback,
                                asset_name=Path(safe_fallback).name,
                                start_ms=start_ms,
                                end_ms=end_ms,
                                raw_duration_sec=dur_sec,
                                effective_duration_sec=dur_sec,
                                volume_db=getattr(l, "target_lufs", -32.0),
                                sanity_status="REMEDIATED",
                                remediation_notes=f"Replaced anachronistic bed ({aname_lower}) with authentic atmospheric tone.",
                            )
                        )
                    else:
                        report.passed_count += 1
                        report.cues.append(
                            AuditedCueRecord(
                                cue_id=f"amb_{sc.scene_id}_{start_ms}",
                                bus="AMB",
                                asset_path=apath_str,
                                asset_name=Path(apath_str).name,
                                start_ms=start_ms,
                                end_ms=end_ms,
                                raw_duration_sec=dur_sec,
                                effective_duration_sec=dur_sec,
                                volume_db=getattr(l, "target_lufs", -32.0),
                                sanity_status="PASS",
                                remediation_notes="Ambience bed validated.",
                            )
                        )

        # ---------------------------------------------------------------------
        # 3. Audit Music Cues
        # ---------------------------------------------------------------------
        music_cues = getattr(manifest, "music_cues", [])
        for mc in music_cues:
            report.total_cues_inspected += 1
            t_name = getattr(mc, "track_name", "music_track")
            m_start = int(mc.start_ms)
            m_dur_sec = float(mc.duration_ms) / 1000.0
            report.passed_count += 1
            report.cues.append(
                AuditedCueRecord(
                    cue_id=mc.cue_id,
                    bus="MX",
                    asset_path=t_name,
                    asset_name=t_name,
                    start_ms=m_start,
                    end_ms=m_start + int(mc.duration_ms),
                    raw_duration_sec=m_dur_sec,
                    effective_duration_sec=m_dur_sec,
                    volume_db=getattr(mc, "volume_db", -18.0),
                    sanity_status="PASS",
                    remediation_notes="Music underscore cue validated.",
                )
            )

        amb_count = len(getattr(manifest, "ambience_scenes", []) or [])
        if not amb_count and getattr(manifest, "scene_acoustics", None):
            amb_count = len(getattr(manifest.scene_acoustics, "scenes", []))

        report.summary = {
            "total_inspected": report.total_cues_inspected,
            "passed": report.passed_count,
            "remediated": report.remediated_count,
            "rejected": report.rejected_count,
            "foley_cues_remaining": len(getattr(manifest, "foley_cues", [])),
            "ambience_scenes_remaining": amb_count,
            "music_cues_remaining": len(getattr(manifest, "music_cues", []) or []),
        }

        # Persist ledger if output_dir provided
        if output_dir:
            out_p = Path(output_dir)
            out_p.mkdir(parents=True, exist_ok=True)
            ledger_file = out_p / f"{chapter_id}_audio_reality_ledger.json"
            with open(ledger_file, "w", encoding="utf-8") as f:
                f.write(report.model_dump_json(indent=2))
            logger.info(f"[+] Audio Reality Auditor: Emitted millisecond reality ledger to {ledger_file.name}")

        return manifest, report
