#!/usr/bin/env python3
"""
Tests for standardized Multi-Gate Independent Verification Auditor.
"""

import unittest
from pathlib import Path

from audiobook_factory.gate_auditor import (
    audit_gate0_translation,
    audit_gate1_roster,
    audit_gate2_script,
    audit_gate3_scenes,
    audit_chapter_gates,
    audit_gate1_anticensorship_agent,
    audit_gate2_screenplay_tags,
    audit_gate5_master,
    GateAuditError,
)

ROOT_DIR = Path(__file__).resolve().parent.parent


class TestMultiGateAuditor(unittest.TestCase):
    def test_chapter_gates_full_audit_synthetic(self):
        """Verify multi-gate chapter auditor validates end-to-end against a canonical project structure."""
        import tempfile
        import json

        with tempfile.TemporaryDirectory() as td:
            pdir = Path(td)
            ext_dir = pdir / "extracted"
            trans_dir = pdir / "translation"
            scripts_dir = pdir / "scripts"
            ext_dir.mkdir(parents=True, exist_ok=True)
            trans_dir.mkdir(parents=True, exist_ok=True)
            scripts_dir.mkdir(parents=True, exist_ok=True)

            ch_str = "chapter_001"
            (ext_dir / f"{ch_str}.md").write_text(
                "The hero walked through the mist into the ancient mountain fortress. The cold winds howled fiercely across the stone walls.\n" * 2,
                encoding="utf-8"
            )
            (trans_dir / f"{ch_str}_hi.md").write_text(
                "नायक कोहरे के बीच से प्राचीन पहाड़ी किले में दाखिल हुआ। ठंडी हवाएं पत्थर की दीवारों से टकराकर सनसना रही थीं।\n" * 2,
                encoding="utf-8"
            )

            roster_data = {
                "characters": {
                    "Narrator": {"voice_persona": "Aoede", "gender": "female"},
                    "Hero": {"voice_persona": "Fenrir", "gender": "male"}
                }
            }
            (pdir / "character_roster.json").write_text(json.dumps(roster_data), encoding="utf-8")

            reg_data = {
                "Narrator": {"voice": "Aoede", "pitch": 1.0, "speed": 1.0},
                "Hero": {"voice": "Fenrir", "pitch": 1.0, "speed": 1.0}
            }
            (pdir / "voice_registry.json").write_text(json.dumps(reg_data), encoding="utf-8")

            script_data = {
                "chapter_num": 1,
                "segments": [
                    {"index": 1, "type": "narration", "speaker": "Narrator", "text": "नायक कोहरे के बीच से प्राचीन पहाड़ी किले में दाखिल हुआ।"},
                    {"index": 2, "type": "dialogue", "speaker": "Hero", "text": "कोई है यहाँ?"}
                ]
            }
            (scripts_dir / f"{ch_str}_hi_script.json").write_text(json.dumps(script_data), encoding="utf-8")

            report = audit_chapter_gates(pdir, chapter_num=1, active_speakers=["Narrator", "Hero"])

            self.assertEqual(report["gate_0"]["status"], "PASS")
            self.assertEqual(report["gate_1"]["status"], "PASS")
            self.assertEqual(report["gate_2"]["status"], "PASS")
            self.assertEqual(report["gate_3"]["status"], "PASS")
            self.assertEqual(report["overall_status"], "ALL GATES 100% PASSED")
            self.assertEqual(report["gate_2"]["total_segments"], 2)

    def test_voice_collision_detection(self):
        """Verify Gate 1 catches deliberate voice collisions."""
        import tempfile
        import json

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            roster_p = tmp / "character_roster.json"
            registry_p = tmp / "voice_registry.json"

            with open(roster_p, "w") as f:
                json.dump({"characters": {
                    "Hero": {"voice_persona": "Aoede"},
                    "Villain": {"voice_persona": "Aoede"}
                }}, f)
            with open(registry_p, "w") as f:
                json.dump({
                    "Hero": {"voice": "Aoede", "pitch": 1.0, "speed": 1.0},
                    "Villain": {"voice": "Aoede", "pitch": 1.0, "speed": 1.0}
                }, f)

            with self.assertRaises(GateAuditError) as ctx:
                audit_gate1_roster(roster_p, registry_p, ["Hero", "Villain"])
            self.assertIn("Voice collision detected", str(ctx.exception))

    def test_audit_gate1_anticensorship_dilution_and_pass(self):
        """Verify Gate 1 Anti-Censorship Agent flags diluted curses and passes authentic translation."""
        eng_sample = "You bastard! I'll see you in hell, you whore!"
        # Diluted polite translation
        hindi_diluted = "तुम दुष्ट हो! मैं तुम्हें देख लूँगा, बुरी स्त्री!"
        res_diluted = audit_gate1_anticensorship_agent(eng_sample, hindi_diluted)
        self.assertEqual(res_diluted["status"], "DILUTED")
        self.assertTrue(len(res_diluted["flagged"]) > 0)
        self.assertLess(res_diluted["score"], 0.8)

        # Gritty authentic translation
        hindi_gritty = "रुक, हरामी! जहन्नुम में जा, कमीनी रंडी!"
        res_gritty = audit_gate1_anticensorship_agent(eng_sample, hindi_gritty)
        self.assertEqual(res_gritty["status"], "PASS")
        self.assertEqual(len(res_gritty["flagged"]), 0)
        self.assertGreaterEqual(res_gritty["score"], 0.8)

    def test_audit_gate2_screenplay_tags(self):
        """Verify Gate 2 Screenplay Tags Auditor validates prosody and vocal tags."""
        import tempfile
        import json

        with tempfile.TemporaryDirectory() as td:
            script_path = Path(td) / "script.json"
            script_data = {
                "chapter_num": 1,
                "segments": [
                    {"index": 1, "type": "narration", "speaker": "Narrator", "text": "नायक ने देखा।", "tags": ["[calm]"]},
                    {"index": 2, "type": "dialogue", "speaker": "Hero", "text": "चलो चलें।", "tags": ["[whispering]"]}
                ]
            }
            script_path.write_text(json.dumps(script_data), encoding="utf-8")
            res = audit_gate2_screenplay_tags(script_path)
            self.assertEqual(res["status"], "PASS")
            self.assertEqual(res["total_segments"], 2)
            self.assertIn("prosody_coverage_pct", res)

        # Non-existent script raises GateAuditError
        with self.assertRaises(GateAuditError):
            audit_gate2_screenplay_tags(Path("/nonexistent/script.json"))

    def test_audit_gate5_master(self):
        """Verify Gate 5 raises GateAuditError on missing file."""
        with self.assertRaises(GateAuditError):
            audit_gate5_master(Path("/nonexistent/master.m4a"))


if __name__ == "__main__":
    unittest.main()
