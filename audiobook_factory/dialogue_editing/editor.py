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

        # 3. Run Breath Analysis (DE-03)
        br_res = self.breath_editor.evaluate_breaths(
            samples=samples,
            sample_rate=sample_rate,
            speech_start_ms=ep_res["speech_start_ms"],
            speech_end_ms=ep_res["speech_end_ms"],
            direction=direction,
            evidence=evidence,
        )

        # 4. Run Contextual Pause Realization (DE-04)
        pa_res = self.pause_editor.realize_pause(
            text=text,
            speaker=speaker,
            direction=direction,
            next_speaker=next_speaker,
            segment_uid=segment_uid,
            segment_index=segment_index,
        )

        # 5. Synthesize Combined DialogueEditPlan
        all_reasons = ep_res["decision_reasons"] + br_res["reasons"] + [pa_res["decision_reason"]]
        combined_conf = round(min(1.0, br_res["confidence"]), 2)

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
            pause_before_ms=direction.pause_before_ms if direction else 0,
            pause_after_ms=pa_res["pause_after_ms"],
            pause_classification=pa_res["pause_classification"],
            crossfade_in_ms=ep_res["crossfade_in_ms"],
            crossfade_out_ms=ep_res["crossfade_out_ms"],
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
        if (
            edit_plan.head_trim_ms == 0
            and edit_plan.tail_trim_ms == 0
            and edit_plan.pre_breath_action == "KEEP"
            and edit_plan.post_breath_action == "KEEP"
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

        # 4. Micro-Fades (True Hann Raised-Cosine preserving 5.0ms technical de-click baseline)
        fade_in_samples = max(2, min(int(sample_rate * (edit_plan.crossfade_in_ms / 1000.0)), n_sliced // 2))
        fade_out_samples = max(2, min(int(sample_rate * (edit_plan.crossfade_out_ms / 1000.0)), n_sliced // 2))

        # Hann micro-fade in: w(0) = 0, w'(0) = 0
        t_in = np.linspace(0.0, np.pi, fade_in_samples)
        sliced[:fade_in_samples] *= 0.5 * (1.0 - np.cos(t_in))

        # Hann micro-fade out: w(0) = 1, w(T) = 0, w'(T) = 0
        t_out = np.linspace(np.pi, 0.0, fade_out_samples)
        sliced[-fade_out_samples:] *= 0.5 * (1.0 - np.cos(t_out))

        # 5. TPDF Dithered Quantization to 16-bit PCM WAV
        seed_int = int(abs(hash(str(edit_plan.source_take) + str(edit_plan.segment_uid))) % (2**31 - 1))
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
        3. Audits complete chapter through DialogueEditingQC.
        4. Renders edited WAVs into output_dir (defaults to project_dir / 'edited_chunks').
        5. Fails closed with graceful fallback to unedited takes on hard QC violations.
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

            # Next speaker for conversational turn latency
            next_spk = None
            if script_segments and i + 1 < len(script_segments):
                next_spk = script_segments[i + 1].get("speaker", None)

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
                evidence=evidence,
                alignment=alignment,
                segment_uid=seg_uid,
                segment_index=s_idx,
            )
            plans.append(plan)

            # Measure segment duration
            try:
                with wave.open(str(seg_path), "rb") as wf:
                    dur_ms = int(wf.getnframes() / float(wf.getframerate()) * 1000.0)
            except Exception:
                dur_ms = 3000
            seg_durations_ms.append(dur_ms)

        # 4. Audit Full Chapter Plans
        qc_report = self.qc.audit_chapter_plans(
            chapter_num=chapter_num,
            plans=plans,
            segment_durations_ms=seg_durations_ms,
        )

        # 5. Render or Fallback
        edited_paths: List[Path] = []
        if qc_report.passed:
            logger.info(
                f"[*] Dialogue Editorial Layer: Rendering {len(plans)} segments for Chapter {chapter_num:02d} "
                f"({qc_report.edited_segments} edited, {qc_report.breaths_kept} breaths kept, "
                f"{qc_report.breaths_reduced} reduced, {qc_report.breaths_removed} removed)..."
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
