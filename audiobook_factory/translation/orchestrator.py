#!/usr/bin/env python3
"""
Audiobook Factory - Literary Translation Intelligence Orchestrator.
Coordinates the entire Pillar 2 Translation Intelligence lifecycle:
Source -> Book Bible & Entity Discovery -> Scene Planner -> Structured Prompt ->
Gemini LLM -> Deterministic Pre-Validators -> Isolated Multi-Pass Evaluators (Gates T0-T11) ->
Tiered Self-Healing Repair -> Certified Hindi Novel Artifact.
"""

from __future__ import annotations
import os
import json
import time
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Callable

from .book_bible import BookBible
from .entity_discovery import EntityDiscoveryEngine
from .scene_planner import ScenePlanner, ScenePlan, ChapterPlan
from .narrative_state import NarrativeContinuityState, NarrativeStateEngine
from .source_semantic_map import (
    SourceSemanticMap,
    build_source_semantic_map,
    TargetSemanticMap,
    build_target_semantic_map,
    SEMANTIC_MAP_VERSION,
)
from .translation_policy import TranslationPolicyConfig, get_default_translation_policy
from .character_profile import get_character_profile
from .relationship_state import DynamicRelationshipState, RelationshipStateEngine
from .hindustani_register import HindustaniRegisterEngine
from .provenance import TranslationProvenanceTracker, TranslationProvenance
from .repair_engine import TieredRepairEngine, REPAIR_ENGINE_VERSION
from .certification import TranslationCertifier, GateAuditResult, EVALUATOR_VERSION
from .intensity_model import LiteraryIntensityVector, IntensityEvaluator
from .translation_memory import TranslationDecisionMemory
from .memory import (
    MemoryStore,
    MemoryRetriever,
    EventExtractor,
)

from audiobook_factory.sanitizer import validate_and_sanitize_translation

TRANSLATOR_VERSION = "2.0"
PROMPT_VERSION = "2.0.0"


