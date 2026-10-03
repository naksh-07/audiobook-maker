#!/usr/bin/env python3
"""
Audiobook Factory - Screenplay & Dramaturgy Quality Gates.
Houses Gate 2 (Screenplay Schema & Speaker Catalog Validation), Gate 2 (Screenplay Tags & Prosody),
Gate 2.5 (Dramatic Fidelity & Character Arc Validator), Gate 2.8 (Performance Fidelity),
and Gate 3 (Dramatic Scenes Source Coverage).
"""

from __future__ import annotations
import re
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Set, Optional, Tuple

from audiobook_factory.contracts import ScreenplayScript
from audiobook_factory.gates.contracts import GateAuditError

logger = logging.getLogger("audiobook_factory.gates.screenplay")


def audit_gate2_script(
    script_file: Path,
    allowed_speakers: Optional[Set[str]] = None,
    project_dir: Optional[Path] = None,
    enable_llm_judge: bool = True,
    source_file: Optional[Path] = None,
    strict: bool = True,
) -> Dict[str, Any]:
    """Audit Gate 2: Verifies screenplay script against schema, speaker keys, and LLM dialogue attribution."""
    script_file = Path(script_file).resolve()
    if not script_file.exists():
        raise GateAuditError(f"Gate 2 Failed: Script file missing at {script_file}")

    script = ScreenplayScript.from_file(script_file)
    if not script.segments:
        raise GateAuditError("Gate 2 Failed: Screenplay has 0 segments!")

    pdir = Path(project_dir).resolve() if project_dir else script_file.parent.parent
    roster_file = pdir / "character_roster.json"
    reg_file = pdir / "voice_registry.json"

    # Auto-discover project roster and voice registry if allowed_speakers is not explicitly provided
    if allowed_speakers is None:
        discovered: Set[str] = {"Narrator", "Foley"}
        has_catalog = False

        if roster_file.exists():
            try:
                with open(roster_file, "r", encoding="utf-8") as f:
                    rdata = json.load(f)
                chars = rdata.get("characters", rdata)
                if isinstance(chars, dict):
                    has_catalog = True
                    for cname, details in chars.items():
                        discovered.add(cname.strip())
                        discovered.add(cname.strip().replace("_", " "))
                        discovered.add(cname.strip().replace(" ", "_"))
                        if isinstance(details, dict):
                            for alias in details.get("aliases", []):
                                if isinstance(alias, str) and alias.strip():
                                    discovered.add(alias.strip())
                                    discovered.add(alias.strip().replace("_", " "))
                                    discovered.add(alias.strip().replace(" ", "_"))
                elif isinstance(chars, list):
                    has_catalog = True
                    for item in chars:
                        if isinstance(item, dict):
                            cname = item.get("english_name") or item.get("display_name") or item.get("name")
                            if cname:
                                discovered.add(cname.strip())
                                discovered.add(cname.strip().replace("_", " "))
                            hname = item.get("hindi_name")
                            if hname:
                                discovered.add(hname.strip())
                            for alias in item.get("aliases", []):
                                if isinstance(alias, str) and alias.strip():
                                    discovered.add(alias.strip())
            except Exception as e:
                logger.warning(f"  [GATE 2 NOTICE] Could not parse {roster_file.name}: {e}")

        if reg_file.exists():
            try:
                with open(reg_file, "r", encoding="utf-8") as f:
                    reg_data = json.load(f)
                if isinstance(reg_data, dict):
                    has_catalog = True
                    for k in reg_data.keys():
                        discovered.add(k.strip())
                        discovered.add(k.strip().replace("_", " "))
            except Exception as e:
                logger.warning(f"  [GATE 2 NOTICE] Could not parse {reg_file.name}: {e}")

        if has_catalog and len(discovered) > 2:
            allowed_speakers = discovered

    unknown_speakers = set()
    speaker_breakdown: Dict[str, int] = {}
    dialogue_indices: List[int] = []
    swallowed_quotes: List[Tuple[int, List[str]]] = []

    for seg in script.segments:
        sp = seg.speaker.strip()
        speaker_breakdown[sp] = speaker_breakdown.get(sp, 0) + 1
        if seg.type == "dialogue":
            dialogue_indices.append(seg.index)

        # ADR-044 Fail-Closed Anti-Swallow Dialogue Guard
        if seg.type == "narration" or sp.lower() == "narrator":
            quotes = re.findall(r'["“][^"”]{2,}["”]', seg.text or "")
            if quotes:
                swallowed_quotes.append((seg.index, quotes))

        if allowed_speakers:
            # Check canonical, normalized lower, or space-to-underscore match
            sp_norm = sp.lower()
            allowed_norm = {a.lower() for a in allowed_speakers}
            if sp_norm not in allowed_norm and sp_norm.replace("_", " ") not in allowed_norm:
                unknown_speakers.add(sp)

    if swallowed_quotes:
        raise GateAuditError(
            f"Gate 2 Failed: Direct dialogue quotes detected inside narration segments: {swallowed_quotes}"
        )

    if unknown_speakers:
        raise GateAuditError(
            f"Gate 2 Failed: Found non-canonical speakers / Unregistered speaker(s) in screenplay: {sorted(list(unknown_speakers))}"
        )

    # Validate monotonic sequential indexing
    for idx, seg in enumerate(script.segments, 1):
        if seg.index != idx:
            raise GateAuditError(
                f"Gate 2 Failed: Non-sequential segment index at position {idx} (found index {seg.index})"
            )

    llm_info: Dict[str, Any] = {}
    if enable_llm_judge:
        source_text = ""
        candidate_sources = []
        if source_file and Path(source_file).exists():
            candidate_sources.append(Path(source_file))

        # Auto-detect source files from project directories
        stem_clean = script_file.stem.replace("_hi_script", "").replace("_script", "")
        candidate_sources.extend([
            pdir / "translation" / f"{stem_clean}_hi.md",
            pdir / "translated" / f"{stem_clean}.md",
            pdir / "extracted" / f"{stem_clean}.md",
        ])
        for cs in candidate_sources:
            if cs.exists():
                try:
                    source_text = cs.read_text(encoding="utf-8")
                    if source_text.strip():
                        break
                except Exception:
                    pass

        if source_text:
            from audiobook_factory.gates.llm_judge import LLMScreenplayAuditor
            raw_segments = [s.model_dump() for s in script.segments]
            roster_data = None
            if roster_file.exists():
                try:
                    with open(roster_file, "r", encoding="utf-8") as rf:
                        roster_data = json.load(rf)
                except Exception:
                    pass

            verdict = LLMScreenplayAuditor.audit_screenplay(
                source_text=source_text,
                script_segments=raw_segments,
                character_roster=roster_data,
                strict=strict,
            )
            llm_info = {
                "attribution_score": verdict.score,
                "misattributed_segments": verdict.misattributed_segments,
                "hallucinated_lines": verdict.hallucinated_lines,
                "attribution_reason": verdict.reason,
            }

    return {
        "status": "PASS",
        "total_segments": len(script.segments),
        "total_dialogue_segments": len(dialogue_indices),
        "unique_speakers": len(speaker_breakdown),
        "speaker_breakdown": speaker_breakdown,
        **llm_info,
    }


