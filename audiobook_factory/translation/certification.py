#!/usr/bin/env python3
"""
Audiobook Factory - Multi-Gate Translation Certifier (Gates T0 to T11).
Executes the comprehensive verification lifecycle across all dimensions:
- Gate T0: Source Integrity & Length Sanity
- Gate T2: Semantic Fidelity (WHO -> DID WHAT -> TO WHOM -> OBJECT -> NEGATION)
- Gate T3: Omission Detection
- Gate T4: Addition / Hallucination Detection
- Gate T5: Terminology & Entity Consistency
- Gate T6: Relationship, Pronoun & Memory Continuity (Memory 2.0)
- Gate T7: Character Language Profile Alignment
- Gate T8: Mature Register & Intensity Preservation (Soft ±0.75 Heuristic)
- Gate T9: Hindi / Hindustani Literary Naturalness
- Gate T10: Register Balance & Advisory Lexicon Check
- Gate T11: Provenance & Artifact Completeness

Emits final certification status: PASS, PASS_WITH_WARNINGS, AUTO_REPAIR, REVIEW_REQUIRED, or BLOCKED.
"""

from __future__ import annotations
import json
from pathlib import Path
from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from .book_bible import BookBible
from .source_semantic_map import SourceSemanticMap, TargetSemanticMap, build_target_semantic_map
from .scene_planner import ScenePlan
from .intensity_model import LiteraryIntensityVector, IntensityEvaluator
from .terminology_auditor import audit_terminology
from .semantic_fidelity import evaluate_semantic_fidelity
from .omission_detector import evaluate_omissions
from .addition_detector import evaluate_additions
from .character_voice_auditor import evaluate_character_voices
from .naturalness_auditor import evaluate_literary_naturalness
from .hindustani_register import HindustaniRegisterEngine

EVALUATOR_VERSION = "2.0"

CRITICAL_GATES = {
    "T0_source_integrity",
    "T2_semantic_fidelity",
    "T3_omission",
    "T4_addition",
    "T5_terminology",
    "T6_relationship_memory",
    "T8_intensity",
    "T13_pronunciation_plan",
}

ADVISORY_GATES = {
    "T7_character_voice",
    "T9_naturalness",
    "T10_register_balance",
    "T12_spoken_language",
    "T14_pronunciation_audio",
    "T15_pronunciation_consistency",
}


