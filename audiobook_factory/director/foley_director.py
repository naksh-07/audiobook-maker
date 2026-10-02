from __future__ import annotations
import os
import re
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from audiobook_factory.logger import logger
from audiobook_factory.contracts import FoleyCue

class FoleyDirectorMixin:
    def _pass3_acoustic_foley(
        self,
        script_segments: List[Dict[str, Any]],
        foley_events_plan: List[Dict[str, Any]],
        seg_starts_ms: Dict[int, int],
        segment_durations_sec: Dict[int, float],
    ) -> List[FoleyCue]:
        """
        Pass 3: Acoustic Foley using structured screenplay cues and explicit physical actions.
        Aligns physical contact events to exact anchor word timestamps with transient pre-roll.
        Zero guessing of weapons or combat in domestic/modern scenes.
        """
        foley_cues: List[FoleyCue] = []
        seg_by_index = {s.get("index", idx + 1): s for idx, s in enumerate(script_segments)}

        # If LLM did not generate foley events (or offline), run explicit dependency parsing
        candidates = list(foley_events_plan) if foley_events_plan else self._parse_grammatical_foley_dependencies(script_segments)

        # Register any dedicated action beats in script_segments not already in candidates
        registered_indices = {c.get("segment_index") for c in candidates}
        for s in script_segments:
            s_idx = s.get("index", 1)
            if s.get("type") == "action" and s_idx not in registered_indices:
                sfx_list = s.get("sfx_cues", [])
                action_verb = "creak"
                material = "wood"
                anchor_tag = "[ACTION]"
                if sfx_list:
                    raw_sfx = sfx_list[0]
                    tag = raw_sfx.get("tag", "") if isinstance(raw_sfx, dict) else str(raw_sfx)
                    if tag:
                        anchor_tag = tag
                        parts = tag.split("_")
                        if len(parts) >= 2:
                            action_verb = parts[0]
                            material = parts[1]
                        elif len(parts) == 1:
                            action_verb = parts[0]
                    candidates.append({
                        "segment_index": s_idx,
                        "subject": "Foley",
                        "action_verb": action_verb,
                        "object_material": material,
                        "anchor_word": anchor_tag,
                        "target_gain_dbfs": -16.0,
                        "azimuth_pan": 0.0,
                    })

        for idx, event in enumerate(candidates):
            s_idx = event.get("segment_index", 1)
            seg = seg_by_index.get(s_idx)
            if not seg:
                continue

            action_verb = event.get("action_verb", "")
            object_material = event.get("object_material", "")
            if not action_verb:
                continue

            anchor_word = event.get("anchor_word", "")
            target_gain_dbfs = float(event.get("target_gain_dbfs", -16.0))
            pan_val = float(event.get("azimuth_pan", 0.0))
            pan_val = max(-0.8, min(0.8, pan_val))

            # Resolve asset dynamically from Sound Bank via category/action/exciter
            asset_path = self._resolve_foley_asset(action_verb, object_material)
            if not asset_path or not asset_path.exists():
                continue

            # Anchor Foley cues: dedicated physical action beats land directly on seg_start_ms + 50ms
            seg_start_ms = seg_starts_ms.get(s_idx, 0)
            seg_dur_ms = int(segment_durations_sec.get(s_idx, 4.0) * 1000)

            is_action_seg = (seg.get("type") == "action") or (seg.get("speaker") == "Foley")
            if is_action_seg:
                # Dedicated action beat: anchor Foley directly to seg_start_ms + 50ms with 50ms transient lead-in
                pre_roll_ms = 50
                cue_start_ms = max(0, seg_start_ms + 50)
            else:
                # Word-level alignment: calculate precise offset of anchor word in segment speech
                anchor_offset_ms = self._compute_word_level_offset(
                    text=seg.get("text", ""),
                    anchor_word=anchor_word,
                    seg_dur_ms=seg_dur_ms,
                    action_verb=action_verb,
                    word_alignments=seg.get("word_alignments")
                )
                pre_roll_ms = 100  # 100ms transient lead-in for physical impact
                cue_start_ms = max(0, seg_start_ms + anchor_offset_ms - pre_roll_ms)

            from audiobook_factory.acoustic_bus_matrix import derive_ucs_category
            ucs_code = derive_ucs_category(action_verb, object_material)

            foley_cues.append(
                FoleyCue(
                    cue_id=f"fc_{s_idx:04d}_{idx:03d}",
                    segment_index=s_idx,
                    anchor_word=anchor_word or action_verb,
                    pre_roll_ms=pre_roll_ms,
                    asset_id=0,
                    asset_path=str(asset_path.resolve()).replace("\\", "/"),
                    asset_name=asset_path.name,
                    gain_dbfs=target_gain_dbfs,
                    azimuth_pan=pan_val,
                    start_ms=cue_start_ms,
                    duration_ms=0,
                    ucs_category=ucs_code,
                )
            )

        from audiobook_factory.acoustic_bus_matrix import filter_concurrency_window
        from audiobook_factory.soundscape import attenuate_foley_whisper_collisions
        pruned_foley = filter_concurrency_window(foley_cues, window_ms=200, max_concurrency=3)
        return attenuate_foley_whisper_collisions(pruned_foley, script_segments, attenuation_db=-6.0)

    def _parse_grammatical_foley_dependencies(
        self, script_segments: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Extracts physical Foley events strictly from explicit segment metadata (sfx_cues)
        or dedicated action segments. Never hallucinates weapons, combat, or fantasy actions
        in domestic, suburban, or peaceful scenes.
        """
        candidates: List[Dict[str, Any]] = []

        for seg in script_segments:
            s_idx = seg.get("index", 1)
            sfx_list = seg.get("sfx_cues", [])
            is_action = (seg.get("type") == "action") or (seg.get("speaker") == "Foley")

            # 1. Parse explicit sfx_cues provided by the LLM or screenplay
            if sfx_list:
                for sfx in sfx_list:
                    tag = sfx.get("tag", "") if isinstance(sfx, dict) else str(sfx)
                    if not tag:
                        continue
                    parts = tag.split("_")
                    action_verb = parts[0]
                    material = parts[1] if len(parts) >= 2 else "wood"
                    candidates.append({
                        "segment_index": s_idx,
                        "subject": seg.get("speaker", "Foley"),
                        "action_verb": action_verb,
                        "object_material": material,
                        "anchor_word": sfx.get("anchor_word", f"[{tag.upper()}]") if isinstance(sfx, dict) else f"[{tag.upper()}]",
                        "target_gain_dbfs": float(sfx.get("gain_dbfs", -16.0)) if isinstance(sfx, dict) else -16.0,
                        "azimuth_pan": float(sfx.get("pan", 0.0)) if isinstance(sfx, dict) else 0.0,
                    })
                continue

            # 2. If dedicated action segment has explicit action_verb metadata, preserve it
            if is_action and seg.get("action_verb"):
                candidates.append({
                    "segment_index": s_idx,
                    "subject": "Foley",
                    "action_verb": seg.get("action_verb"),
                    "object_material": seg.get("object_material", "physical"),
                    "anchor_word": seg.get("anchor_word", "[ACTION]"),
                    "target_gain_dbfs": float(seg.get("gain_dbfs", -16.0)),
                    "azimuth_pan": float(seg.get("pan", 0.0)),
                })

        return candidates

    def _compute_word_level_offset(
        self, text: str, anchor_word: str, seg_dur_ms: int, action_verb: str = "", word_alignments: Optional[List[Dict[str, Any]]] = None
    ) -> int:
        """Computes speech timeline offset of the anchor word within a dialogue segment with bilingual normalization."""
        anchor_lower = (anchor_word or "").lower().strip()
        verb_lower = (action_verb or "").lower().strip()

        # Bilingual Synonym / Stem Map (Devanagari <-> English)
        BILINGUAL_ANCHOR_MAP = {
            "sword": ["तलवार", "खंजर", "ब्लेड", "शमशीर", "blade"],
            "blade": ["तलवार", "खंजर", "ब्लेड"],
            "draw": ["खींची", "निकाली", "निकाल", "खींच", "draw"],
            "unsheathe": ["खींची", "निकाली", "म्यान"],
            "door": ["दरवाजा", "किवाड़", "कपाट", "gate"],
            "slam": ["पटक", "दे मारा", "धड़ाम", "ठोक", "slam"],
            "creak": ["चूं", "चरमरा", "आवाज", "creak"],
            "step": ["कदम", "पैरों", "चला", "बढ़ा", "step"],
            "footstep": ["कदम", "पैरों", "पदचाप", "footsteps"],
            "plate": ["थाली", "तश्तरी", "बर्तन", "रकाब", "plate"],
            "dish": ["थाली", "कटोरा", "प्याला", "बर्तन", "dish"],
            "cup": ["प्याला", "गिलास", "कटोरा", "cup"],
            "tankard": ["प्याला", "मग", "सुराही", "कटोरा", "tankard"],
            "pour": ["उड़ेला", "उड़ेल", "डाला", "भर", "pour"],
            "bone": ["हड्डी", "अस्थि", "bone"],
            "body": ["शरीर", "देह", "धड़", "लाश", "body"],
            "fall": ["गिरा", "गिरे", "फर्श", "जमीन", "fall"],
            "clash": ["टकरा", "वार", "clash"],
            "ignite": ["जला", "सुलगा", "ignite"],
            "torch": ["मशाल", "आग", "torch"],
            "fire": ["आग", "ज्वाला", "fire"],
        }

        search_targets = {anchor_lower} if anchor_lower else set()
        if anchor_lower in BILINGUAL_ANCHOR_MAP:
            search_targets.update(BILINGUAL_ANCHOR_MAP[anchor_lower])
        if verb_lower in BILINGUAL_ANCHOR_MAP:
            search_targets.update(BILINGUAL_ANCHOR_MAP[verb_lower])
        for eng, hindi_list in BILINGUAL_ANCHOR_MAP.items():
            if anchor_lower in hindi_list:
                search_targets.add(eng)
                search_targets.update(hindi_list)

        # 1. Precise Aligner Mode
        if word_alignments:
            for word_data in word_alignments:
                w_norm = str(word_data.get("normalized_token", "")).lower()
                w_raw = str(word_data.get("token", "")).lower()
                if any(t and (t == w_norm or t == w_raw or t in w_raw) for t in search_targets):
                    # Return exact exact alignment timestamp in MS
                    return int(word_data.get("start_ms", 0))

        # 2. Fallback Linear Math Mode (If forced aligner data is missing)
        words = [w.strip(".,!?;:\"'()[]{}—–") for w in text.split() if w.strip(".,!?;:\"'()[]{}—–")]
        if not words:
            return 150

        word_idx = -1
        for i, w in enumerate(words):
            w_low = w.lower()
            if any(t and (t in w_low or w_low in t) for t in search_targets):
                word_idx = i
                break

        if word_idx >= 0:
            word_ratio = (word_idx + 0.5) / max(1, len(words))
            return int(seg_dur_ms * max(0.08, min(0.92, word_ratio)))

        impact_actions = {"clash", "slam", "fall", "impact", "break", "bone", "पटक", "गिरा", "टकरा"}
        if anchor_lower in impact_actions or verb_lower in impact_actions:
            return int(seg_dur_ms * 0.75)
        return int(seg_dur_ms * 0.15)

    def _resolve_foley_asset(self, action_verb: str, object_material: str) -> Optional[Path]:
        """Resolves sound asset from sound bank using Sonic Intelligence Engine semantic intent queries."""
        intent = f"{action_verb} {object_material}".strip()
        if not intent:
            return None

        try:
            # Engage hybrid intelligence FTS/Vector query
            result = self.sound_bank.search_intelligence(intent=intent, limit=3)
            if result and hasattr(result, "ranked_cards") and result.ranked_cards:
                for card in result.ranked_cards:
                    if card and getattr(card, "file_path", None):
                        cand = Path(card.file_path)
                        # CATEGORY GUARD: Prohibit weapon/combat assets for non-combat intents
                        is_combat_intent = any(w in intent.lower() for w in ("sword", "blade", "dagger", "axe", "weapon", "clash"))
                        banned_non_combat = ("sword", "blade", "scabbard", "parry", "axe", "dagger", "drawbridge", "armor", "clash")
                        if not is_combat_intent and any(b in cand.name.lower() for b in banned_non_combat):
                            continue
                        if cand.exists():
                            return cand
        except Exception as e:
            # Fallback to basic search if intelligence engine fails
            pass

        # 2. Basic fallback search if Intelligence didn't yield a valid local path
        matches = self.sound_bank.search(intent, category="foley", limit=3)
        if not matches:
            matches = self.sound_bank.search(action_verb, category="foley", limit=2)
        for m in matches:
            if m.get("filepath"):
                cand = Path(m["filepath"])
                is_combat_intent = any(w in intent.lower() for w in ("sword", "blade", "dagger", "axe", "weapon", "clash"))
                banned_non_combat = ("sword", "blade", "scabbard", "parry", "axe", "dagger", "drawbridge", "armor", "clash")
                if not is_combat_intent and any(b in cand.name.lower() for b in banned_non_combat):
                    continue
                if cand.exists():
                    return cand

        # 3. Sonic Intelligence Bridge: Relaxed / Bilingual resolution
        try:
            from audiobook_factory.sonic_intelligence_bridge import SonicIntelligenceBridge
            bridge = SonicIntelligenceBridge(sound_bank=self.sound_bank)
            is_combat_intent = any(w in intent.lower() for w in ("sword", "blade", "dagger", "axe", "weapon", "clash"))
            cand_path, tier, _ = bridge.resolve_asset_with_fallback(
                query=intent,
                category="foley",
                is_combat_scene=is_combat_intent,
            )
            if cand_path and cand_path.exists():
                return cand_path
        except Exception:
            pass

        return None

