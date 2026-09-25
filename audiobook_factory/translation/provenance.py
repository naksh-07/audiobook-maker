#!/usr/bin/env python3
"""
Audiobook Factory - Translation Provenance & Dependency-Aware Cache Engine.
Ensures cache validity strictly depends on:
- Source text hash
- Book Bible version hash
- Policy version
- Prompt version
- Translator version
- Evaluator version
- Semantic Map version & hash
- Repair Engine version
- Model tier
- Advisory Lexicon version
Prevents stale translations from surviving architecture upgrades.
"""

from __future__ import annotations
import os
import json
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class TranslationProvenance(BaseModel):
    source_hash: str
    bible_version_hash: str
    policy_version: str = "2.0.0"
    prompt_version: str = "2.0.0"
    translator_version: str = "2.0"
    evaluator_version: str = "2.0"
    semantic_map_version: str = "2.0"
    semantic_map_hash: str = ""
    repair_version: str = "2.0"
    model: str
    advisory_version: str = "2.0"
    pronunciation_version: str = "1.0"
    pronunciation_hash: str = ""
    composite_cache_key: str
    created_at: str
    chapter_num: int = 1
    scene_id: Optional[str] = None
    git_commit: Optional[str] = None
    certified: bool = False
    certification_status: str = "UNCHECKED"


class TranslationProvenanceTracker:
    @staticmethod
    def generate_composite_key(
        source_text: str,
        bible_version_hash: str,
        policy_version: str = "2.0.0",
        prompt_version: str = "2.0.0",
        model: str = "gemini-3.8-flash",
        advisory_version: str = "2.0",
        translator_version: str = "2.0",
        evaluator_version: str = "2.0",
        semantic_map_version: str = "2.0",
        semantic_map_hash: str = "",
        repair_version: str = "2.0",
        pronunciation_version: str = "1.0",
        pronunciation_hash: str = "",
    ) -> str:
        """Computes deterministic SHA256 composite cache key across all 13 dependency components."""
        source_hash = hashlib.sha256(source_text.encode("utf-8")).hexdigest()[:16]
        payload = (
            f"{source_hash}:{bible_version_hash}:{policy_version}:{prompt_version}:"
            f"{translator_version}:{evaluator_version}:{semantic_map_version}:{semantic_map_hash}:"
            f"{repair_version}:{model}:{advisory_version}:{pronunciation_version}:{pronunciation_hash}"
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]

    @staticmethod
    def is_cache_valid(cache_provenance_file: Path, current_key: str) -> bool:
        """
        Validates whether cached artifact provenance exactly matches the current key
        AND is properly certified (PASS or PASS_WITH_WARNINGS).
        """
        if not cache_provenance_file.exists():
            return False
        try:
            with open(cache_provenance_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            key_matches = data.get("composite_cache_key") == current_key
            is_certified = data.get("certified", False) is True
            valid_status = data.get("certification_status") in ("PASS", "PASS_WITH_WARNINGS", "AUTO_REPAIR")
            return key_matches and is_certified and valid_status
        except Exception:
            return False

    @staticmethod
    def write_provenance(
        output_file: Path,
        source_text: str,
        bible_version_hash: str,
        policy_version: str = "2.0.0",
        prompt_version: str = "2.0.0",
        model: str = "gemini-3.8-flash",
        chapter_num: int = 1,
        scene_id: Optional[str] = None,
        translator_version: str = "2.0",
        evaluator_version: str = "2.0",
        semantic_map_version: str = "2.0",
        semantic_map_hash: str = "",
        repair_version: str = "2.0",
        advisory_version: str = "2.0",
        pronunciation_version: str = "1.0",
        pronunciation_hash: str = "",
        certified: bool = False,
        certification_status: str = "UNCHECKED",
    ):
        """Persists full provenance metadata alongside the translated chapter artifact."""
        import datetime
        comp_key = TranslationProvenanceTracker.generate_composite_key(
            source_text=source_text,
            bible_version_hash=bible_version_hash,
            policy_version=policy_version,
            prompt_version=prompt_version,
            model=model,
            advisory_version=advisory_version,
            translator_version=translator_version,
            evaluator_version=evaluator_version,
            semantic_map_version=semantic_map_version,
            semantic_map_hash=semantic_map_hash,
            repair_version=repair_version,
            pronunciation_version=pronunciation_version,
            pronunciation_hash=pronunciation_hash,
        )
        source_hash = hashlib.sha256(source_text.encode("utf-8")).hexdigest()[:16]

        prov = TranslationProvenance(
            source_hash=source_hash,
            bible_version_hash=bible_version_hash,
            policy_version=policy_version,
            prompt_version=prompt_version,
            translator_version=translator_version,
            evaluator_version=evaluator_version,
            semantic_map_version=semantic_map_version,
            semantic_map_hash=semantic_map_hash,
            repair_version=repair_version,
            model=model,
            advisory_version=advisory_version,
            pronunciation_version=pronunciation_version,
            pronunciation_hash=pronunciation_hash,
            composite_cache_key=comp_key,
            created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            chapter_num=chapter_num,
            scene_id=scene_id,
            certified=certified,
            certification_status=certification_status,
        )

        output_file = Path(output_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(prov.model_dump(), f, ensure_ascii=False, indent=2)
