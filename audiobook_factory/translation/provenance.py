#!/usr/bin/env python3
"""
Audiobook Factory - Translation Provenance & Dependency-Aware Cache Engine.
Ensures cache validity strictly depends on source hash, Book Bible version,
translation policy version, prompt template, and model tier.
Prevents stale translations from surviving architecture upgrades.
"""

import os
import json
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class TranslationProvenance(BaseModel):
    source_hash: str
    bible_version_hash: str
    policy_version: str
    prompt_version: str
    model: str
    advisory_version: str = "2.0"
    composite_cache_key: str
    created_at: str
    chapter_num: int = 1
    scene_id: Optional[str] = None
    git_commit: Optional[str] = None


class TranslationProvenanceTracker:
    @staticmethod
    def generate_composite_key(
        source_text: str,
        bible_version_hash: str,
        policy_version: str = "2.0.0",
        prompt_version: str = "2.0.0",
        model: str = "gemini-3.8-flash",
        advisory_version: str = "2.0",
    ) -> str:
        """Computes deterministic SHA256 composite cache key."""
        source_hash = hashlib.sha256(source_text.encode("utf-8")).hexdigest()[:16]
        payload = f"{source_hash}:{bible_version_hash}:{policy_version}:{prompt_version}:{model}:{advisory_version}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]

    @staticmethod
    def is_cache_valid(cache_provenance_file: Path, current_key: str) -> bool:
        """Validates whether cached artifact provenance exactly matches the current key."""
        if not cache_provenance_file.exists():
            return False
        try:
            with open(cache_provenance_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("composite_cache_key") == current_key
        except Exception:
            return False

    @staticmethod
    def write_provenance(
        output_file: Path,
        source_text: str,
        bible_version_hash: str,
        policy_version: str,
        prompt_version: str,
        model: str,
        chapter_num: int = 1,
        scene_id: Optional[str] = None,
    ):
        """Persists provenance metadata alongside the translated chapter artifact."""
        import datetime
        comp_key = TranslationProvenanceTracker.generate_composite_key(
            source_text=source_text,
            bible_version_hash=bible_version_hash,
            policy_version=policy_version,
            prompt_version=prompt_version,
            model=model,
        )
        source_hash = hashlib.sha256(source_text.encode("utf-8")).hexdigest()[:16]

        prov = TranslationProvenance(
            source_hash=source_hash,
            bible_version_hash=bible_version_hash,
            policy_version=policy_version,
            prompt_version=prompt_version,
            model=model,
            composite_cache_key=comp_key,
            created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            chapter_num=chapter_num,
            scene_id=scene_id,
        )

        output_file = Path(output_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(prov.model_dump(), f, ensure_ascii=False, indent=2)
