#!/usr/bin/env python3
"""
Audiobook Factory - Room 1: Pre-Production Supervisor.
Coordinates the Pre-Production Studio agents to establish locked novel master state:
1. book_bible.json: Authoritative lore, characters, locations, and relationships.
2. sonic_bible.json: Acoustic DNA, room impulse reverb targets, and signature foley palettes.
3. cast_lock.json: Collision-free voice actor assignments locked for the entire novel.

Guarantees one-time master execution per novel with zero voice drift across chapters.
"""

from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Callable

from audiobook_factory.translation.book_bible import BookBible, BookEntity
from audiobook_factory.character_caster import CharacterCaster
from .novel_deepsearch import NovelDeepSearchEngine, DeepSearchNovelDossier
from .book_dna_agent import BookDNAAgent
from .dramatis_personae_agent import DramatisPersonaeAgent
from .sonic_world_architect import SonicWorldArchitect
from .phonetic_lexicon_dramaturge import PhoneticLexiconDramaturge

logger = logging.getLogger("AudiobookFactory")


class PreProductionSupervisor:
    """Room 1 Showrunner: Coordinates full-novel lore, acoustic DNA, and voice locking."""

    def __init__(self, model: Optional[str] = None):
        self.model = model
        self.deepsearch = NovelDeepSearchEngine(model=model)
        self.book_dna_agent = BookDNAAgent(model=model)
        self.dramatis_personae_agent = DramatisPersonaeAgent(model=model)
        self.sonic_architect = SonicWorldArchitect(model=model)
        self.lexicon_dramaturge = PhoneticLexiconDramaturge(model=model)

    def execute_preproduction(
        self,
        project_dir: Path | str,
        force: bool = False,
        call_llm_fn: Optional[Callable[..., Any]] = None,
    ) -> Dict[str, Any]:
        """Executes one-time pre-production master pass for the novel."""
        p_dir = Path(project_dir).resolve()
        book_dna_path = p_dir / "book_dna.json"
        book_bible_path = p_dir / "book_bible.json"
        sonic_bible_path = p_dir / "sonic_bible.json"
        cast_lock_path = p_dir / "cast_lock.json"
        meta_path = p_dir / "metadata.json"

        # Check existing master state
        if not force and book_dna_path.exists() and book_bible_path.exists() and sonic_bible_path.exists() and cast_lock_path.exists():
            logger.info(f"[*] PreProductionSupervisor: Master novel state already locked for {p_dir.name}. Skipping.")
            return {
                "status": "CACHED_LOCKED",
                "book_dna": str(book_dna_path),
                "book_bible": str(book_bible_path),
                "sonic_bible": str(sonic_bible_path),
                "cast_lock": str(cast_lock_path),
            }

        logger.info(f"[*] PreProductionSupervisor: Commencing One-Time Pre-Production Master Room for '{p_dir.name}'...")

        book_metadata: Dict[str, Any] = {}
        if meta_path.exists():
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    book_metadata = json.load(f)
            except Exception:
                pass

        if not book_metadata.get("title"):
            book_metadata["title"] = p_dir.name.replace("_", " ").title()
        book_metadata.setdefault("project_slug", p_dir.name)

        # Gather sample chapters across the novel
        search_dirs = [p_dir / "extracted", p_dir / "chapters", p_dir / "translation"]
        chapter_files = []
        for sdir in search_dirs:
            if sdir.exists():
                chapter_files = sorted(sdir.glob("chapter_*.md"))
                if chapter_files:
                    break

        sample_passages: list[str] = []
        if chapter_files:
            # Sample up to 5 chapters distributed across beginning, middle, and end
            step = max(1, len(chapter_files) // 5)
            selected_files = chapter_files[::step][:5]
            for cf in selected_files:
                try:
                    txt = cf.read_text(encoding="utf-8")
                    sample_passages.append(txt[:3000])
                except Exception:
                    pass

        combined_sample = "\n\n--- NEXT CHAPTER ---\n\n".join(sample_passages)
        if not combined_sample.strip():
            combined_sample = f"Novel title: {book_metadata.get('title')}"

        # 0A. Canonical Novel DeepSearch Reconnaissance (Google Search Grounding)
        dossier_path = p_dir / "book_dossier.json"
        dossier: Optional[DeepSearchNovelDossier] = None
        if dossier_path.exists():
            try:
                with open(dossier_path, "r", encoding="utf-8") as f:
                    dossier = DeepSearchNovelDossier.model_validate_json(f.read())
                if dossier and dossier.characters and len(dossier.characters) > 0 and dossier.characters[0].english_name != "Protagonist":
                    logger.info(f"  [Room 1 Step 0A/5] Canonical Novel DeepSearch dossier verified on disk ({len(dossier.characters)} characters). Reusing existing research.")
                else:
                    dossier = None
            except Exception as e:
                logger.warning(f"  [Room 1 Step 0A/5] Existing dossier unreadable ({e}), re-running web reconnaissance...")
                dossier = None

        if dossier is None:
            logger.info("  [Room 1 Step 0A/5] NovelDeepSearch conducting multi-angle web reconnaissance...")
            dossier = self.deepsearch.conduct_deepsearch(
                title=book_metadata.get("title", ""),
                author=book_metadata.get("author", ""),
                sample_text=combined_sample,
                project_slug=p_dir.name,
                call_llm_fn=call_llm_fn,
            )
            with open(dossier_path, "w", encoding="utf-8") as f:
                json.dump(dossier.model_dump(), f, ensure_ascii=False, indent=2)

        # 0B. Universal Literary DNA & Register Profiling (Novel-Agnostic)
        book_dna_data = None
        if book_dna_path.exists() and not force:
            try:
                with open(book_dna_path, "r", encoding="utf-8") as f:
                    book_dna_data = json.load(f)
                if book_dna_data.get("literary_tradition"):
                    logger.info("  [Room 1 Step 0B/5] Existing book_dna.json verified on disk. Reusing.")
                else:
                    book_dna_data = None
            except Exception:
                book_dna_data = None

        if book_dna_data is None:
            logger.info("  [Room 1 Step 0B/5] BookDNAAgent profiling universal literary DNA & register...")
            book_dna_data = self.book_dna_agent.analyze_book_dna(
                novel_text_sample=combined_sample,
                book_metadata=book_metadata,
                call_llm_fn=call_llm_fn,
                enable_web_research=(dossier is None),
            )
        # Synchronize with DeepSearch canonical findings
        if dossier:
            if dossier.literary_dna.tradition:
                book_dna_data["literary_tradition"] = dossier.literary_dna.tradition
            if dossier.literary_dna.source_fidelity_tier:
                book_dna_data["source_fidelity_tier"] = dossier.literary_dna.source_fidelity_tier
            if dossier.literary_dna.narrative_tone:
                book_dna_data["world_atmosphere_summary"] = dossier.literary_dna.narrative_tone
            if dossier.world_acoustics.banned_anachronisms:
                book_dna_data["banned_anachronisms"] = dossier.world_acoustics.banned_anachronisms
            if dossier.linguistic_dialect.acceptable_loanwords:
                book_dna_data["acceptable_loanwords"] = dossier.linguistic_dialect.acceptable_loanwords
            if dossier.musical_tradition.signature_instruments:
                book_dna_data["musical_instruments"] = dossier.musical_tradition.signature_instruments
            if dossier.literary_dna.historical_era:
                book_dna_data["historical_era"] = dossier.literary_dna.historical_era
            if dossier.linguistic_dialect.recommended_hindustani_register:
                book_dna_data["regional_dialect_cadence"] = dossier.linguistic_dialect.recommended_hindustani_register

        with open(book_dna_path, "w", encoding="utf-8") as f:
            json.dump(book_dna_data, f, ensure_ascii=False, indent=2)

        # 1. Dramatis Personae Extraction (Guided by Book DNA & DeepSearch)
        logger.info("  [Room 1 Step 1/5] DramatisPersonaeAgent extracting character dossiers...")
        raw_chars = self.dramatis_personae_agent.extract_dramatis_personae(
            novel_text_sample=combined_sample,
            book_metadata=book_metadata,
            book_dna=book_dna_data,
            call_llm_fn=call_llm_fn,
        )

        # Seed characters_list with DeepSearch canonical characters so verified Devanagari spellings take precedence
        characters_list: list[Dict[str, Any]] = []
        known_names = set()
        if dossier and dossier.characters:
            for d_char in dossier.characters:
                c_name = d_char.english_name.strip()
                if c_name and c_name.lower() != "protagonist":
                    characters_list.append({
                        "english_name": c_name,
                        "hindi_name": d_char.hindi_name,
                        "gender": d_char.gender,
                        "aliases": d_char.aliases,
                        "prominence": d_char.role_prominence,
                        "vocal_archetype": d_char.vocal_weight,
                        "sociolect_trait": d_char.occupation_status or "NEUTRAL",
                        "recommended_pronoun_level": "aap" if d_char.age_group == "elder" else "tum",
                        "speech_quirks": "",
                    })
                    known_names.add(c_name.lower())
                    for a in d_char.aliases:
                        known_names.add(a.lower())

        # Append novel-text discovered characters not already covered by canonical dossier
        for c in raw_chars:
            if isinstance(c, dict) and c.get("english_name"):
                name = c["english_name"].strip()
                if name.lower() not in known_names and name.lower() not in ("protagonist", "narrator"):
                    characters_list.append(c)
                    known_names.add(name.lower())

        # 2. Sonic World Architecture
        sonic_bible_data = None
        if sonic_bible_path.exists() and not force:
            try:
                with open(sonic_bible_path, "r", encoding="utf-8") as f:
                    sonic_bible_data = json.load(f)
                if sonic_bible_data.get("acoustic_spaces"):
                    logger.info("  [Room 1 Step 2/5] Existing sonic_bible.json verified on disk. Reusing.")
                else:
                    sonic_bible_data = None
            except Exception:
                sonic_bible_data = None

        if sonic_bible_data is None:
            logger.info("  [Room 1 Step 2/5] SonicWorldArchitect synthesizing acoustic DNA...")
            sonic_bible_data = self.sonic_architect.design_sonic_bible(
                novel_text_sample=combined_sample,
                book_metadata=book_metadata,
                call_llm_fn=call_llm_fn,
            )
        if dossier:
            if dossier.world_acoustics.banned_anachronisms:
                sonic_bible_data["banned_anachronisms"] = dossier.world_acoustics.banned_anachronisms
            if dossier.musical_tradition.signature_instruments:
                sonic_bible_data["signature_instruments"] = dossier.musical_tradition.signature_instruments
            if dossier.musical_tradition.cultural_tradition:
                sonic_bible_data["cultural_tradition"] = dossier.musical_tradition.cultural_tradition
            if dossier.musical_tradition.primary_moods:
                sonic_bible_data["primary_moods"] = dossier.musical_tradition.primary_moods
            if dossier.world_acoustics.primary_materials:
                sonic_bible_data["primary_materials"] = dossier.world_acoustics.primary_materials
            if dossier.world_acoustics.architectural_style:
                sonic_bible_data["architectural_style"] = dossier.world_acoustics.architectural_style
            if dossier.literary_dna.historical_era:
                sonic_bible_data["primary_era"] = dossier.literary_dna.historical_era

        with open(sonic_bible_path, "w", encoding="utf-8") as f:
            json.dump(sonic_bible_data, f, ensure_ascii=False, indent=2)

        # 3. Phonetic Lexicon Extraction
        logger.info("  [Room 1 Step 3/5] PhoneticLexiconDramaturge extracting world lexicon...")
        lexicon_data = self.lexicon_dramaturge.extract_lexicon_and_phonetics(
            novel_text_sample=combined_sample,
            book_metadata=book_metadata,
            call_llm_fn=call_llm_fn,
        )

        # 4. Assemble and Save BookBible
        bible = BookBible.load_from_project(p_dir)
        bible.book_title = book_metadata.get("title", bible.book_title)
        bible.author = book_metadata.get("author", bible.author)

        for c_dict in characters_list:
            if isinstance(c_dict, dict) and c_dict.get("english_name"):
                eng_name = c_dict["english_name"]
                entity = BookEntity(
                    canonical_name=eng_name,
                    english_name=eng_name,
                    hindi_name=c_dict.get("hindi_name", ""),
                    gender=c_dict.get("gender", "neutral"),
                    aliases=c_dict.get("aliases", []),
                    sociolect_trait=c_dict.get("sociolect_trait"),
                    speech_quirks=c_dict.get("speech_quirks", ""),
                    recommended_pronoun_level=c_dict.get("recommended_pronoun_level", "tum"),
                )
                bible.characters[eng_name] = entity

        bible.locations.update(lexicon_data.get("locations", {}))
        bible.organizations.update(lexicon_data.get("organizations", {}))
        bible.creatures.update(lexicon_data.get("creatures", {}))
        bible.objects.update(lexicon_data.get("objects", {}))
        bible.terminology.update(lexicon_data.get("terminology", {}))
        bible.save(p_dir)

        # 5. Lock Cast using CharacterCaster
        logger.info("  [Room 1 Finalize] Locking cast registry via CharacterCaster...")
        try:
            CharacterCaster.discover_and_cast_project(
                project_dir=p_dir,
                use_hindi=True,
                force_recast=force,
            )
        except Exception as e:
            logger.warning(f"  [!] CharacterCaster lock warning: {e}")

        # Ensure cast_lock.json exists even in minimal or synthetic project setups
        if not cast_lock_path.exists():
            try:
                roster_chars = [
                    {"name": c.get("english_name"), "gender": c.get("gender", "male")}
                    for c in characters_list if isinstance(c, dict) and c.get("english_name")
                ]
                roster, vreg, cast_lock = CharacterCaster._build_cast_allocation(
                    project_id=f"proj-{p_dir.name}",
                    raw_characters=roster_chars,
                    use_hindi=True,
                )
                with open(cast_lock_path, "w", encoding="utf-8") as f:
                    json.dump(cast_lock, f, ensure_ascii=False, indent=2)
                with open(p_dir / "voice_registry.json", "w", encoding="utf-8") as f:
                    json.dump(vreg, f, ensure_ascii=False, indent=2)
                with open(p_dir / "character_roster.json", "w", encoding="utf-8") as f:
                    json.dump(roster, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.warning(f"  [!] Direct cast lock synthesis warning: {e}")

        logger.info(f"[+] PreProductionSupervisor: Novel master state locked successfully in {p_dir.name}.")
        return {
            "status": "MASTER_LOCKED",
            "characters_count": len(bible.characters),
            "locations_count": len(bible.locations),
            "book_dna": str(book_dna_path),
            "book_bible": str(book_bible_path),
            "sonic_bible": str(sonic_bible_path),
            "cast_lock": str(cast_lock_path),
        }


def run_preproduction(project_dir: Path | str, force: bool = False, model: Optional[str] = None) -> Dict[str, Any]:
    """Convenience helper to run one-time pre-production master pass."""
    supervisor = PreProductionSupervisor(model=model)
    return supervisor.execute_preproduction(project_dir=project_dir, force=force)
