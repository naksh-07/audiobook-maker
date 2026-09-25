#!/usr/bin/env python3
"""
Audiobook Factory - Cross-Chapter Pronunciation Consistency Auditor.
Ensures that recurring canonical entities maintain uniform spoken representations
across chapters, scenes, narrators, and dialogue without accidental phonetic drift.
Supports explicit contextual exceptions.
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

from audiobook_factory.logger import logger
from .contracts import CrossChapterPronunciationDrift


class CrossChapterConsistencyAuditor:
    """
    Audits book-level pronunciation consistency across all chapters.
    """

    def __init__(self, allowed_exceptions: Optional[Dict[str, str]] = None):
        # Maps canonical_id -> reason for intentional spoken variation
        self.allowed_exceptions = allowed_exceptions or {}

    def audit_project(
        self,
        project_dir: Path | str,
        lexicon: Optional[Any] = None,
    ) -> List[CrossChapterPronunciationDrift]:
        """
        Audits all screenplay script files in project_dir/scripts for pronunciation drift.
        """
        proj = Path(project_dir).resolve()
        scripts_dir = proj / "scripts"
        if not scripts_dir.exists():
            return []

        script_files = sorted(scripts_dir.glob("chapter_*_script.json"))
        entity_occurrences: Dict[str, List[Dict[str, Any]]] = {}

        for sf in script_files:
            # Parse chapter number
            try:
                with open(sf, "r", encoding="utf-8") as f:
                    s_data = json.load(f)
                if isinstance(s_data, dict):
                    segments = s_data.get("segments", [])
                else:
                    segments = s_data

                for seg in segments:
                    if not isinstance(seg, dict):
                        continue
                    meta_list = seg.get("pronunciation_metadata")
                    if not meta_list or not isinstance(meta_list, list):
                        continue

                    chap_num = seg.get("chapter_num", 1)
                    s_idx = seg.get("index", 1)
                    speaker = seg.get("speaker", "Narrator")

                    for item in meta_list:
                        cid = item.get("canonical_id") or item.get("original_token", "").strip().lower()
                        if not cid:
                            continue

                        spoken = item.get("resolved_spoken", "")
                        orig = item.get("original_token", "")
                        status = item.get("status", "VERIFIED")

                        if cid not in entity_occurrences:
                            entity_occurrences[cid] = []

                        entity_occurrences[cid].append({
                            "chapter": chap_num,
                            "segment_index": s_idx,
                            "speaker": speaker,
                            "original_token": orig,
                            "spoken_form": spoken,
                            "status": status,
                        })
            except Exception as e:
                logger.warning(f"  [!] Consistency auditor notice on {sf.name}: {e}")

        # Analyze occurrences for drift
        drifts: List[CrossChapterPronunciationDrift] = []

        for cid, occs in entity_occurrences.items():
            if len(occs) < 2:
                continue

            unique_spoken = list({o["spoken_form"] for o in occs if o["spoken_form"]})
            if len(unique_spoken) > 1:
                # Potential drift detected
                canon_text = occs[0]["original_token"]
                sample_strs = ", ".join(f"Ch{o['chapter']}:{o['spoken_form']}" for o in occs[:4])
                drift_details = [
                    f"Spoken form variation across chapters: {unique_spoken}. "
                    f"Sample occurrences: [{sample_strs}]"
                ]

                is_allowed = cid in self.allowed_exceptions
                exc_reason = self.allowed_exceptions.get(cid, "")

                drift_record = CrossChapterPronunciationDrift(
                    canonical_id=cid,
                    canonical_text=canon_text,
                    occurrences=occs,
                    drift_detected=True,
                    drift_details=drift_details,
                    allowed_exception=is_allowed,
                    exception_reason=exc_reason,
                )
                drifts.append(drift_record)

        return drifts
