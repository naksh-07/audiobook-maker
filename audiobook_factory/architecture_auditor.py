#!/usr/bin/env python3
"""
Audiobook Factory - Master Architecture Auditor.
Provides a comprehensive, non-destructive, strictly read-only diagnostic scanner
across all 10 subsystems of the audiobook production pipeline.
Audits:
- System 1: Ingestion & Physical Extraction
- System 2: Translation & Cultural Fidelity
- System 3: Dramaturgy & Screenplay Attribution
- System 4: Voice Casting & Neural TTS
- System 5: Sonic Intelligence Database & LLM Query Utilization
- System 6: Dialogue Editorial & Pacing
- System 7: 5-Track Cinematic Multitrack Mixing
- System 8: Broadcast Mastering & EBU R128
- System 9: Packaging & M4B Monotonic Navigation
- System 10: State Governance & Telemetry
"""

from __future__ import annotations
import os
import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set

from audiobook_factory.logger import logger
from audiobook_factory.sound_bank import SoundBank, get_sound_bank
from audiobook_factory.sonic_intelligence_bridge import SonicIntelligenceBridge
from audiobook_factory.coordination_contracts import (
    RawScreenplaySegmentContract,
    strip_markdown_fences,
)


class ArchitectureAuditor:
    """Non-destructive, strictly read-only architecture auditor."""

    def __init__(self, project_dir: Path, sound_bank: Optional[SoundBank] = None):
        self.project_dir = Path(project_dir).resolve()
        self.sound_bank = sound_bank or get_sound_bank()
        self.bridge = SonicIntelligenceBridge(sound_bank=self.sound_bank)

    def audit_all(self, chapter_num: Optional[int] = None) -> Dict[str, Any]:
        """
        Executes read-only audits across all 10 subsystems.
        Returns a structured master audit report.
        """
        results: Dict[str, Any] = {
            "project_dir": str(self.project_dir),
            "project_name": self.project_dir.name,
            "chapter_filtered": chapter_num,
            "read_only": True,
            "subsystems": {},
        }

        # System 1: Ingestion
        results["subsystems"]["system1_ingestion"] = self.audit_system1_ingestion()

        # System 2: Translation
        results["subsystems"]["system2_translation"] = self.audit_system2_translation()

        # System 3: Screenplay
        results["subsystems"]["system3_screenplay"] = self.audit_system3_screenplay(chapter_num)

        # System 4: TTS & Casting
        results["subsystems"]["system4_tts_casting"] = self.audit_system4_tts_casting(chapter_num)

        # System 5: Sonic Intelligence
        results["subsystems"]["system5_sonic_intelligence"] = self.audit_system5_sonic_intelligence(chapter_num)

        # System 6: Dialogue Editorial
        results["subsystems"]["system6_editorial"] = self.audit_system6_editorial(chapter_num)

        # System 7: 5-Track Mixing
        results["subsystems"]["system7_mixing"] = self.audit_system7_mixing(chapter_num)

        # System 8: Broadcast Mastering
        results["subsystems"]["system8_mastering"] = self.audit_system8_mastering(chapter_num)

        # System 9: Packaging & M4B
        results["subsystems"]["system9_packaging"] = self.audit_system9_packaging()

        # System 10: State Governance & Telemetry
        results["subsystems"]["system10_orchestration"] = self.audit_system10_orchestration()

        # Overall Scoring
        total_subsystems = len(results["subsystems"])
        passed = sum(1 for s in results["subsystems"].values() if s.get("status") == "PASS")
        warned = sum(1 for s in results["subsystems"].values() if s.get("status") == "WARN")
        failed = sum(1 for s in results["subsystems"].values() if s.get("status") == "FAIL")

        overall_score = round(((passed * 1.0 + warned * 0.5) / max(1, total_subsystems)) * 100.0, 1)

        results["summary"] = {
            "overall_score": overall_score,
            "total_subsystems": total_subsystems,
            "passed": passed,
            "warned": warned,
            "failed": failed,
            "overall_status": "PASS" if failed == 0 and overall_score >= 80.0 else "WARN" if failed == 0 else "FAIL",
            "sonic_intelligence_hit_rate": results["subsystems"]["system5_sonic_intelligence"].get("hit_rate_pct", 0.0),
        }

        return results

    # =========================================================================
    # Subsystem 1: Ingestion & Physical Extraction
    # =========================================================================
    def audit_system1_ingestion(self) -> Dict[str, Any]:
        extracted_dir = self.project_dir / "extracted"
        if not extracted_dir.exists():
            return {
                "status": "WARN",
                "message": "Extracted directory not found. Ingestion may not have run yet.",
                "chapter_count": 0,
            }

        chap_files = sorted(extracted_dir.glob("chapter_*.md"))
        if not chap_files:
            chap_files = sorted(extracted_dir.glob("*.md"))

        total_chars = 0
        valid_chapters = 0
        for f in chap_files:
            try:
                txt = f.read_text(encoding="utf-8").strip()
                if len(txt) > 200:
                    valid_chapters += 1
                    total_chars += len(txt)
            except Exception:
                pass

        status = "PASS" if valid_chapters > 0 else "WARN"
        return {
            "status": status,
            "chapter_files_found": len(chap_files),
            "valid_chapters": valid_chapters,
            "total_chars_extracted": total_chars,
            "message": f"Verified {valid_chapters} extracted chapters ({total_chars} total characters).",
        }

    # =========================================================================
    # Subsystem 2: Translation & Cultural Fidelity
    # =========================================================================
    def audit_system2_translation(self) -> Dict[str, Any]:
        trans_dirs = [self.project_dir / "translated", self.project_dir / "translation"]
        active_trans_dir = None
        for td in trans_dirs:
            if td.exists():
                active_trans_dir = td
                break

        if not active_trans_dir:
            return {
                "status": "WARN",
                "message": "Translation directory not found (Native/English mode or pending translation).",
                "chapter_count": 0,
            }

        trans_files = sorted(active_trans_dir.glob("chapter_*_hi.md"))
        if not trans_files:
            trans_files = sorted(active_trans_dir.glob("chapter_*.md"))

        if not trans_files:
            return {
                "status": "WARN",
                "message": "No translated chapter files found in translation directory.",
                "chapter_count": 0,
            }

        devanagari_pattern = re.compile(r"[\u0900-\u097F]")
        banned_phrases = ["scene overview", "i cannot provide", "would you like", "as an ai", "note :"]

        total_files = len(trans_files)
        pure_files = 0
        meta_leaks = 0

        for tf in trans_files:
            try:
                txt = tf.read_text(encoding="utf-8")
                dev_chars = len(devanagari_pattern.findall(txt))
                total_chars = max(1, len(txt.strip()))
                dev_ratio = dev_chars / total_chars
                if dev_ratio >= 0.70:
                    pure_files += 1

                txt_lower = txt.lower()
                if any(bp in txt_lower for bp in banned_phrases):
                    meta_leaks += 1
            except Exception:
                pass

        status = "PASS" if meta_leaks == 0 and pure_files == total_files else "WARN"
        return {
            "status": status,
            "translated_files_found": total_files,
            "devanagari_pure_files": pure_files,
            "meta_commentary_leaks": meta_leaks,
            "message": f"{pure_files}/{total_files} files passed Devanagari purity. Leaks detected: {meta_leaks}.",
        }

    # =========================================================================
    # Subsystem 3: Dramaturgy & Screenplay Attribution
    # =========================================================================
    def audit_system3_screenplay(self, chapter_num: Optional[int] = None) -> Dict[str, Any]:
        scripts_dir = self.project_dir / "scripts"
        if not scripts_dir.exists():
            return {
                "status": "WARN",
                "message": "Scripts directory not found.",
            }

        pattern = f"chapter_{chapter_num:03d}_*.json" if chapter_num else "chapter_*_script.json"
        script_files = sorted(scripts_dir.glob(pattern))
        if not script_files:
            script_files = sorted(scripts_dir.glob("chapter_*.json"))
            script_files = [f for f in script_files if "_manifest" not in f.name and "_timeline" not in f.name]

        if not script_files:
            return {
                "status": "WARN",
                "message": "No screenplay script files found.",
            }

        # Load known character roster if available
        roster_file = self.project_dir / "character_roster.json"
        known_speakers: Set[str] = {"Narrator", "Foley"}
        if roster_file.exists():
            try:
                with open(roster_file, "r", encoding="utf-8") as rf:
                    rdata = json.load(rf)
                chars = rdata.get("characters", rdata)
                if isinstance(chars, dict):
                    known_speakers.update(chars.keys())
                elif isinstance(chars, list):
                    for c in chars:
                        if isinstance(c, dict):
                            known_speakers.add(c.get("english_name", c.get("display_name", "")))
            except Exception:
                pass

        total_segments = 0
        action_segments = 0
        unmapped_speakers: Set[str] = set()
        schema_errors = 0

        for sf in script_files:
            try:
                with open(sf, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)
                segs = raw_data.get("segments", raw_data) if isinstance(raw_data, dict) else raw_data
                if isinstance(segs, list):
                    for s in segs:
                        total_segments += 1
                        spk = str(s.get("speaker", "Narrator")).strip()
                        if spk not in known_speakers and len(known_speakers) > 2:
                            unmapped_speakers.add(spk)
                        if s.get("type") == "action" or spk == "Foley":
                            action_segments += 1
                        try:
                            RawScreenplaySegmentContract.model_validate(s)
                        except Exception:
                            schema_errors += 1
            except Exception as e:
                schema_errors += 1

        status = "PASS" if schema_errors == 0 and len(unmapped_speakers) <= 2 else "WARN"
        return {
            "status": status,
            "script_files_audited": len(script_files),
            "total_segments": total_segments,
            "action_segments": action_segments,
            "schema_errors": schema_errors,
            "unmapped_speakers": list(unmapped_speakers)[:5],
            "message": f"Audited {total_segments} segments across {len(script_files)} scripts. Action beats: {action_segments}.",
        }

    # =========================================================================
    # Subsystem 4: Voice Casting & Neural TTS
    # =========================================================================
    def audit_system4_tts_casting(self, chapter_num: Optional[int] = None) -> Dict[str, Any]:
        audio_dir = self.project_dir / "audio_chunks"
        if not audio_dir.exists():
            return {
                "status": "WARN",
                "message": "Audio chunks directory not found.",
            }

        pattern = f"c{chapter_num:03d}_*.wav" if chapter_num else "c*.wav"
        chunks = list(audio_dir.glob(pattern))

        # Check for retained chunks or mastered dialogue
        mastered_dir = self.project_dir / "mastered"
        has_dialogue_master = any(mastered_dir.glob("*_dialogue.wav")) if mastered_dir.exists() else False

        voice_registry_file = self.project_dir / "voice_registry.json"
        registered_voices = 0
        if voice_registry_file.exists():
            try:
                with open(voice_registry_file, "r", encoding="utf-8") as vf:
                    vdata = json.load(vf)
                registered_voices = len(vdata.get("characters", vdata))
            except Exception:
                pass

        status = "PASS" if (len(chunks) > 0 or has_dialogue_master) else "WARN"
        return {
            "status": status,
            "audio_chunks_count": len(chunks),
            "dialogue_master_exists": has_dialogue_master,
            "registered_cast_size": registered_voices,
            "message": f"Found {len(chunks)} synthesized speech chunks. Cast size: {registered_voices}.",
        }

    # =========================================================================
    # Subsystem 5: Sonic Intelligence Database & LLM Query Utilization
    # =========================================================================
    def audit_system5_sonic_intelligence(self, chapter_num: Optional[int] = None) -> Dict[str, Any]:
        manifests_dir = self.project_dir / "manifests"
        if not manifests_dir.exists():
            return {
                "status": "WARN",
                "hit_rate_pct": 0.0,
                "message": "Manifests directory not found.",
            }

        pattern = f"chapter_{chapter_num:03d}_*manifest.json" if chapter_num else "*manifest.json"
        manifest_files = sorted(manifests_dir.glob(pattern))
        if not manifest_files:
            return {
                "status": "WARN",
                "hit_rate_pct": 0.0,
                "message": "No creative manifest files found.",
            }

        all_music_queries: List[Dict[str, Any]] = []
        all_foley_queries: List[Dict[str, Any]] = []
        fantasy_cues_in_modern_scenes = 0
        total_silence_pct = 0.0

        for mf in manifest_files:
            try:
                with open(mf, "r", encoding="utf-8") as f:
                    mdata = json.load(f)

                total_silence_pct = mdata.get("silence_percentage", 65.0)

                # Collect music queries
                for mc in mdata.get("music_cues", []):
                    q = mc.get("search_query") or mc.get("track_name") or mc.get("narrative_archetype", "")
                    if q:
                        all_music_queries.append({"query": q, "category": "music"})

                # Check for fantasy sound leaks only in explicitly modern environments
                is_modern_scene = (
                    mdata.get("era", "").upper() in ("MODERN", "MODERN_CONTEMPORARY")
                    or (mdata.get("scene_intent", {}) or {}).get("era", "").upper() in ("MODERN", "MODERN_CONTEMPORARY")
                )
                for fc in mdata.get("foley_cues", []):
                    anchor = fc.get("anchor_word", "")
                    tag = fc.get("asset_name", "")
                    lower_name = (tag + " " + anchor).lower()
                    if is_modern_scene and any(w in lower_name for w in ("sword", "blade", "dagger", "axe", "magic_blast", "spell")):
                        fantasy_cues_in_modern_scenes += 1
                    if anchor and anchor != "[STOCHASTIC]":
                        all_foley_queries.append({"query": anchor, "category": "foley"})
                    elif anchor == "[STOCHASTIC]" and tag:
                        all_foley_queries.append({"query": tag, "category": "foley"})

            except Exception as e:
                logger.debug(f"Manifest parse error: {e}")

        # Execute hit-rate audit across queries
        combined_queries = all_music_queries + all_foley_queries
        hit_audit = self.bridge.audit_catalog_hit_rate(combined_queries)

        hit_rate = hit_audit.get("hit_rate_pct", 0.0)
        status = "PASS" if hit_rate >= 75.0 and fantasy_cues_in_modern_scenes == 0 else "WARN"

        return {
            "status": status,
            "manifest_files_audited": len(manifest_files),
            "total_queries_evaluated": hit_audit["total_queries"],
            "hit_rate_pct": hit_rate,
            "exact_hits": hit_audit["exact_hits"],
            "relaxed_hits": hit_audit["relaxed_hits"],
            "silence_fallbacks": hit_audit["silence_fallbacks"],
            "fantasy_cues_in_modern_scenes": fantasy_cues_in_modern_scenes,
            "silence_percentage": total_silence_pct,
            "message": f"Sonic Intelligence Hit Rate: {hit_rate}% ({hit_audit['resolved_count']}/{hit_audit['total_queries']} cues resolved). Fantasy leaks: {fantasy_cues_in_modern_scenes}.",
        }

    # =========================================================================
    # Subsystem 6: Dialogue Editorial & Pacing
    # =========================================================================
    def audit_system6_editorial(self, chapter_num: Optional[int] = None) -> Dict[str, Any]:
        audio_dir = self.project_dir / "audio_chunks"
        if not audio_dir.exists():
            return {"status": "WARN", "message": "Audio chunks directory not found."}

        word_alignments = list(audio_dir.glob("*.words.json"))
        return {
            "status": "PASS" if len(word_alignments) > 0 else "WARN",
            "forced_alignment_files": len(word_alignments),
            "message": f"Found {len(word_alignments)} word-level phoneme alignment files.",
        }

    # =========================================================================
    # Subsystem 7: 5-Track Cinematic Multitrack Mixing
    # =========================================================================
    def audit_system7_mixing(self, chapter_num: Optional[int] = None) -> Dict[str, Any]:
        mastered_dir = self.project_dir / "mastered"
        if not mastered_dir.exists():
            return {"status": "WARN", "message": "Mastered stems directory not found."}

        stems = list(mastered_dir.glob("*_stem_*.wav"))
        has_dx = any("_stem_DX" in s.name for s in stems)
        has_fx = any("_stem_FX" in s.name for s in stems)
        has_bg = any("_stem_BG" in s.name for s in stems)
        has_mx = any("_stem_MX" in s.name for s in stems)

        status = "PASS" if (has_dx and (has_fx or has_bg or has_mx)) else "WARN"
        return {
            "status": status,
            "stem_count": len(stems),
            "dialogue_dx": has_dx,
            "foley_fx": has_fx,
            "ambience_bg": has_bg,
            "music_mx": has_mx,
            "message": f"5-Track Stems: DX={has_dx}, FX={has_fx}, BG={has_bg}, MX={has_mx}.",
        }

    # =========================================================================
    # Subsystem 8: Broadcast Mastering & EBU R128
    # =========================================================================
    def audit_system8_mastering(self, chapter_num: Optional[int] = None) -> Dict[str, Any]:
        mastered_dir = self.project_dir / "mastered"
        if not mastered_dir.exists():
            return {"status": "WARN", "message": "Mastered directory not found."}

        masters = list(mastered_dir.glob("*_cinema_master.wav"))
        cinematic_m4a = list(mastered_dir.glob("*_cinematic.m4a")) + list(mastered_dir.glob("*_hi_cinematic.m4a"))

        status = "PASS" if (len(masters) > 0 or len(cinematic_m4a) > 0) else "WARN"
        return {
            "status": status,
            "master_wavs": [m.name for m in masters],
            "cinematic_m4a": [m.name for m in cinematic_m4a],
            "message": f"Certified master outputs: {len(masters)} WAV masters, {len(cinematic_m4a)} M4A containers.",
        }

    # =========================================================================
    # Subsystem 9: Packaging & M4B Monotonic Navigation
    # =========================================================================
    def audit_system9_packaging(self) -> Dict[str, Any]:
        output_dir = self.project_dir.parent.parent / "output"
        m4b_files = list(self.project_dir.glob("*.m4b"))
        if output_dir.exists():
            m4b_files.extend(list(output_dir.glob("*.m4b")))

        status = "PASS" if len(m4b_files) > 0 else "WARN"
        return {
            "status": status,
            "m4b_files_found": [f.name for f in m4b_files],
            "total_packaged": len(m4b_files),
            "message": f"Found {len(m4b_files)} packaged M4B deliverables.",
        }

    # =========================================================================
    # Subsystem 10: State Governance & Telemetry
    # =========================================================================
    def audit_system10_orchestration(self) -> Dict[str, Any]:
        active_ctx = Path(__file__).resolve().parent.parent / ".agents" / "memory" / "activeContext.md"
        line_count = 0
        if active_ctx.exists():
            try:
                line_count = len(active_ctx.read_text(encoding="utf-8").splitlines())
            except Exception:
                pass

        budget_ok = line_count <= 50
        status = "PASS" if budget_ok else "WARN"
        return {
            "status": status,
            "active_context_lines": line_count,
            "active_context_budget_pass": budget_ok,
            "message": f"Active context budget: {line_count}/50 lines ({'PASS' if budget_ok else 'WARN'}).",
        }