def audit_gate2_screenplay_tags(script_file: Path) -> Dict[str, Any]:
    """
    Audit Gate 2 (Screenplay Tags & Prosody Auditor):
    Verifies that emotional character dialogues and dramatic segments
    contain appropriate expressive neural vocal tags or dramatic typography prosody.
    """
    script_file = Path(script_file).resolve()
    if not script_file.exists():
        raise GateAuditError(f"Gate 2 Screenplay Tags Failed: Script file missing at {script_file}")

    script = ScreenplayScript.from_file(script_file)
    if not script.segments:
        raise GateAuditError("Gate 2 Screenplay Tags Failed: Screenplay has 0 segments!")

    from audiobook_factory.sanitizer import SUPPORTED_TTS_TAG_PATTERNS
    tag_regex = re.compile(rf"\[\s*(?:{'|'.join(SUPPORTED_TTS_TAG_PATTERNS)})\s*\]", re.IGNORECASE)

    EMOTIONAL_EMOTIONS = {"angry", "whispering", "whisper", "sad", "excited", "growl", "calm_raspy", "shouting", "fear", "rage", "crying"}
    EMOTIONAL_ACTING_STYLES = {
        "whispering_fear", "cold_menace", "breathless_exhaustion",
        "ironic_mockery", "bellowing_rage", "gentle_tender"
    }

    dialogue_count = 0
    emotional_dialogues = 0
    tagged_or_prosodic = 0
    missing_prosody_segments = []

    for seg in script.segments:
        if seg.type != "dialogue":
            continue
        dialogue_count += 1
        text = seg.text or ""
        emotion = (seg.emotion or "").lower()
        acting = getattr(seg, "acting", None)
        delivery_style = ""
        if isinstance(acting, dict):
            delivery_style = acting.get("delivery_style", "")
        elif hasattr(acting, "delivery_style"):
            delivery_style = getattr(acting, "delivery_style", "")

        is_emotional = (
            emotion in EMOTIONAL_EMOTIONS or
            delivery_style in EMOTIONAL_ACTING_STYLES or
            "!" in text or "..." in text or "—" in text
        )

        has_vocal_tag = bool(tag_regex.search(text))
        has_punctuation_prosody = any(p in text for p in ("...", "!", "—", "?!"))
        has_acting_style = bool(delivery_style and delivery_style != "neutral")

        if is_emotional:
            emotional_dialogues += 1
            if has_vocal_tag or has_punctuation_prosody or has_acting_style:
                tagged_or_prosodic += 1
            else:
                missing_prosody_segments.append({
                    "index": seg.index,
                    "speaker": seg.speaker,
                    "emotion": emotion,
                    "delivery_style": delivery_style,
                    "text": text[:50],
                })

    coverage_pct = round((tagged_or_prosodic / max(1, emotional_dialogues)) * 100.0, 1)

    return {
        "status": "PASS",
        "total_segments": len(script.segments),
        "total_dialogues": dialogue_count,
        "emotional_dialogues": emotional_dialogues,
        "prosodic_dialogues": tagged_or_prosodic,
        "prosody_coverage_pct": coverage_pct,
        "flagged_missing_prosody": missing_prosody_segments,
    }


