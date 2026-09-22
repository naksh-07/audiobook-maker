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
PROJECT_DIR = ROOT_DIR / "audiobooks" / "projects" / "witcher1"


class TestMultiGateAuditor(unittest.TestCase):
    def test_chapter_5_full_audit(self):
        """Verify Chapter 5 passes all gates with 0 collisions and 100% coverage."""
        active_cast = ["Narrator", "Geralt", "Nenneke", "Falwick", "Tailles"]
        report = audit_chapter_gates(PROJECT_DIR, chapter_num=5, active_speakers=active_cast)

        self.assertEqual(report["gate_0"]["status"], "PASS")
        self.assertEqual(report["gate_1"]["status"], "PASS")
        self.assertEqual(report["gate_2"]["status"], "PASS")
        self.assertEqual(report["gate_3"]["status"], "PASS")
        self.assertEqual(report["overall_status"], "ALL GATES 100% PASSED")
        self.assertEqual(report["gate_2"]["total_segments"], 49)
        self.assertEqual(report["gate_3"]["total_acts"], 4)

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
        script_path = PROJECT_DIR / "scripts" / "chapter_005_hi_script.json"
        if script_path.exists():
            res = audit_gate2_screenplay_tags(script_path)
            self.assertEqual(res["status"], "PASS")
            self.assertGreater(res["total_segments"], 0)
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
