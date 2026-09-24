import sys
import unittest
from pathlib import Path

# Add repo root to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from standalone_pipeline import parse_literature_offline

class TestOfflineScreenplayParser(unittest.TestCase):
    def test_offline_narrator_mode(self):
        sample_text = (
            "This is the first paragraph of standard novel narration. It sets the scene in a dark forest.\n\n"
            "This is the second paragraph where the adventurer walks along the winding path."
        )
        segments = parse_literature_offline(sample_text, is_hindi=False, mode="narrator")
        self.assertGreaterEqual(len(segments), 1)
        for s in segments:
            self.assertEqual(s["speaker"], "Narrator")
            self.assertEqual(s["type"], "narration")

    def test_offline_dialogue_hindi_mode(self):
        sample_hindi = (
            "एक शाम की बात है।\n\n"
            "गरिमा ने कहा- चलो चलते हैं। सोनू बोला- हां ठीक है।"
        )
        segments = parse_literature_offline(sample_hindi, is_hindi=True, mode="dialogue")
        speakers = [s["speaker"] for s in segments]
        types = [s["type"] for s in segments]
        self.assertIn("गरिमा", speakers)
        self.assertIn("सोनू", speakers)
        self.assertIn("dialogue", types)

    def test_offline_superchunk_minimum_requests(self):
        sample_hindi = (
            "एक शाम की बात है।\n\n"
            "गरिमा ने कहा- चलो चलते हैं। सोनू बोला- हां ठीक है।"
        )
        segments = parse_literature_offline(sample_hindi, is_hindi=True, mode="narrator", max_chunk_words=550)
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0]["speaker"], "Narrator")

    def test_offline_screenplay_script_mode(self):
        script_text = (
            "NARRATOR: The battle was fierce.\n"
            "GERALT: Stand your ground!\n"
            "YENNEFER: Behind you!"
        )
        segments = parse_literature_offline(script_text, is_hindi=False, mode="screenplay")
        self.assertEqual(len(segments), 3)
        self.assertEqual(segments[0]["speaker"], "Narrator")
        self.assertEqual(segments[1]["speaker"], "GERALT")
        self.assertEqual(segments[2]["speaker"], "YENNEFER")

if __name__ == "__main__":
    unittest.main()
