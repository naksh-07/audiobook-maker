#!/usr/bin/env python3
"""
Audiobook Factory - Script Engine: Project Screenplay Batch Generator.
Processes all chapters in a project, orchestrates BookBible/Memory continuity,
and outputs chapter screenplay JSON files.
"""

from __future__ import annotations
import re
import json
import hashlib
import logging
from pathlib import Path
from typing import Optional, List

from audiobook_factory.script.normalizer import build_narrator_script
from audiobook_factory.script.dramatized_builder import build_dramatized_script_llm
from audiobook_factory.llm_client import call_gemini

logger = logging.getLogger("AudiobookFactory")


def generate_project_scripts(
    project_dir: Path,
    use_hindi: bool = False,
    dramatized: bool = False,
    overwrite: bool = False,
    chapters: Optional[List[int]] = None,
) -> Path:
    """Generates JSON screenplay scripts for all chapters in project."""
    project_dir = Path(project_dir).resolve()
    input_dir = project_dir / ("translation" if use_hindi else "extracted")
    scripts_dir = project_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)

    target_files = sorted(input_dir.glob("*.md"))
    if chapters:
        target_files = [
            tf for tf in target_files
            if any(f"_{ch:03d}" in tf.stem or tf.stem.endswith(f"_{ch}") or tf.stem == f"chapter_{ch:03d}" or tf.stem == f"chapter_{ch}" for ch in chapters)
        ]
    if not target_files:
        raise FileNotFoundError(f"No markdown chapters found in {input_dir}")

    # Load character roster from translation glossary or project registry if available
    roster = None
    roster_file = project_dir / "character_roster.json"
    glossary_file = project_dir / "translation" / "glossary.json"
    if roster_file.exists():
        try:
            with open(roster_file, "r", encoding="utf-8") as f:
                roster = json.load(f)
        except Exception:
            pass
    elif glossary_file.exists():
        try:
            with open(glossary_file, "r", encoding="utf-8") as f:
                glossary = json.load(f)
                roster = {"characters": {c["hindi_name"] if use_hindi and "hindi_name" in c else c.get("english_name", ""): {"aliases": [c.get("english_name", "")]} for c in glossary.get("characters", [])}}
        except Exception:
            pass

    # Load BookBible & MemoryStore 2.0 for screenplay continuity
    bible = None
    memory_store = None
    memory_store_path = None
    try:
        from audiobook_factory.translation.book_bible import BookBible
        from audiobook_factory.translation.memory import (
            MemoryStore,
            MemoryRetriever,
            EventExtractor,
        )
        bible = BookBible.load_from_project(project_dir)
        memory_store_path = MemoryStore.default_store_path(project_dir)
        memory_store = MemoryStore.load(memory_store_path, book_bible=bible)
    except Exception:
        pass

    # Enrich roster with BookBible canonical characters and all aliases
    if bible and bible.characters:
        if not roster or not isinstance(roster, dict):
            roster = {"characters": {}}
        elif "characters" not in roster:
            roster["characters"] = {}
        for c_name, c_ent in bible.characters.items():
            h_name = c_ent.hindi_name or c_name
            target_key = h_name if use_hindi else c_name
            existing = roster["characters"].get(target_key, {})
            current_aliases = set(existing.get("aliases", []))
            for a in c_ent.aliases + [c_name, h_name]:
                if a:
                    current_aliases.add(a)
            roster["characters"][target_key] = {
                "english_name": c_name,
                "gender": c_ent.gender or existing.get("gender", "male"),
                "aliases": sorted(list(current_aliases)),
            }
            if c_name not in roster["characters"]:
                roster["characters"][c_name] = roster["characters"][target_key]

    if dramatized:
        try:
            from audiobook_factory.dramaturgy.performance_bible import PerformanceBibleGenerator
            pb = PerformanceBibleGenerator.generate_bible_for_project(
                project_dir=project_dir,
                book_bible=bible,
                roster_data=roster,
            )
            pb.save_to_file(project_dir / "performance_bible.json")
        except Exception:
            pass

    dramaturgy_dir = project_dir / "dramaturgy"
    if dramatized:
        dramaturgy_dir.mkdir(parents=True, exist_ok=True)

    print(f"[*] Building audiobook scripts for {len(target_files)} chapters (Mode: {'Dramatized' if dramatized else 'Narrator'})...")

    for seq_idx, chap_file in enumerate(target_files, 1):
        m_ch = re.search(r"chapter_(\d+)", chap_file.stem, re.IGNORECASE)
        real_ch = int(m_ch.group(1)) if m_ch else seq_idx
        script_file = scripts_dir / f"{chap_file.stem}_script.json"
        if not overwrite and script_file.exists() and script_file.stat().st_size > 50:
            print(f"[-] Script already exists: {script_file.name} (Skipping)")
            continue

        with open(chap_file, "r", encoding="utf-8") as f:
            content = f.read()

        mem_ctx = None
        if memory_store is not None:
            try:
                from audiobook_factory.translation.memory import MemoryRetriever
                mem_ctx = MemoryRetriever.retrieve_for_scene(
                    store=memory_store,
                    book_bible=bible,
                    chapter=real_ch,
                    scene_id=chap_file.stem,
                    scene_text=content,
                )
            except Exception:
                mem_ctx = None

        if dramatized:
            script, d_plan, val_res = build_dramatized_script_llm(
                content,
                is_hindi=use_hindi,
                character_roster=roster,
                memory_context=mem_ctx,
                chapter_num=real_ch,
                chapter_id=chap_file.stem,
                return_dramatic_plan=True,
            )
            try:
                d_plan.save_to_file(dramaturgy_dir / f"{chap_file.stem}_dramatic_plan.json")
                val_res.save_to_file(dramaturgy_dir / f"{chap_file.stem}_validation.json")
            except Exception as e:
                logger.warning(f"  [!] Failed to save dramatic plan/validation for {chap_file.stem}: {e}")
        else:
            script = build_narrator_script(content, is_hindi=use_hindi)
            if mem_ctx is not None:
                script = [mem_ctx.apply_performance_guidance_to_segment(seg) for seg in script]

        # Attach source provenance hash to screenplay segments
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
        for seg in script:
            if isinstance(seg, dict) and "source_hash" not in seg:
                seg["source_hash"] = content_hash

        # Commit extracted screenplay events to MemoryStore if not already committed
        if memory_store is not None and memory_store_path is not None:
            try:
                from audiobook_factory.translation.memory import EventExtractor
                already_committed = any(c.scene_id == chap_file.stem for c in memory_store.commit_history)
                if not already_committed and content.strip():
                    known_chars = (
                        list(bible.characters.keys())
                        if bible and isinstance(bible.characters, dict)
                        else ([c.canonical_name for c in bible.characters] if bible else [])
                    )
                    from audiobook_factory.model_manager import TaskType
                    llm_wrapper = (
                        lambda prompt, system_instruction="", json_mode=True, **kw: json.dumps(
                            call_gemini(
                                prompt=f"{system_instruction}\n\n{prompt}",
                                task_type=TaskType.SCREENPLAY,
                                response_mime_type="application/json",
                            )
                        )
                    )
                    events, _ = EventExtractor.extract_scene_events(
                        scene_text=content,
                        chapter=real_ch,
                        scene_id=chap_file.stem,
                        known_characters=known_chars,
                        location=mem_ctx.location_name if mem_ctx else "Unspecified",
                        call_llm_fn=llm_wrapper,
                    )
                    memory_store.commit_scene_memory(
                        scene_id=chap_file.stem,
                        chapter=real_ch,
                        events=events,
                        source_text=content,
                        book_bible=bible,
                        location=mem_ctx.location_name if mem_ctx else "Unspecified",
                    )
                    memory_store.save(memory_store_path)
            except Exception:
                pass

        with open(script_file, "w", encoding="utf-8") as f:
            json.dump(script, f, ensure_ascii=False, indent=2)

        print(f"[+] Built script for {chap_file.name} -> {len(script)} audio segments")

    print(f"[DONE] All chapter scripts built -> {scripts_dir}")
    return scripts_dir
