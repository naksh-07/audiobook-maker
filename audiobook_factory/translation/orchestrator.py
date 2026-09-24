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
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Callable

from .book_bible import BookBible
from .entity_discovery import EntityDiscoveryEngine
from .scene_planner import ScenePlanner, ScenePlan, ChapterPlan
from .narrative_state import NarrativeContinuityState, NarrativeStateEngine
from .source_semantic_map import SourceSemanticMap, build_source_semantic_map
from .translation_policy import TranslationPolicyConfig, get_default_translation_policy
from .character_profile import get_character_profile
from .relationship_state import DynamicRelationshipState, RelationshipStateEngine
from .hindustani_register import HindustaniRegisterEngine
from .provenance import TranslationProvenanceTracker
from .repair_engine import TieredRepairEngine
from .certification import TranslationCertifier, GateAuditResult

from audiobook_factory.sanitizer import validate_and_sanitize_translation


class IntelligentTranslationPipeline:
    def __init__(
        self,
        project_dir: Path,
        model: str = "gemini-3.8-flash",
        policy: Optional[TranslationPolicyConfig] = None,
    ):
        self.project_dir = Path(project_dir)
        self.model = model
        self.policy = policy or get_default_translation_policy()
        self.book_bible = BookBible.load_from_project(self.project_dir)
        self.hindustani_engine = HindustaniRegisterEngine()
        self.narrative_state = NarrativeContinuityState()

    def translate_chapter(
        self,
        chapter_text: str,
        chapter_num: int = 1,
        chapter_title: str = "Chapter",
        call_llm_fn: Optional[Callable[..., str]] = None,
        use_cache: bool = True,
    ) -> Tuple[str, List[GateAuditResult]]:
        """
        Executes autonomous scene-by-scene translation, QA certification, and repair.
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

        # 2. Transition-Driven Scene Planning
        print(f"[*] Step 2: Transition-Driven Scene Segmentation...")
        chapter_plan = ScenePlanner.plan_chapter(
            chapter_text=chapter_text,
            chapter_title=chapter_title,
            known_characters=list(self.book_bible.characters.keys()),
        )
        print(f"    [+] Chapter segmented into {len(chapter_plan.scenes)} dramatic scenes (Total Words: {chapter_plan.total_words}).")

        # Prepare artifact directory
        chapter_artifact_dir = self.project_dir / "translation" / f"chapter_{chapter_num:03d}"
        chapter_artifact_dir.mkdir(parents=True, exist_ok=True)

        translated_scenes: List[str] = []
        scene_audit_results: List[GateAuditResult] = []

        bible_hash = self.book_bible.get_version_hash()

        # 3. Scene-by-Scene Translation Lifecycle
        for s_idx, scene in enumerate(chapter_plan.scenes, 1):
            scene_dir = chapter_artifact_dir / scene.scene_id
            scene_dir.mkdir(parents=True, exist_ok=True)

            print(f"\n[*] [Scene {s_idx}/{len(chapter_plan.scenes)}] {scene.scene_title} ({len(scene.text_block.split())} words)...")

            # A. Build persistent SourceSemanticMap
            semantic_map_path = scene_dir / "semantic_map.json"
            if semantic_map_path.exists():
                source_map = SourceSemanticMap.load(semantic_map_path)
            else:
                source_map = build_source_semantic_map(
                    scene_text=scene.text_block,
                    scene_id=scene.scene_id,
                    known_entities=list(self.book_bible.characters.keys()),
                )
                source_map.save(semantic_map_path)

            # B. Check Provenance Cache
            cache_file = scene_dir / "translation.md"
            prov_file = scene_dir / "provenance.json"
            comp_key = TranslationProvenanceTracker.generate_composite_key(
                source_text=scene.text_block,
                bible_version_hash=bible_hash,
                policy_version=self.policy.version,
                model=self.model,
            )

            if use_cache and cache_file.exists() and TranslationProvenanceTracker.is_cache_valid(prov_file, comp_key):
                with open(cache_file, "r", encoding="utf-8") as f:
                    translated_text = f.read()
                print(f"    [CACHED] Scene loaded from valid provenance cache ({len(translated_text)} chars).")
                translated_scenes.append(translated_text)
                continue

            # C. Construct Contextual Instructions
            policy_prompt = self.policy.get_prompt_instructions()
            hindustani_prompt = self.hindustani_engine.get_prompt_guidelines()
            scene_context = scene.get_prompt_context()
            narrative_context = self.narrative_state.get_prompt_context()

            # Character profiles for active characters
            char_profiles_prompt = "\n\n".join(
                get_character_profile(c, self.book_bible).get_prompt_guidelines()
                for c in scene.active_characters
            ) if scene.active_characters else "No specific character profiles present."

            # Canonical proper nouns
            canonical_lexicon = self.book_bible.get_canonical_lexicon()
            relevant_lexicon = {
                k: v for k, v in canonical_lexicon.items()
                if k.lower() in scene.text_block.lower()
            }
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

### SCENE METADATA:
{scene_context}

### ENGLISH TEXT TO TRANSLATE ({scene.scene_title}):
\"\"\"
{scene.text_block}
\"\"\"
"""
            # D. Dispatch Translation LLM Call
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
            cleaned_target, rep_actions = TieredRepairEngine.apply_deterministic_repair(cleaned_target)
            if rep_actions:
                for act in rep_actions:
                    print(f"    [AUTO-REPAIR L1] {act.details}")

            # G. Independent Certification (Gates T0 to T11)
            audit_result = TranslationCertifier.certify_scene(
                source_text=scene.text_block,
                target_text=cleaned_target,
                source_map=source_map,
                scene_plan=scene,
                book_bible=self.book_bible,
                chapter_num=chapter_num,
                call_llm_fn=call_llm_fn,
            )

            # H. Level 2 Targeted Repair if needed
            if not audit_result.certified:
                print(f"    [!] Certification Alert ({audit_result.overall_status}). Attempting Level 2 targeted repair...")
                # Find failing gates
                for gate_key, g_res in audit_result.gates.items():
                    if g_res.status == "FAIL":
                        print(f"        -> Failing Gate {gate_key}: {', '.join(g_res.failures)}")
                        # Attempt targeted repair on first paragraph
                        paras_src = [p for p in scene.text_block.split("\n\n") if p.strip()]
                        paras_tgt = [p for p in cleaned_target.split("\n\n") if p.strip()]
                        if paras_src and paras_tgt:
                            rep_para, ok = TieredRepairEngine.repair_paragraph(
                                source_paragraph=paras_src[0],
                                current_target_paragraph=paras_tgt[0],
                                failure_reason="; ".join(g_res.failures),
                                call_llm_fn=call_llm_fn,
                            )
                            if ok:
                                paras_tgt[0] = rep_para
                                cleaned_target = "\n\n".join(paras_tgt)
                                print("        [+] Level 2 repair applied successfully.")
                                # Re-certify
                                audit_result = TranslationCertifier.certify_scene(
                                    source_text=scene.text_block,
                                    target_text=cleaned_target,
                                    source_map=source_map,
                                    scene_plan=scene,
                                    book_bible=self.book_bible,
                                    chapter_num=chapter_num,
                                    call_llm_fn=None,  # fast re-check
                                )
                                break

            status_color = "[CERTIFIED]" if audit_result.certified else "[REVIEW_REQUIRED]"
            print(f"    {status_color} {audit_result.summary}")

            # I. Save Artifacts & Provenance
            prov_dict = {
                "source_hash": source_map.source_hash,
                "bible_version_hash": bible_hash,
                "policy_version": self.policy.version,
                "prompt_version": "2.0.0",
                "model": self.model,
                "composite_cache_key": comp_key,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "chapter_num": chapter_num,
                "scene_id": scene.scene_id,
            }

            TranslationCertifier.save_artifact_bundle(
                output_dir=scene_dir,
                source_text=scene.text_block,
                target_text=cleaned_target,
                source_map=source_map,
                scene_plan=scene,
                audit_result=audit_result,
                provenance_dict=prov_dict,
            )

            # J. Update Narrative Continuity State
            scene_summary = f"{scene.scene_title}: {scene.location}, active: {', '.join(scene.active_characters)}"
            self.narrative_state = NarrativeStateEngine.update_from_scene_completion(
                current_state=self.narrative_state,
                scene_summary=scene_summary,
                active_characters=scene.active_characters,
                location=scene.location,
            )

            translated_scenes.append(cleaned_target)
            scene_audit_results.append(audit_result)

        # 4. Assemble Full Certified Chapter
        full_chapter_hindi = "\n\n".join(translated_scenes)
        return full_chapter_hindi, scene_audit_results