class IntelligentTranslationPipeline:
    def __init__(
        self,
        project_dir: Path,
        model: str = "gemini-3.8-flash",
        policy: Optional[TranslationPolicyConfig] = None,
    ):
        self.project_dir = Path(project_dir).resolve()
        self.model = model
        self.policy = policy or get_default_translation_policy()
        self.book_bible = BookBible.load_from_project(self.project_dir)
        self.hindustani_engine = HindustaniRegisterEngine()
        self.decision_memory_path = self.project_dir / "translation" / "translation_decisions.json"
        self.decision_memory = TranslationDecisionMemory.load(self.decision_memory_path)
        self.memory_store_path = MemoryStore.default_store_path(self.project_dir)
        self.memory_store = MemoryStore.load(self.memory_store_path, book_bible=self.book_bible)
        self.narrative_state = NarrativeStateEngine.sync_from_memory_store(
            current_state=NarrativeContinuityState(),
            character_states=self.memory_store.character_states,
            world_state=self.memory_store.world_state,
            recent_events=list(self.memory_store.events.values())[-5:],
        )

    def _get_known_character_names(self) -> List[str]:
        if isinstance(self.book_bible.characters, dict):
            return list(self.book_bible.characters.keys())
        return [c.canonical_name for c in self.book_bible.characters]

    def _extract_and_commit_scene_memory(
        self,
        scene: ScenePlan,
        chapter_num: int,
        call_llm_fn: Optional[Callable[..., str]] = None,
    ) -> None:
        """
        Executes EXTRACT -> CALCULATE DELTAS -> VALIDATE -> COMMIT for a completed scene.
        Skips duplicate commit if the exact (chapter_num, scene_id) is already recorded.
        """
        already_committed = any(
            c.chapter == chapter_num and c.scene_id == scene.scene_id
            for c in self.memory_store.commit_history
        )
        if already_committed:
            return

        known_chars = self._get_known_character_names()
        events, assessment = EventExtractor.extract_scene_events(
            scene_text=scene.text_block,
            chapter=chapter_num,
            scene_id=scene.scene_id,
            known_characters=known_chars or scene.active_characters,
            location=scene.location,
            call_llm_fn=call_llm_fn,
            model=self.model,
        )
        val_report = self.memory_store.commit_scene_memory(
            scene_id=scene.scene_id,
            chapter=chapter_num,
            events=events,
            source_text=scene.text_block,
            book_bible=self.book_bible,
            location=scene.location,
            time_marker=getattr(scene, "time", "Unspecified"),
        )
        self.memory_store.save(self.memory_store_path)
        self.book_bible.save(self.project_dir)

        self.narrative_state = NarrativeStateEngine.sync_from_memory_store(
            current_state=self.narrative_state,
            character_states=self.memory_store.character_states,
            world_state=self.memory_store.world_state,
            recent_events=events,
            active_characters=scene.active_characters,
            location=scene.location,
        )
        if val_report.flagged_conflicts:
            print(
                f"    [MEMORY VALIDATOR] {len(val_report.flagged_conflicts)} conflict(s) rejected; "
                f"{len(val_report.accepted_deltas)} delta(s) committed (v{self.memory_store.memory_version})."
            )

    def translate_chapter(
        self,
        chapter_text: str,
        chapter_num: int = 1,
        chapter_title: str = "Chapter",
        call_llm_fn: Optional[Callable[..., str]] = None,
        use_cache: bool = True,
        force_gate: bool = False,
    ) -> Tuple[str, List[GateAuditResult]]:
        """
        Executes autonomous scene-by-scene translation, QA certification, repair, and Memory 2.0 updates.
        Emits top-level chapter_XXX_hi.md and granular scene artifacts.
        """
        if call_llm_fn is None:
            from audiobook_factory.translator import call_gemini
            call_llm_fn = call_gemini

        print(f"\n{'=' * 80}")
        print(f"  LITERARY TRANSLATION INTELLIGENCE ENGINE: {chapter_title} (Ch {chapter_num})")
        print(f"  Model: {self.model} | Policy Version: {self.policy.version} | Book: {self.book_bible.book_title}")
        print(f"{'=' * 80}\n")

        # 1. Entity Discovery
        print(f"[*] Step 1: Running Entity Discovery Engine on {chapter_title}...")
        discovered = EntityDiscoveryEngine.discover_entities_from_text(
            text=chapter_text,
            book_bible=self.book_bible,
            chapter_num=chapter_num,
        )
        committed, flagged = EntityDiscoveryEngine.reconcile_and_commit(
            discovered=discovered,
            book_bible=self.book_bible,
            chapter_num=chapter_num,
        )
        if committed > 0 or flagged > 0:
            print(f"    [+] Entity Discovery: {committed} new entities committed, {flagged} flagged conflicts.")
            self.book_bible.save(self.project_dir)

        self.memory_store.seed_from_book_bible(self.book_bible)
        known_chars = self._get_known_character_names()

        # 2. Transition-Driven Scene Planning
        print(f"[*] Step 2: Transition-Driven Scene Segmentation...")
        chapter_plan = ScenePlanner.plan_chapter(
            chapter_text=chapter_text,
            chapter_title=chapter_title,
            known_characters=known_chars,
        )
        print(f"    [+] Chapter segmented into {len(chapter_plan.scenes)} dramatic scenes (Total Words: {chapter_plan.total_words}).")

        # Prepare artifact directories
        trans_dir = self.project_dir / "translation"
        trans_dir.mkdir(parents=True, exist_ok=True)
        chapter_artifact_dir = trans_dir / f"chapter_{chapter_num:03d}"
        chapter_artifact_dir.mkdir(parents=True, exist_ok=True)

        translated_scenes: List[str] = []
        scene_audit_results: List[GateAuditResult] = []

        bible_hash = self.book_bible.get_version_hash()
        pron_hash = ""
        try:
            from audiobook_factory.pronunciation.provenance import PronunciationProvenanceTracker
            pron_lex = self.book_bible.sync_pronunciation_lexicon(self.project_dir)
            pron_hash = PronunciationProvenanceTracker.compute_lexicon_hash(pron_lex.entries)
        except Exception:
            pron_hash = ""

        # 3. Scene-by-Scene Translation Lifecycle
        for s_idx, scene in enumerate(chapter_plan.scenes, 1):
            scene_dir = chapter_artifact_dir / scene.scene_id
            scene_dir.mkdir(parents=True, exist_ok=True)

            print(f"\n[*] [Scene {s_idx}/{len(chapter_plan.scenes)}] {scene.scene_title} ({len(scene.text_block.split())} words)...")

            # STEP 1 (READ): Selective Memory Retrieval
            memory_ctx = MemoryRetriever.retrieve_for_scene(
                store=self.memory_store,
                book_bible=self.book_bible,
                chapter=chapter_num,
                scene_id=scene.scene_id,
                active_characters=scene.active_characters,
                location=scene.location,
                scene_text=scene.text_block,
            )

            # A. Build persistent SourceSemanticMap (Check version freshness)
            semantic_map_path = scene_dir / "semantic_map.json"
            expected_src_hash = hashlib.sha256(scene.text_block.encode("utf-8")).hexdigest()[:16]
            source_map = None

            if semantic_map_path.exists():
                try:
                    loaded_map = SourceSemanticMap.load(semantic_map_path)
                    if (
                        getattr(loaded_map, "source_hash", "") == expected_src_hash
                        and getattr(loaded_map, "semantic_map_version", "") == SEMANTIC_MAP_VERSION
                    ):
                        source_map = loaded_map
                except Exception:
                    source_map = None

            if source_map is None:
                source_map = build_source_semantic_map(
                    scene_text=scene.text_block,
                    scene_id=scene.scene_id,
                    known_entities=known_chars,
                    call_llm_fn=call_llm_fn,
                )
                source_map.save(semantic_map_path)

            sem_map_hash = hashlib.sha256(source_map.model_dump_json().encode("utf-8")).hexdigest()[:16]

            # Estimate source intensity (calibrated)
            source_intensity = IntensityEvaluator.estimate_source_intensity(
                source_text=scene.text_block,
                semantic_map=source_map,
                call_llm_fn=call_llm_fn,
            )

            # B. Check Provenance Cache
            cache_file = scene_dir / "translation.md"
            prov_file = scene_dir / "provenance.json"
            comp_key = TranslationProvenanceTracker.generate_composite_key(
                source_text=scene.text_block,
                bible_version_hash=bible_hash,
                policy_version=self.policy.version,
                prompt_version=PROMPT_VERSION,
                model=self.model,
                translator_version=TRANSLATOR_VERSION,
                evaluator_version=EVALUATOR_VERSION,
                semantic_map_version=SEMANTIC_MAP_VERSION,
                semantic_map_hash=sem_map_hash,
                repair_version=REPAIR_ENGINE_VERSION,
                pronunciation_version="1.0",
                pronunciation_hash=pron_hash,
            )

            if use_cache and cache_file.exists() and TranslationProvenanceTracker.is_cache_valid(prov_file, comp_key):
                with open(cache_file, "r", encoding="utf-8") as f:
                    translated_text = f.read()
                print(f"    [CACHED] Scene loaded from valid certified provenance cache ({len(translated_text)} chars).")
                self._extract_and_commit_scene_memory(scene, chapter_num, call_llm_fn=None)
                translated_scenes.append(translated_text)
                continue

            # C. Construct Contextual Instructions
            policy_prompt = self.policy.get_prompt_instructions()
            hindustani_prompt = self.hindustani_engine.get_prompt_guidelines()
            scene_context = scene.get_prompt_context()
            narrative_context = self.narrative_state.get_prompt_context()
            memory_prompt_block = memory_ctx.get_prompt_context()

            char_profiles_prompt = "\n\n".join(
                get_character_profile(c, self.book_bible).get_prompt_guidelines()
                for c in scene.active_characters
            ) if scene.active_characters else "No specific character profiles present."

            canonical_lexicon = self.book_bible.get_canonical_lexicon()
            relevant_lexicon = {
                k: v for k, v in canonical_lexicon.items()
                if k.lower() in scene.text_block.lower()
            }
            for concept_key, dec in self.decision_memory.decisions.items():
                if concept_key in scene.text_block.lower():
                    relevant_lexicon.setdefault(dec.source_concept, dec.chosen_translation)
            lexicon_str = json.dumps(relevant_lexicon, ensure_ascii=False, indent=2)

            system_instruction = (
                f"You are a master literary translator rendering European dark-fantasy literature into "
                f"unapologetic, publication-grade literary Hindustani (Hindi in Devanagari script).\n\n"
                f"{policy_prompt}\n\n"
                f"{hindustani_prompt}\n\n"
                f"### ACTIVE CHARACTER PROFILES:\n{char_profiles_prompt}"
            )

            prompt = f"""### CANONICAL TERMINOLOGY & PROPER NOUNS:
{lexicon_str}

### PRECEDING NARRATIVE CONTINUITY:
{narrative_context}

### SELECTIVE SCENE MEMORY & EPISTEMIC CONSTRAINTS:
{memory_prompt_block}

### SCENE METADATA:
{scene_context}

### ENGLISH TEXT TO TRANSLATE ({scene.scene_title}):
\"\"\"
{scene.text_block}
\"\"\"
"""
            # D. Dispatch Translation LLM Call (ACT)
            t0 = time.time()
            raw_target = call_llm_fn(
                prompt=prompt,
                system_instruction=system_instruction,
                model=self.model,
                json_mode=False,
            ).strip()
            dur = time.time() - t0
            print(f"    [+] Scene translated in {dur:.1f}s ({len(raw_target)} chars)")

            # E. Sanitize
            is_valid, cleaned_target, reason = validate_and_sanitize_translation(raw_target, is_hindi=True)
            if not is_valid:
                print(f"    [!] Warning: Sanitizer note: {reason}")
                cleaned_target = raw_target

            # F. Deterministic Level 1 Repair
            cleaned_target, rep_actions = TieredRepairEngine.apply_deterministic_repair(
                cleaned_target,
                terminology_variants=self.book_bible.terminology_variants,
            )
            if rep_actions:
                for act in rep_actions:
                    print(f"    [AUTO-REPAIR L1] {act.details}")

            # G. Build TargetSemanticMap and Initial Certification
            target_map = build_target_semantic_map(
                target_text=cleaned_target,
                scene_id=scene.scene_id,
                book_bible=self.book_bible,
                call_llm_fn=call_llm_fn,
            )

            target_intensity = IntensityEvaluator.estimate_target_intensity(
                target_text=cleaned_target,
                target_map=target_map,
                source_vector=source_intensity,
                call_llm_fn=call_llm_fn,
            )

            audit_result = TranslationCertifier.certify_scene(
                source_text=scene.text_block,
                target_text=cleaned_target,
                source_map=source_map,
                scene_plan=scene,
                book_bible=self.book_bible,
                chapter_num=chapter_num,
                source_intensity=source_intensity,
                target_intensity=target_intensity,
                call_llm_fn=call_llm_fn,
                memory_context=memory_ctx,
                target_map=target_map,
            )

            # H. Multi-Tiered Self-Healing Repair (Fix 5)
            if not audit_result.certified:
                print(f"    [!] Certification Alert ({audit_result.overall_status}). Initiating Tiered Repair Engine...")
                paras_src = [p.strip() for p in scene.text_block.split("\n\n") if p.strip()]
                paras_tgt = [p.strip() for p in cleaned_target.split("\n\n") if p.strip()]

                # Level 2: Paragraph-level repair (up to MAX_PARAGRAPH_ATTEMPTS = 2)
                p_attempts = 0
                while p_attempts < TieredRepairEngine.MAX_PARAGRAPH_ATTEMPTS and not audit_result.certified:
                    rep_level, target_indices, reasons = TieredRepairEngine.plan_repair(
                        audit_report=audit_result,
                        total_paragraphs=len(paras_tgt),
                        paragraph_attempts_taken=p_attempts,
                    )
                    if rep_level != "PARAGRAPH_REWRITE" or not target_indices:
                        break

                    p_attempts += 1
                    print(f"    [REPAIR L2: Attempt {p_attempts}/2] Repairing paragraphs {target_indices}...")

                    for t_idx in target_indices:
                        if 0 <= t_idx < len(paras_tgt):
                            # Map target paragraph index to source paragraph index proportionally
                            if paras_src and paras_tgt:
                                s_idx = min(int(round(t_idx * (len(paras_src) / len(paras_tgt)))), len(paras_src) - 1)
                            else:
                                s_idx = 0
                            src_p = paras_src[s_idx]
                            tgt_p = paras_tgt[t_idx]
                            
                            rep_p, ok = TieredRepairEngine.repair_paragraph(
                                source_paragraph=src_p,
                                current_target_paragraph=tgt_p,
                                failure_reason="; ".join(reasons) if reasons else "Fidelity improvement",
                                call_llm_fn=call_llm_fn,
                            )
                            if ok:
                                is_clean_p, clean_p, _ = validate_and_sanitize_translation(rep_p, is_hindi=True)
                                paras_tgt[t_idx] = clean_p if is_clean_p else rep_p

                    cleaned_target = "\n\n".join(paras_tgt)
                    # Re-run Level 1 cleanup on reassembled text
                    cleaned_target, _ = TieredRepairEngine.apply_deterministic_repair(
                        cleaned_target,
                        terminology_variants=self.book_bible.terminology_variants,
                    )
                    # Re-evaluate TargetSemanticMap & Certification
                    target_map = build_target_semantic_map(
                        target_text=cleaned_target,
                        scene_id=scene.scene_id,
                        book_bible=self.book_bible,
                        call_llm_fn=call_llm_fn,
                    )
                    target_intensity = IntensityEvaluator.estimate_target_intensity(
                        target_text=cleaned_target,
                        target_map=target_map,
                        source_vector=source_intensity,
                        call_llm_fn=call_llm_fn,
                    )
                    audit_result = TranslationCertifier.certify_scene(
                        source_text=scene.text_block,
                        target_text=cleaned_target,
                        source_map=source_map,
                        scene_plan=scene,
                        book_bible=self.book_bible,
                        chapter_num=chapter_num,
                        source_intensity=source_intensity,
                        target_intensity=target_intensity,
                        call_llm_fn=call_llm_fn,
                        memory_context=memory_ctx,
                        target_map=target_map,
                    )
                    if audit_result.certified:
                        print(f"        [+] Level 2 repair succeeded on attempt {p_attempts}.")
                        break

                # Level 3: Full Scene Retranslation (up to MAX_SCENE_ATTEMPTS = 1)
                if not audit_result.certified:
                    rep_level, _, scene_reasons = TieredRepairEngine.plan_repair(
                        audit_report=audit_result,
                        total_paragraphs=len(paras_tgt),
                        paragraph_attempts_taken=p_attempts,
                    )
                    print(f"    [REPAIR L3: Scene Retranslation] Escalating to full scene rewrite...")
                    scene_repair_prompt = TieredRepairEngine.build_scene_repair_prompt(
                        source_scene=scene.text_block,
                        flawed_scene=cleaned_target,
                        failure_reasons=scene_reasons,
                        base_prompt=prompt,
                    )
                    try:
                        raw_retranslated = call_llm_fn(
                            prompt=scene_repair_prompt,
                            system_instruction=system_instruction,
                            model=self.model,
                            json_mode=False,
                        ).strip()
                        is_val_s, clean_s, _ = validate_and_sanitize_translation(raw_retranslated, is_hindi=True)
                        candidate_scene = clean_s if is_val_s else raw_retranslated
                        candidate_scene, _ = TieredRepairEngine.apply_deterministic_repair(
                            candidate_scene,
                            terminology_variants=self.book_bible.terminology_variants,
                        )
                        # Re-certify candidate scene
                        target_map_cand = build_target_semantic_map(
                            target_text=candidate_scene,
                            scene_id=scene.scene_id,
                            book_bible=self.book_bible,
                            call_llm_fn=call_llm_fn,
                        )
                        target_int_cand = IntensityEvaluator.estimate_target_intensity(
                            target_text=candidate_scene,
                            target_map=target_map_cand,
                            source_vector=source_intensity,
                            call_llm_fn=call_llm_fn,
                        )
                        audit_cand = TranslationCertifier.certify_scene(
                            source_text=scene.text_block,
                            target_text=candidate_scene,
                            source_map=source_map,
                            scene_plan=scene,
                            book_bible=self.book_bible,
                            chapter_num=chapter_num,
                            source_intensity=source_intensity,
                            target_intensity=target_int_cand,
                            call_llm_fn=call_llm_fn,
                            memory_context=memory_ctx,
                            target_map=target_map_cand,
                        )
                        if audit_cand.certified or len(audit_cand.affected_paragraphs) < len(audit_result.affected_paragraphs):
                            cleaned_target = candidate_scene
                            target_map = target_map_cand
                            audit_result = audit_cand
                            print("        [+] Level 3 full-scene repair completed.")
                    except Exception as e:
                        print(f"        [!] Level 3 repair notice: {e}")

                # Post-Repair Policy Enforcement (Decision A2)
                if audit_result.overall_status == "BLOCKED" and not force_gate:
                    raise RuntimeError(
                        f"Scene {scene.scene_id} certification BLOCKED: {audit_result.summary}"
                    )
                elif audit_result.overall_status == "REVIEW_REQUIRED":
                    print(
                        f"    [!] REVIEW_REQUIRED: Proceeding with best repaired translation. "
                        f"Details saved to {scene_dir / 'certification.json'}."
                    )

            status_color = "[CERTIFIED]" if audit_result.certified else f"[{audit_result.overall_status}]"
            print(f"    {status_color} {audit_result.summary}")

            # I. Save Artifacts & Full 11-Component Provenance
            prov_dict = {
                "source_hash": source_map.source_hash,
                "bible_version_hash": bible_hash,
                "policy_version": self.policy.version,
                "prompt_version": PROMPT_VERSION,
                "translator_version": TRANSLATOR_VERSION,
                "evaluator_version": EVALUATOR_VERSION,
                "semantic_map_version": SEMANTIC_MAP_VERSION,
                "semantic_map_hash": sem_map_hash,
                "repair_version": REPAIR_ENGINE_VERSION,
                "model": self.model,
                "pronunciation_version": "1.0",
                "pronunciation_hash": pron_hash,
                "composite_cache_key": comp_key,
                "memory_version": self.memory_store.memory_version,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "chapter_num": chapter_num,
                "scene_id": scene.scene_id,
                "certified": audit_result.certified,
                "certification_status": audit_result.overall_status,
            }

            TranslationCertifier.save_artifact_bundle(
                output_dir=scene_dir,
                source_text=scene.text_block,
                target_text=cleaned_target,
                source_map=source_map,
                scene_plan=scene,
                audit_result=audit_result,
                provenance_dict=prov_dict,
                target_map=target_map,
            )

            # J. Update Narrative Continuity State & Commit Scene Memory 2.0
            scene_summary = f"{scene.scene_title}: {scene.location}, active: {', '.join(scene.active_characters)}"
            self.narrative_state = NarrativeStateEngine.update_from_scene_completion(
                current_state=self.narrative_state,
                scene_summary=scene_summary,
                active_characters=scene.active_characters,
                location=scene.location,
            )
            self._extract_and_commit_scene_memory(scene, chapter_num, call_llm_fn=call_llm_fn)

            translated_scenes.append(cleaned_target)
            scene_audit_results.append(audit_result)

        # 4. Assemble Full Chapter and Emit Top-Level & Chapter Artifacts (Decision A1)
        full_chapter_hindi = "\n\n".join(translated_scenes)
        
        # Save chapter-level markdown files atomically
        chapter_md_path = chapter_artifact_dir / f"chapter_{chapter_num:03d}_hi.md"
        top_level_md_path = trans_dir / f"chapter_{chapter_num:03d}_hi.md"
        
        tmp_chapter_md = chapter_artifact_dir / f"chapter_{chapter_num:03d}_hi.md.tmp"
        tmp_top_md = trans_dir / f"chapter_{chapter_num:03d}_hi.md.tmp"
        
        with open(tmp_chapter_md, "w", encoding="utf-8") as f:
            f.write(full_chapter_hindi + "\n")
        os.replace(tmp_chapter_md, chapter_md_path)

        with open(tmp_top_md, "w", encoding="utf-8") as f:
            f.write(full_chapter_hindi + "\n")
        os.replace(tmp_top_md, top_level_md_path)

        print(f"[+] Chapter {chapter_num} fully assembled and saved -> {top_level_md_path}")
        return full_chapter_hindi, scene_audit_results