def audit_gate2_5_dramatic_fidelity(
    script_file: Path,
    dramatic_plan_file: Optional[Path] = None,
    source_file: Optional[Path] = None,
    project_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Audit Gate 2.5: Dramatic Fidelity & Character Arc Validator.
    Verifies dramatic beat consistency, anti-emotional teleportation, character objectives,
    and creative overreach guards on dramatized screenplay scripts.
    """
    from audiobook_factory.dramaturgy.dramatic_validator import DramaticValidator
    from audiobook_factory.dramaturgy.contracts import DramaticPlan

    script_file = Path(script_file).resolve()
    if not script_file.exists():
        raise GateAuditError(f"Gate 2.5 Failed: Script file missing at {script_file}")

    script = ScreenplayScript.from_file(script_file)
    segments = [s.model_dump() for s in script.segments]

    d_plan = None
    if dramatic_plan_file and Path(dramatic_plan_file).exists():
        try:
            d_plan = DramaticPlan.load_from_file(dramatic_plan_file)
        except Exception as e:
            logger.warning(f"  [GATE 2.5 NOTICE] Could not load dramatic plan {dramatic_plan_file}: {e}")

    source_text = ""
    if source_file and Path(source_file).exists():
        try:
            with open(source_file, "r", encoding="utf-8") as f:
                source_text = f.read()
        except Exception:
            pass

    known_chars = None
    if project_dir:
        pdir = Path(project_dir).resolve()
        r_file = pdir / "character_roster.json"
        if r_file.exists():
            try:
                with open(r_file, "r", encoding="utf-8") as f:
                    r_data = json.load(f)
                    known_chars = list(r_data.get("characters", {}).keys())
            except Exception:
                pass

    val_res = DramaticValidator.validate_screenplay_and_plan(
        segments=segments,
        dramatic_plan=d_plan,
        source_text=source_text,
        known_characters=known_chars,
    )

    if not val_res.passed:
        error_msgs = [i.message for i in val_res.issues if i.severity == "ERROR"]
        raise GateAuditError(f"Gate 2.5 Dramatic Fidelity Failed: {'; '.join(error_msgs[:3])}")

    return {
        "status": val_res.status,
        "total_segments": len(segments),
        "total_issues": val_res.total_issues,
        "warnings": [i.message for i in val_res.issues if i.severity == "WARNING"],
        "summary": val_res.summary,
    }


def audit_gate2_8_performance_fidelity(
    chapter_id: str,
    directions: List[Any],
    selected_takes: List[Any],
    allow_warnings: bool = True,
) -> Dict[str, Any]:
    """
    Audit Gate 2.8: Pre-Mix Performance Fidelity Gate.
    Verifies that performance directions are intact, anti-emotional teleportation rules are upheld,
    and all selected takes pass dimensional quality thresholds before dialogue stems enter mastering.
    """
    from audiobook_factory.performance.gate import PerformanceFidelityGate
    from audiobook_factory.performance.contracts import PerformanceDirection, TakeVariant

    parsed_directions = [
        d if isinstance(d, PerformanceDirection) else PerformanceDirection.model_validate(d)
        for d in directions
    ]
    parsed_takes = [
        t if isinstance(t, TakeVariant) else TakeVariant.model_validate(t)
        for t in selected_takes
    ]

    report = PerformanceFidelityGate.audit_chapter_performance(
        chapter_id=chapter_id,
        directions=parsed_directions,
        selected_takes=parsed_takes,
        allow_warnings=allow_warnings,
    )

    if not report.passed:
        raise GateAuditError(
            f"Gate 2.8 Performance Fidelity Failed for {chapter_id}: "
            f"{'; '.join(report.unresolved_issues[:3])}"
        )

    return {
        "status": "PASS",
        "chapter_id": chapter_id,
        "total_segments": report.total_segments,
        "total_takes": report.total_takes_generated,
        "avg_score": report.avg_evaluation_score,
        "dimension_averages": report.dimension_averages,
        "violations": report.teleportation_violations,
    }


def audit_gate3_scenes(scenes_file: Path, script_file: Path) -> Dict[str, Any]:
    """Audit Gate 3: Verifies dramatic scenes source continuity and coverage against the script."""
    scenes_file = Path(scenes_file).resolve()
    script_file = Path(script_file).resolve()

    if not scenes_file.exists():
        raise GateAuditError(f"Gate 3 Failed: Scenes source file missing at {scenes_file}")

    with open(scenes_file, "r", encoding="utf-8") as f:
        scenes = json.load(f)

    script = ScreenplayScript.from_file(script_file)
    total_segments = len(script.segments)

    if scenes.get("total_segments") != total_segments:
        raise GateAuditError(
            f"Gate 3 Failed: Segment count mismatch: scenes says {scenes.get('total_segments')}, script has {total_segments}"
        )

    acts = scenes.get("acts", [])
    if not acts:
        raise GateAuditError(f"Gate 3 Failed: Zero dramatic acts found in {scenes_file}")

    covered: Set[int] = set()
    for act in acts:
        s_start = act.get("segment_start", 0)
        s_end = act.get("segment_end", 0)
        if s_start < 1 or s_end > total_segments or s_start > s_end:
            raise GateAuditError(f"Gate 3 Failed: Invalid act range {s_start}..{s_end}")
        for i in range(s_start, s_end + 1):
            if i in covered:
                raise GateAuditError(f"Gate 3 Failed: Overlapping segment {i} across acts")
            covered.add(i)

    if covered != set(range(1, total_segments + 1)):
        missing = set(range(1, total_segments + 1)) - covered
        raise GateAuditError(f"Gate 3 Failed: Discontinuous segment coverage! Missing segments: {missing}")

    return {
        "status": "PASS",
        "total_acts": len(acts),
        "total_segments": total_segments,
    }
