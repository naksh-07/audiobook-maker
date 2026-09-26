#!/usr/bin/env python3
"""
Audiobook Factory - Master Dialogue Editor (DE-01).
Coordinates Endpoint, Breath, and Pause Editors with QC validation.
Renders deterministic, high-fidelity dialogue edits into non-destructive edited WAVs
before downstream vocal stem concatenation and mastering.
"""

from __future__ import annotations
import json
import wave
import math
import hashlib
import shutil
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import numpy as np

from audiobook_factory.logger import logger
from audiobook_factory.forensic_analyzer import MathematicalAcousticAnalyzer
from audiobook_factory.alignment_contracts import AlignmentResult
from audiobook_factory.performance.contracts import (
    PerformanceDirection,
    PerformanceEvidence,
    TakeVariant,
)
from audiobook_factory.performance.director import PerformanceDirector
from audiobook_factory.performance.timing_realizer import TimingRealizer
from .contracts import DialogueEditPlan, DialogueEditorialConfig, DialogueQCReport
from .endpoint_editor import EndpointEditor
from .breath_editor import BreathEditor
from .pause_editor import PauseEditor
from .qc import DialogueEditingQC


class DialogueEditor:
    """
    World-Class Dialogue Editorial Engine.
    Executes: Audio + Alignment + Performance Metadata -> Analysis -> DialogueEditPlan -> QC -> Render.
    """

    def __init__(
        self,
        config: Optional[DialogueEditorialConfig] = None,
        project_dir: Optional[Path | str] = None,
        aligner: Optional[Any] = None,
        sample_rate: int = 24000,
    ):
        self.config = config or DialogueEditorialConfig()
        self.project_dir = Path(project_dir).resolve() if project_dir else Path(".")
        self.sample_rate = sample_rate
        self.aligner = aligner

        self.analyzer = MathematicalAcousticAnalyzer(sample_rate=sample_rate)
        self.endpoint_editor = EndpointEditor(config=self.config, analyzer=self.analyzer, sample_rate=sample_rate)
        self.breath_editor = BreathEditor(config=self.config)
        self.pause_editor = PauseEditor(config=self.config)
        self.qc = DialogueEditingQC(config=self.config)

    def plan_segment_edit(
        self,
        audio_path: Path | str,
        text: str = "",
        speaker: str = "Narrator",
        next_speaker: Optional[str] = None,
        direction: Optional[PerformanceDirection] = None,
        next_direction: Optional[PerformanceDirection] = None,
        evidence: Optional[PerformanceEvidence] = None,
        alignment: Optional[AlignmentResult] = None,
        segment_uid: str = "",
        segment_index: int = 1,
    ) -> DialogueEditPlan:
        """
        Creates a deterministic DialogueEditPlan for a single dialogue take.
        """
        p = Path(audio_path).resolve()
        source_take = p.stem

        # 1. Read PCM Audio Samples
        samples, sample_rate = self._load_wav_samples(p)
        total_dur_ms = int(len(samples) / sample_rate * 1000.0) if sample_rate > 0 else 0

        if total_dur_ms <= 80:
            if len(samples) == 0:
                # Corrupt or unreadable audio - fail closed
                return DialogueEditPlan(
                    segment_uid=segment_uid,
                    source_take=source_take,
                    speech_start_ms=0,
                    speech_end_ms=0,
                    confidence=0.0,
                    decision_reason="[HARD_FAILURE] Empty or unreadable audio take",
                    metadata={"segment_index": segment_index, "corrupt": True},
                )
            # Fallback for empty or near-empty chunks
            timing_dict = TimingRealizer.calculate_performance_timing(text=text, speaker=speaker)
            return DialogueEditPlan(
                segment_uid=segment_uid,
                source_take=source_take,
                speech_start_ms=0,
                speech_end_ms=total_dur_ms,
                pause_after_ms=timing_dict["pause_after_ms"],
                confidence=1.0,
                decision_reason="Very short audio; zero modifications applied",
                metadata={"segment_index": segment_index},
            )

        # 2. Run Endpoint Analysis (DE-02)
        ep_res = self.endpoint_editor.analyze_endpoints(
            samples=samples,
            sample_rate=sample_rate,
            alignment=alignment,
            direction=direction,
            evidence=evidence,
        )

        # 3. Run Breath Analysis (DE-03, DE-07)
        br_res = self.breath_editor.evaluate_breaths(
            samples=samples,
            sample_rate=sample_rate,
            speech_start_ms=ep_res["speech_start_ms"],
            speech_end_ms=ep_res["speech_end_ms"],
            direction=direction,
            evidence=evidence,
            alignment=alignment,
        )

        # 4. Run Contextual Pause Realization (DE-04, DE-05)
        pa_res = self.pause_editor.realize_pause(
            text=text,
            speaker=speaker,
            direction=direction,
            next_speaker=next_speaker,
            next_direction=next_direction,
            segment_uid=segment_uid,
            segment_index=segment_index,
        )

        # 5. Synthesize Combined DialogueEditPlan
        all_reasons = ep_res["decision_reasons"] + br_res["reasons"] + [pa_res["decision_reason"]]
        combined_conf = round(min(1.0, br_res["confidence"]), 2)

        interruption_mode = pa_res.get("interruption_mode")
        overlap_ms = pa_res.get("overlap_ms", 0)
        # Abrupt cut uses snappy zero-crossing micro-fade (2ms) instead of standard fade
        crossfade_out = 2.0 if interruption_mode == "abrupt_cut" else ep_res["crossfade_out_ms"]

        plan = DialogueEditPlan(
            segment_uid=segment_uid,
            source_take=source_take,
            speech_start_ms=ep_res["speech_start_ms"],
            speech_end_ms=ep_res["speech_end_ms"],
            head_trim_ms=ep_res["head_trim_ms"],
            tail_trim_ms=ep_res["tail_trim_ms"],
            head_classification=ep_res["head_classification"],
            tail_classification=ep_res["tail_classification"],
            pre_breath_action=br_res["pre_breath_action"],
            post_breath_action=br_res["post_breath_action"],
            pre_breath_attenuation_db=br_res["pre_breath_attenuation_db"],
            post_breath_attenuation_db=br_res["post_breath_attenuation_db"],
            mid_breath_edits=br_res.get("mid_breath_edits", []),
            pause_before_ms=direction.pause_before_ms if direction else 0,
            pause_after_ms=pa_res["pause_after_ms"],
            pause_classification=pa_res["pause_classification"],
            overlap_ms=overlap_ms,
            interruption_mode=interruption_mode,
            crossfade_in_ms=ep_res["crossfade_in_ms"],
            crossfade_out_ms=crossfade_out,
            confidence=combined_conf,
            decision_reason="; ".join(r for r in all_reasons if r),
            diagnostics=[],
            metadata={
                "segment_index": segment_index,
                "original_duration_ms": total_dur_ms,
                "effective_duration_ms": total_dur_ms - ep_res["head_trim_ms"] - ep_res["tail_trim_ms"],
            },
        )

        # 6. Audit through QC Gate
        diags = self.qc.audit_segment_plan(plan, total_dur_ms, alignment, samples)
        if diags:
            plan.diagnostics = [f"[{d.severity}] {d.code}: {d.message}" for d in diags]
            has_hard_fail = any(d.severity == "HARD_FAILURE" for d in diags)
            if has_hard_fail:
                plan.confidence = 0.0
                plan.head_trim_ms = 0
                plan.tail_trim_ms = 0
                plan.decision_reason += " [QC HARD FAILURE: Reverted trims to preserve speech integrity]"

        return plan

    def apply_edit_plan(
        self,
        input_wav: Path | str,
        edit_plan: DialogueEditPlan,
        output_wav: Path | str,
    ) -> Path:
        """
        Renders a DialogueEditPlan to disk as an edited 16-bit PCM WAV.
        Executes head/tail slicing, breath attenuation, micro-fades, and zero-crossing pinning.
        """
        inp = Path(input_wav).resolve()
        outp = Path(output_wav).resolve()
        outp.parent.mkdir(parents=True, exist_ok=True)

        samples, sample_rate = self._load_wav_samples(inp)
        total_samples = len(samples)
        total_dur_ms = int(total_samples / sample_rate * 1000.0) if sample_rate > 0 else 0

        # Check if plan bypassed editing
        has_mid_edits = any(me.action != "KEEP" for me in edit_plan.mid_breath_edits)
        if (
            edit_plan.head_trim_ms == 0
            and edit_plan.tail_trim_ms == 0
            and edit_plan.pre_breath_action == "KEEP"
            and edit_plan.post_breath_action == "KEEP"
            and not has_mid_edits
            and edit_plan.interruption_mode != "fade_under"
            and abs(edit_plan.gain_adjustment_db) < 0.05
        ):
            if inp != outp:
                shutil.copy2(inp, outp)
            return outp

        # 1. Calculate Sample Slice Offsets
        head_samples = int(edit_plan.head_trim_ms / 1000.0 * sample_rate)
        tail_samples = int(edit_plan.tail_trim_ms / 1000.0 * sample_rate)

        head_samples = max(0, min(total_samples - 100, head_samples))
        tail_samples = max(0, min(total_samples - head_samples - 50, tail_samples))

        sliced = samples[head_samples : total_samples - tail_samples].copy()
        n_sliced = len(sliced)

        if n_sliced < 50:
            if inp != outp:
                shutil.copy2(inp, outp)
            return outp

        # 2. Editorial Gain Balancing
        if abs(edit_plan.gain_adjustment_db) >= 0.05:
            gain_factor = 10.0 ** (edit_plan.gain_adjustment_db / 20.0)
            sliced *= gain_factor

        # 3. Breath Attenuation Envelope Application
        # Pre-speech breath attenuation
        if edit_plan.pre_breath_action == "REDUCE" and edit_plan.pre_breath_attenuation_db < 0:
            factor = 10.0 ** (edit_plan.pre_breath_attenuation_db / 20.0)
            breath_end_idx = min(n_sliced // 4, int(0.20 * sample_rate))
            if breath_end_idx > 10:
                t = np.linspace(0.0, np.pi, breath_end_idx)
                ramp = factor + (1.0 - factor) * 0.5 * (1.0 - np.cos(t))
                sliced[:breath_end_idx] *= ramp

        elif edit_plan.pre_breath_action == "REMOVE":
            breath_end_idx = min(n_sliced // 4, int(0.15 * sample_rate))
            if breath_end_idx > 10:
                t = np.linspace(0.0, np.pi, breath_end_idx)
                ramp = 0.02 + 0.98 * 0.5 * (1.0 - np.cos(t))
                sliced[:breath_end_idx] *= ramp

        # Post-speech breath attenuation
        if edit_plan.post_breath_action == "REDUCE" and edit_plan.post_breath_attenuation_db < 0:
            factor = 10.0 ** (edit_plan.post_breath_attenuation_db / 20.0)
            breath_start_idx = max(3 * n_sliced // 4, n_sliced - int(0.25 * sample_rate))
            span = n_sliced - breath_start_idx
            if span > 10:
                t = np.linspace(0.0, np.pi, span)
                ramp = 1.0 - (1.0 - factor) * 0.5 * (1.0 - np.cos(t))
                sliced[breath_start_idx:] *= ramp

        # Mid-line breath attenuation envelope application (DE-07)
        if edit_plan.mid_breath_edits:
            for me in edit_plan.mid_breath_edits:
                if me.action in ("REDUCE", "REMOVE"):
                    factor = 0.05 if me.action == "REMOVE" else (10.0 ** (me.attenuation_db / 20.0))
                    rel_start = max(0, int(me.start_ms / 1000.0 * sample_rate) - head_samples)
                    rel_end = min(n_sliced, int(me.end_ms / 1000.0 * sample_rate) - head_samples)
                    span = rel_end - rel_start
                    if span > 10 and rel_start < n_sliced:
                        fade_len = min(int(0.020 * sample_rate), span // 3)
                        ramp = np.full(span, factor, dtype=np.float32)
                        if fade_len > 2:
                            t_in = np.linspace(0.0, np.pi, fade_len)
                            ramp[:fade_len] = factor + (1.0 - factor) * 0.5 * (1.0 + np.cos(t_in))
                            t_out = np.linspace(np.pi, 0.0, fade_len)
                            ramp[-fade_len:] = factor + (1.0 - factor) * 0.5 * (1.0 + np.cos(t_out))
                        sliced[rel_start:rel_end] *= ramp

        # Interruption tail ducking for fade_under (DE-05)
        if edit_plan.interruption_mode == "fade_under":
            duck_samples = min(int(0.12 * sample_rate), n_sliced // 3)
            if duck_samples > 10:
                t_duck = np.linspace(0.0, np.pi, duck_samples)
                duck_ramp = 0.35 + 0.65 * 0.5 * (1.0 + np.cos(t_duck))
                sliced[-duck_samples:] *= duck_ramp

        # 4. Micro-Fades (True Hann Raised-Cosine preserving 5.0ms technical de-click baseline)
        fade_in_samples = max(2, min(int(sample_rate * (edit_plan.crossfade_in_ms / 1000.0)), n_sliced // 2))
        fade_out_samples = max(2, min(int(sample_rate * (edit_plan.crossfade_out_ms / 1000.0)), n_sliced // 2))

        # Hann micro-fade in: w(0) = 0, w'(0) = 0
        t_in = np.linspace(0.0, np.pi, fade_in_samples)
        sliced[:fade_in_samples] *= 0.5 * (1.0 - np.cos(t_in))

        # Hann micro-fade out: w(0) = 1, w(T) = 0, w'(T) = 0
        t_out = np.linspace(np.pi, 0.0, fade_out_samples)
        sliced[-fade_out_samples:] *= 0.5 * (1.0 - np.cos(t_out))

        # 5. Deterministic TPDF Dithered Quantization to 16-bit PCM WAV (SHA256 seeded)
        h_bytes = hashlib.sha256(f"{edit_plan.source_take}:{edit_plan.segment_uid}".encode("utf-8")).digest()
        seed_int = int.from_bytes(h_bytes[:4], byteorder="little") & 0x7FFFFFFF
        rng = np.random.default_rng(seed_int)
        dither = rng.uniform(-0.5, 0.5, size=n_sliced).astype(np.float32) + rng.uniform(-0.5, 0.5, size=n_sliced).astype(np.float32)
        int16_samples = np.clip(np.round(sliced + dither), -32768.0, 32767.0).astype(np.int16)

        # 6. Zero-crossing Boundary Pinning (exact zero at endpoints to guarantee click-free boundaries)
        int16_samples[0] = 0
        int16_samples[-1] = 0


        with wave.open(str(outp), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(int16_samples.tobytes())

        return outp


    def smooth_take_boundaries(
        self,
        plans: List[DialogueEditPlan],
        audio_segments: List[Path],
        directions: Optional[Dict[int, PerformanceDirection]] = None,
    ) -> None:
        """
        Enhances take boundary continuity between independently generated takes (DE-06).
        Applies inter-take gain leveling (up to +/-2.5dB) across adjacent takes
        and detects elevated noise floors to expand transition micro-fades to 15ms.
        """
        if not plans or not audio_segments or len(plans) != len(audio_segments):
            return

        speech_rms_list: List[float] = []
        noise_floors_db: List[float] = []

        # 1. Measure Speech RMS and Noise Floor for each segment
        for seg_path, plan in zip(audio_segments, plans):
            samples, sr = self._load_wav_samples(seg_path)
            if len(samples) < 200 or sr <= 0:
                speech_rms_list.append(-24.0)
                noise_floors_db.append(-60.0)
                continue

            # Speech portion RMS
            s_start = int(plan.speech_start_ms / 1000.0 * sr)
            s_end = int(plan.speech_end_ms / 1000.0 * sr)
            speech_sub = samples[s_start:s_end] if s_end > s_start else samples
            if len(speech_sub) > 100:
                s_rms = float(np.sqrt(np.mean(speech_sub ** 2)))
                s_db = 20.0 * math.log10(max(s_rms, 1e-5) / 32768.0)
            else:
                s_db = -24.0
            speech_rms_list.append(s_db)

            # Measure noise floor in silence margin (first 80ms or last 80ms)
            margin_samples = min(int(0.08 * sr), len(samples) // 4)
            if margin_samples > 20:
                head_noise = float(np.sqrt(np.mean(samples[:margin_samples] ** 2)))
                tail_noise = float(np.sqrt(np.mean(samples[-margin_samples:] ** 2)))
                min_noise = min(head_noise, tail_noise)
                n_db = 20.0 * math.log10(max(min_noise, 1e-6) / 32768.0)
            else:
                n_db = -60.0
            noise_floors_db.append(n_db)

        # 2. Inter-take Gain Leveling across adjacent takes
        max_adj = self.config.inter_take_max_gain_adjust_db
        for i in range(len(plans) - 1):
            plan_curr = plans[i]
            plan_next = plans[i + 1]

            dir_curr = directions.get(i + 1) if directions else None
            dir_next = directions.get(i + 2) if directions else None

            curr_intensity = getattr(dir_curr, "intensity", getattr(dir_curr, "intensity_level", None)) if dir_curr else None
            next_intensity = getattr(dir_next, "intensity", getattr(dir_next, "intensity_level", None)) if dir_next else None

            curr_is_extreme = bool(curr_intensity in ("explosive", "whisper", "shouting", "screaming", "high"))
            next_is_extreme = bool(next_intensity in ("explosive", "whisper", "shouting", "screaming", "high"))

            if not curr_is_extreme and not next_is_extreme:
                rms_curr = speech_rms_list[i]
                rms_next = speech_rms_list[i + 1]
                delta = rms_next - rms_curr

                # If jump exceeds 1.2dB, nudge plan_next to level volume smoothly
                if abs(delta) > 1.2:
                    adjustment = float(np.clip(-delta * 0.5, -max_adj, max_adj))
                    if abs(plan_next.gain_adjustment_db) < 0.05:
                        plan_next.gain_adjustment_db = round(adjustment, 2)
                        plan_next.decision_reason += f"; Inter-take gain leveling adjusted by {adjustment:+.1f}dB"

        # 3. Elevated Noise-Floor Discontinuity Detection
        elevated_threshold = self.config.boundary_elevated_noise_floor_db
        for plan, n_db in zip(plans, noise_floors_db):
            if n_db > elevated_threshold:
                # Expand micro-fades to 15ms Hann tapers to prevent vocoder noise drop click
                plan.crossfade_in_ms = max(plan.crossfade_in_ms, 15.0)
                plan.crossfade_out_ms = max(plan.crossfade_out_ms, 15.0)
                plan.metadata["room_match_required"] = True
                plan.decision_reason += f"; Elevated noise floor ({n_db:.1f} dBFS); expanded boundary micro-fades to 15ms"

    def process_chapter(
        self,
        chapter_num: int,
        audio_segments: List[Path],
        script_segments: Optional[List[Dict[str, Any]]] = None,
        output_dir: Optional[Path] = None,
    ) -> Tuple[List[Path], List[DialogueEditPlan], DialogueQCReport]:
        """
        Coordinates full chapter dialogue editing:
        1. Loads TakeBank manifest if present; otherwise infers directions.
        2. Generates DialogueEditPlan for each segment with conversational context.
        3. Applies inter-take boundary continuity smoothing (DE-06).
        4. Audits complete chapter through DialogueEditingQC.
        5. Renders edited WAVs into output_dir (defaults to project_dir / 'edited_chunks').
        6. Fails closed with graceful fallback to unedited takes on hard QC violations.
        """
        if not audio_segments:
            return [], [], DialogueQCReport(chapter_num=chapter_num, total_segments=0, passed=True)

        audio_dir = audio_segments[0].parent
        target_dir = Path(output_dir) if output_dir else (self.project_dir / "edited_chunks")
        target_dir.mkdir(parents=True, exist_ok=True)

        # 1. Attempt to load TakeBank manifest for rich performance context
        take_bank_file = audio_dir / f"c{chapter_num:03d}_take_bank.json"
        takes_by_uid: Dict[str, TakeVariant] = {}
        if take_bank_file.exists():
            try:
                with open(take_bank_file, "r", encoding="utf-8") as f:
                    tb_data = json.load(f)
                for uid, t_list in tb_data.items():
                    for t_dict in t_list:
                        tv = TakeVariant.model_validate(t_dict)
                        if tv.is_selected or uid not in takes_by_uid:
                            takes_by_uid[uid] = tv
            except Exception as e:
                logger.warning(f"  [!] DialogueEditor could not load take bank: {e}")

        # 2. Derive PerformanceDirections for script segments if not in TakeBank
        dir_by_idx: Dict[int, PerformanceDirection] = {}
        if script_segments:
            try:
                director = PerformanceDirector()
                directions = director.direct_chapter_script(script_segments)
                for d in directions:
                    dir_by_idx[d.index] = d
            except Exception as e:
                logger.warning(f"  [!] DialogueEditor could not direct script: {e}")

        # 3. Plan Edits Across All Segments
        plans: List[DialogueEditPlan] = []
        seg_durations_ms: List[int] = []
        alignments: List[Optional[AlignmentResult]] = []

        total_segs = len(audio_segments)
        for i, seg_path in enumerate(audio_segments):
            # Parse segment index from filename (e.g. c001_s0005_hash.wav)
            s_idx = i + 1
            for part in seg_path.stem.split("_"):
                if part.startswith("s") and part[1:].isdigit():
                    s_idx = int(part[1:])
                    break

            script_info = script_segments[i] if (script_segments and i < len(script_segments)) else {}
            speaker = script_info.get("speaker", "Narrator")
            text = script_info.get("text", "")
            seg_uid = script_info.get("uid", f"seg_{s_idx}")

            # Next speaker and direction for conversational turn latency & interruption context
            next_spk = None
            next_dir = None
            if script_segments and i + 1 < len(script_segments):
                next_spk = script_segments[i + 1].get("speaker", None)

            next_s_idx = s_idx + 1
            if next_s_idx in dir_by_idx:
                next_dir = dir_by_idx[next_s_idx]
            elif i + 1 < len(audio_segments):
                for part in audio_segments[i + 1].stem.split("_"):
                    if part.startswith("s") and part[1:].isdigit():
                        candidate_idx = int(part[1:])
                        if candidate_idx in dir_by_idx:
                            next_dir = dir_by_idx[candidate_idx]
                        break

            # Match direction & take telemetry
            direction = dir_by_idx.get(s_idx)
            evidence = None
            alignment = None

            if seg_uid in takes_by_uid:
                matched_take = takes_by_uid[seg_uid]
                if matched_take.direction:
                    direction = matched_take.direction
                if matched_take.evaluation and matched_take.evaluation.evidence:
                    evidence = matched_take.evaluation.evidence
                if matched_take.alignment_result:
                    alignment = matched_take.alignment_result

            # Run forced aligner on-demand if available and not yet aligned
            if alignment is None and self.aligner is not None:
                try:
                    alignment = self.aligner.align_segment(
                        audio_path=seg_path,
                        text=text,
                        segment_uid=seg_uid,
                        direction=direction,
                    )
                except Exception:
                    pass

            plan = self.plan_segment_edit(
                audio_path=seg_path,
                text=text,
                speaker=speaker,
                next_speaker=next_spk,
                direction=direction,
                next_direction=next_dir,
                evidence=evidence,
                alignment=alignment,
                segment_uid=seg_uid,
                segment_index=s_idx,
            )
            plans.append(plan)
            alignments.append(alignment)

            # Measure segment duration
            try:
                with wave.open(str(seg_path), "rb") as wf:
                    dur_ms = int(wf.getnframes() / float(wf.getframerate()) * 1000.0)
            except Exception:
                dur_ms = 3000
            seg_durations_ms.append(dur_ms)

        # 4. Apply Take Boundary Continuity Smoothing (DE-06)
        self.smooth_take_boundaries(plans=plans, audio_segments=audio_segments, directions=dir_by_idx)

        # 5. Audit Full Chapter Plans
        qc_report = self.qc.audit_chapter_plans(
            chapter_num=chapter_num,
            plans=plans,
            segment_durations_ms=seg_durations_ms,
            alignments=alignments,
        )

        # 6. Render or Fallback
        edited_paths: List[Path] = []
        if qc_report.passed:
            logger.info(
                f"[*] Dialogue Editorial Layer: Rendering {len(plans)} segments for Chapter {chapter_num:02d} "
                f"({qc_report.edited_segments} edited, {qc_report.breaths_kept} breaths kept, "
                f"{qc_report.breaths_reduced} reduced, {qc_report.mid_breaths_reduced} mid-reduced, "
                f"{qc_report.interruptions_managed} interruptions, {qc_report.overlaps_rendered} overlaps)..."
            )
            for seg_path, plan in zip(audio_segments, plans):
                out_path = target_dir / seg_path.name
                rendered = self.apply_edit_plan(seg_path, plan, out_path)
                edited_paths.append(rendered)

            # Persist editorial manifest for auditability
            manifest_file = self.project_dir / "manifests" / f"c{chapter_num:03d}_editorial_manifest.json"
            manifest_file.parent.mkdir(parents=True, exist_ok=True)
            try:
                with open(manifest_file, "w", encoding="utf-8") as mf:
                    dump_dict = {
                        "chapter_num": chapter_num,
                        "qc_report": qc_report.model_dump(),
                        "plans": [p.model_dump() for p in plans],
                    }
                    json.dump(dump_dict, mf, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"  [!] Failed to save editorial manifest: {e}")
        else:
            logger.warning(
                f"[!] Dialogue Editorial QC FAILED for Chapter {chapter_num:02d} ({len(qc_report.hard_failures)} hard failures). "
                f"Safely falling back to unedited raw takes."
            )
            edited_paths = list(audio_segments)

        return edited_paths, plans, qc_report

    def _load_wav_samples(self, wav_path: Path) -> Tuple[np.ndarray, int]:
        """Loads 16-bit, 24-bit packed PCM or 32-bit float samples, downmixed to mono float32."""
        try:
            with wave.open(str(wav_path), "rb") as wf:
                sample_rate = wf.getframerate()
                n_frames = wf.getnframes()
                sampwidth = wf.getsampwidth()
                n_channels = wf.getnchannels()
                raw_bytes = wf.readframes(n_frames)

            if n_frames == 0 or len(raw_bytes) == 0:
                return np.zeros(0, dtype=np.float32), sample_rate

            if sampwidth == 2:
                samples = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32)
            elif sampwidth == 3:  # 24-bit packed PCM
                raw_arr = np.frombuffer(raw_bytes, dtype=np.uint8).reshape(-1, 3)
                padded = np.pad(raw_arr, ((0, 0), (1, 0)), mode="constant", constant_values=0)
                int32_arr = padded.view("<i4").flatten() >> 8
                samples = (int32_arr / 256.0).astype(np.float32)
            elif sampwidth == 4:  # 32-bit float or 32-bit int PCM
                try:
                    float_arr = np.frombuffer(raw_bytes, dtype=np.float32)
                    if len(float_arr) == n_frames * n_channels:
                        samples = float_arr * 32768.0
                    else:
                        samples = (np.frombuffer(raw_bytes, dtype=np.int32) / 65536.0).astype(np.float32)
                except Exception:
                    samples = (np.frombuffer(raw_bytes, dtype=np.int32) / 65536.0).astype(np.float32)
            else:
                samples = np.zeros(n_frames * n_channels, dtype=np.float32)

            if n_channels > 1 and len(samples) >= n_channels:
                samples = samples.reshape(-1, n_channels).mean(axis=1)

            return samples, sample_rate
        except Exception:
            return np.zeros(0, dtype=np.float32), self.sample_rate