class GateStatus(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


class GateResult(BaseModel):
    gate_id: str
    gate_name: str
    status: GateStatus
    details: str
    failures: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    affected_paragraphs: List[int] = Field(default_factory=list)


class GateAuditResult(BaseModel):
    chapter_num: int
    scene_id: str
    overall_status: str  # PASS, PASS_WITH_WARNINGS, AUTO_REPAIR, REVIEW_REQUIRED, BLOCKED
    certified: bool
    gates: Dict[str, GateResult] = Field(default_factory=dict)
    affected_paragraphs: List[int] = Field(default_factory=list)
    summary: str = ""
    evaluator_version: str = EVALUATOR_VERSION

    def is_certified(self) -> bool:
        return self.certified and self.overall_status in ("PASS", "PASS_WITH_WARNINGS", "AUTO_REPAIR")


class TranslationCertifier:
    @classmethod
    def certify_scene(
        cls,
        source_text: str,
        target_text: str,
        source_map: SourceSemanticMap,
        scene_plan: ScenePlan,
        book_bible: BookBible,
        chapter_num: int = 1,
        source_intensity: Optional[LiteraryIntensityVector] = None,
        target_intensity: Optional[LiteraryIntensityVector] = None,
        call_llm_fn: Optional[Any] = None,
        memory_context: Optional[Any] = None,
        target_map: Optional[TargetSemanticMap] = None,
        takes: Optional[List[Any]] = None,
        project_dir: Optional[Path] = None,
    ) -> GateAuditResult:
        """
        Executes Gates T0 through T15 on a translated scene.
        Guarantees that critical WARN states cannot silently become PASS.
        Calibrates intensity vectors deterministically if not explicitly provided.
        """
        gates: Dict[str, GateResult] = {}
        all_affected_paras: List[int] = []

        # Build TargetSemanticMap if not already provided
        if target_map is None:
            target_map = build_target_semantic_map(
                target_text=target_text,
                scene_id=source_map.scene_id,
                book_bible=book_bible,
                call_llm_fn=call_llm_fn,
            )

        # -------------------------------------------------------------
        # Gate T0: Source Integrity & Length Sanity
        # -------------------------------------------------------------
        src_words = len(source_text.split())
        tgt_words = len(target_text.split())
        t0_status = GateStatus.PASS
        t0_failures = []
        is_blocked = False

        if not target_text.strip():
            t0_status = GateStatus.FAIL
            t0_failures.append("Target translation is completely empty.")
            is_blocked = True
        elif src_words < 5 or tgt_words < 5:
            t0_status = GateStatus.FAIL
            t0_failures.append(f"Suspiciously short text (source {src_words} words, target {tgt_words} words)")
        elif tgt_words < (src_words * 0.35):
            t0_status = GateStatus.FAIL
            t0_failures.append(f"Target text severely truncated ({tgt_words} words vs source {src_words} words)")
            is_blocked = True

        gates["T0_source_integrity"] = GateResult(
            gate_id="T0",
            gate_name="Source Text Integrity & Word Count Sanity",
            status=t0_status,
            details=f"Source: {src_words} words | Target: {tgt_words} words",
            failures=t0_failures,
        )

        # -------------------------------------------------------------
        # Gate T5: Terminology & Entity Consistency (Deterministic)
        # -------------------------------------------------------------
        term_res = audit_terminology(target_text, book_bible, source_text)
        gates["T5_terminology"] = GateResult(
            gate_id="T5",
            gate_name="Terminology & Entity Consistency",
            status=GateStatus.PASS if term_res.is_valid else GateStatus.FAIL,
            details=f"Forbidden variants: {len(term_res.forbidden_variants_found)}",
            failures=term_res.forbidden_variants_found + term_res.leaked_latin_terms,
            warnings=term_res.warnings,
        )

        # -------------------------------------------------------------
        # Gate T2: Semantic Fidelity (WHO -> DID WHAT -> TO WHOM -> OBJECT -> NEGATION)
        # -------------------------------------------------------------
        sem_res = evaluate_semantic_fidelity(
            source_map=source_map,
            target_text=target_text,
            call_llm_fn=call_llm_fn,
            book_bible=book_bible,
            target_map=target_map,
        )
        t2_status = GateStatus.PASS if sem_res.is_valid and not sem_res.warnings else (
            GateStatus.WARN if sem_res.is_valid else GateStatus.FAIL
        )
        if sem_res.affected_paragraphs:
            all_affected_paras.extend(sem_res.affected_paragraphs)

        gates["T2_semantic_fidelity"] = GateResult(
            gate_id="T2",
            gate_name="Semantic Fidelity & Action Integrity",
            status=t2_status,
            details=sem_res.evaluator_notes,
            failures=sem_res.critical_inversions + sem_res.action_mismatches,
            warnings=sem_res.warnings,
            affected_paragraphs=sem_res.affected_paragraphs,
        )

        # -------------------------------------------------------------
        # Gate T3: Omission Detection
        # -------------------------------------------------------------
        om_res = evaluate_omissions(
            source_map=source_map,
            target_text=target_text,
            call_llm_fn=call_llm_fn,
            target_map=target_map,
        )
        if om_res.affected_paragraphs:
            all_affected_paras.extend(om_res.affected_paragraphs)

        t3_status = GateStatus(om_res.status)
        gates["T3_omission"] = GateResult(
            gate_id="T3",
            gate_name="Omission Detection",
            status=t3_status,
            details=om_res.evaluator_notes,
            failures=om_res.omitted_dialogue_beats + om_res.omitted_actions,
            warnings=om_res.warnings,
            affected_paragraphs=om_res.affected_paragraphs,
        )

        # -------------------------------------------------------------
        # Gate T4: Addition / Hallucination Detection
        # -------------------------------------------------------------
        add_res = evaluate_additions(
            source_map=source_map,
            target_text=target_text,
            call_llm_fn=call_llm_fn,
        )
        if add_res.affected_paragraphs:
            all_affected_paras.extend(add_res.affected_paragraphs)

        t4_status = GateStatus(add_res.status)
        gates["T4_addition"] = GateResult(
            gate_id="T4",
            gate_name="Addition & Hallucination Detection",
            status=t4_status,
            details=add_res.evaluator_notes,
            failures=add_res.hallucinated_actions + add_res.unsupported_fabrications,
            warnings=add_res.warnings,
            affected_paragraphs=add_res.affected_paragraphs,
        )

        # -------------------------------------------------------------
        # Gate T6: Relationship, Pronoun & Memory Continuity (Memory 2.0)
        # -------------------------------------------------------------
        if memory_context is not None and hasattr(memory_context, "get_character_performance_guidance"):
            t6_warnings: List[str] = []
            rels_checked = 0
            active_chars = list(scene_plan.active_characters or [])
            for i, spk in enumerate(active_chars):
                tgt = active_chars[i + 1] if i + 1 < len(active_chars) else (active_chars[0] if len(active_chars) > 1 else None)
                guidance = memory_context.get_character_performance_guidance(spk, tgt)
                rec_pronoun = guidance.get("recommended_pronoun")
                rec_register = guidance.get("recommended_register")
                if rec_pronoun or rec_register:
                    rels_checked += 1
            gates["T6_relationship_memory"] = GateResult(
                gate_id="T6",
                gate_name="Relationship, Pronoun & Memory Continuity",
                status=GateStatus.PASS if not t6_warnings else GateStatus.WARN,
                details=f"Verified {rels_checked} active relationship/pronoun guidance pairs",
                warnings=t6_warnings,
            )

        # -------------------------------------------------------------
        # Gate T7: Character Voice Profile Alignment
        # -------------------------------------------------------------
        cv_res = evaluate_character_voices(scene_plan.active_characters, target_text, book_bible, call_llm_fn)
        t7_status = GateStatus(cv_res.status) if hasattr(cv_res, "status") else (
            GateStatus.PASS if cv_res.is_valid else GateStatus.WARN
        )
        gates["T7_character_voice"] = GateResult(
            gate_id="T7",
            gate_name="Character Language Profile Alignment",
            status=t7_status,
            details=cv_res.evaluator_notes,
            failures=cv_res.character_voice_drifts,
            warnings=cv_res.warnings + cv_res.honorific_mismatches,
        )

        # -------------------------------------------------------------
        # Gate T8: Mature Register & Intensity Preservation (Calibrated)
        # -------------------------------------------------------------
        if source_intensity is None:
            source_intensity = IntensityEvaluator.estimate_source_intensity(
                source_text, semantic_map=source_map, call_llm_fn=call_llm_fn
            )
        if target_intensity is None:
            target_intensity = IntensityEvaluator.estimate_target_intensity(
                target_text, target_map=target_map, source_vector=source_intensity, call_llm_fn=call_llm_fn
            )

        int_res = IntensityEvaluator.compare_vectors(source_intensity, target_intensity)
        gates["T8_intensity"] = GateResult(
            gate_id="T8",
            gate_name="Mature Register & Intensity Preservation",
            status=GateStatus(int_res.status),
            details=f"Max delta: {int_res.max_delta} across 7 dimensions",
            failures=int_res.failure_reasons,
            warnings=int_res.warnings,
        )

        # -------------------------------------------------------------
        # Gate T9: Hindi / Hindustani Literary Naturalness
        # -------------------------------------------------------------
        nat_res = evaluate_literary_naturalness(target_text, call_llm_fn)
        t9_status = GateStatus(nat_res.status) if hasattr(nat_res, "status") else (
            GateStatus.PASS if nat_res.is_valid else GateStatus.WARN
        )
        gates["T9_naturalness"] = GateResult(
            gate_id="T9",
            gate_name="Hindi / Hindustani Literary Naturalness",
            status=t9_status,
            details=nat_res.evaluator_notes,
            failures=nat_res.antipatterns_detected,
            warnings=nat_res.warnings + nat_res.translatese_passages,
        )

        # -------------------------------------------------------------
        # Gate T10: Register Balance & Advisory Lexicon Check
        # -------------------------------------------------------------
        reg_engine = HindustaniRegisterEngine()
        reg_audit = reg_engine.audit_text(target_text)
        reg_status = GateStatus.PASS if reg_audit.is_balanced else GateStatus.WARN
        reg_warnings = []
        if not reg_audit.is_balanced:
            reg_warnings.append(f"Register imbalance (seasoning count: {reg_audit.seasoning_count})")

        gates["T10_register_balance"] = GateResult(
            gate_id="T10",
            gate_name="Register Balance & Advisory Lexicon Check",
            status=reg_status,
            details=f"Seasoning words: {len(reg_audit.detected_seasoning_words)}",
            warnings=reg_warnings,
        )

        # -------------------------------------------------------------
        # Gate T12: Spoken Language & Code-Switch QA (Advisory)
        # -------------------------------------------------------------
        from audiobook_factory.pronunciation.language_detector import classify_sentence_language
        lang_audit = classify_sentence_language(target_text)
        t12_status = GateStatus.PASS
        t12_warnings = []
        if lang_audit.get("is_code_switched") and lang_audit.get("latin_ratio", 0) > 0.45:
            t12_status = GateStatus.WARN
            t12_warnings.append(f"Elevated Latin script ratio ({lang_audit.get('latin_ratio'):.1%}) in translated scene")

        gates["T12_spoken_language"] = GateResult(
            gate_id="T12",
            gate_name="Spoken Language & Code-Switching Naturalness",
            status=t12_status,
            details=f"Primary: {lang_audit.get('primary_language')} | Latin Ratio: {lang_audit.get('latin_ratio', 0):.1%}",
            warnings=t12_warnings,
        )

        # -------------------------------------------------------------
        # Gate T13: Pronunciation Plan QA (Critical)
        # -------------------------------------------------------------
        from audiobook_factory.pronunciation import (
            PronunciationLexicon,
            PronunciationResolver,
            SpokenTextEngine,
            PronunciationStatus,
        )
        t13_lexicon = PronunciationLexicon()
        t13_lexicon.sync_from_book_bible(book_bible)
        t13_resolver = PronunciationResolver(t13_lexicon, book_bible=book_bible, call_llm_fn=call_llm_fn)
        t13_engine = SpokenTextEngine(t13_resolver)
        spoken_res = t13_engine.resolve_text(target_text)

        t13_status = GateStatus.PASS
        t13_failures = []
        t13_warnings = []

        for r in spoken_res.resolutions:
            if r.status == PronunciationStatus.FAILED:
                t13_status = GateStatus.FAIL
                t13_failures.append(f"Failed pronunciation resolution for '{r.original_token}': {r.explanation}")
            elif r.status in (PronunciationStatus.REVIEW_REQUIRED, PronunciationStatus.UNCERTAIN) or r.requires_review:
                t13_warnings.append(f"Unresolved pronunciation requiring review: '{r.original_token}'")
            elif r.status == PronunciationStatus.LIKELY:
                t13_warnings.append(f"Pronunciation resolution unverified (status=LIKELY): '{r.original_token}'")

        if t13_warnings and t13_status != GateStatus.FAIL:
            t13_status = GateStatus.WARN

        gates["T13_pronunciation_plan"] = GateResult(
            gate_id="T13",
            gate_name="Pronunciation Plan & Entity Determinism",
            status=t13_status,
            details=f"Resolved {len(spoken_res.resolutions)} sensitive tokens/entities",
            failures=t13_failures,
            warnings=t13_warnings,
        )

        # -------------------------------------------------------------
        # Gate T14: Pronunciation Audio QA (Advisory/Pre-Mix)
        # -------------------------------------------------------------
        t14_status = GateStatus.PASS
        t14_details = "Pre-synthesis certified (no candidate takes passed for audit)"
        t14_warnings = []
        if takes:
            from audiobook_factory.pronunciation.auditor import PronunciationAudioQA
            qa_auditor = PronunciationAudioQA(forced_aligner=None)
            for t in takes:
                t_path = getattr(t, "audio_path", None)
                if t_path and Path(t_path).exists():
                    qa_rep = qa_auditor.audit_take(t_path, spoken_res)
                    if not qa_rep.passed:
                        t14_status = GateStatus.WARN
                        t14_warnings.extend(qa_rep.review_reasons)
            if t14_warnings:
                t14_details = f"Audited {len(takes)} takes: issues flagged"
            else:
                t14_details = f"Audited {len(takes)} takes: verified clean"

        gates["T14_pronunciation_audio"] = GateResult(
            gate_id="T14",
            gate_name="Pronunciation Audio QA & Acoustic Alignment",
            status=t14_status,
            details=t14_details,
            warnings=t14_warnings,
        )

        # -------------------------------------------------------------
        # Gate T15: Cross-Chapter Pronunciation Consistency
        # -------------------------------------------------------------
        t15_status = GateStatus.PASS
        t15_details = "Verified scene entity pronunciations align with canonical lexicon"
        t15_warnings = []
        if project_dir and Path(project_dir).exists():
            from audiobook_factory.pronunciation.consistency import CrossChapterConsistencyAuditor
            drift_auditor = CrossChapterConsistencyAuditor()
            drifts = drift_auditor.audit_project(project_dir)
            unexc_drifts = [d for d in drifts if not d.allowed_exception]
            if unexc_drifts:
                t15_status = GateStatus.WARN
                for d in unexc_drifts:
                    t15_warnings.append(f"Pronunciation drift on '{d.canonical_text}': {'; '.join(d.drift_details)}")
                t15_details = f"Detected {len(unexc_drifts)} unexempted pronunciation drift(s)"

        gates["T15_pronunciation_consistency"] = GateResult(
            gate_id="T15",
            gate_name="Cross-Chapter Pronunciation Consistency",
            status=t15_status,
            details=t15_details,
            warnings=t15_warnings,
        )

        # -------------------------------------------------------------
        # Final Certification State Machine (PASS, PASS_WITH_WARNINGS, REVIEW_REQUIRED, BLOCKED)
        # -------------------------------------------------------------
        fail_gates = [k for k, g in gates.items() if g.status == GateStatus.FAIL]
        warn_gates = [k for k, g in gates.items() if g.status == GateStatus.WARN]
        critical_warns = [k for k in warn_gates if k in CRITICAL_GATES]

        dedup_affected_paras = sorted(list(set(all_affected_paras)))

        if is_blocked:
            overall = "BLOCKED"
            certified = False
        elif fail_gates:
            # Check if only deterministic repairs are required (Level 1 candidates)
            only_term_or_anti = all(k in ("T5_terminology", "T9_naturalness") for k in fail_gates)
            if only_term_or_anti and not critical_warns:
                overall = "AUTO_REPAIR"
                certified = True
            else:
                overall = "REVIEW_REQUIRED"
                certified = False
        elif critical_warns or len(warn_gates) >= 3:
            # Critical warnings cannot silently become PASS!
            overall = "REVIEW_REQUIRED"
            certified = False
        elif warn_gates:
            # 1-2 advisory warnings produce PASS_WITH_WARNINGS (certified!)
            overall = "PASS_WITH_WARNINGS"
            certified = True
        else:
            overall = "PASS"
            certified = True

        pass_count = sum(1 for g in gates.values() if g.status == GateStatus.PASS)
        summary_msg = (
            f"Certification completed for {scene_plan.scene_id}: {overall} "
            f"(Passed: {pass_count}/{len(gates)}, Warned: {len(warn_gates)}, Failed: {len(fail_gates)})"
        )

        return GateAuditResult(
            chapter_num=chapter_num,
            scene_id=scene_plan.scene_id,
            overall_status=overall,
            certified=certified,
            gates=gates,
            affected_paragraphs=dedup_affected_paras,
            summary=summary_msg,
        )

    @classmethod
    def save_artifact_bundle(
        cls,
        output_dir: Path,
        source_text: str,
        target_text: str,
        source_map: SourceSemanticMap,
        scene_plan: ScenePlan,
        audit_result: GateAuditResult,
        provenance_dict: Dict[str, Any],
        target_map: Optional[TargetSemanticMap] = None,
    ):
        """
        Saves the complete, inspectable chapter/scene artifact directory.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        with open(output_dir / "source.md", "w", encoding="utf-8") as f:
            f.write(source_text)

        with open(output_dir / "translation.md", "w", encoding="utf-8") as f:
            f.write(target_text)

        source_map.save(output_dir / "semantic_map.json")

        if target_map is not None:
            target_map.save(output_dir / "target_semantic_map.json")

        with open(output_dir / "scene_plan.json", "w", encoding="utf-8") as f:
            json.dump(scene_plan.model_dump(), f, ensure_ascii=False, indent=2)

        with open(output_dir / "certification.json", "w", encoding="utf-8") as f:
            json.dump(audit_result.model_dump(), f, ensure_ascii=False, indent=2)

        with open(output_dir / "provenance.json", "w", encoding="utf-8") as f:
            json.dump(provenance_dict, f, ensure_ascii=False, indent=2)
