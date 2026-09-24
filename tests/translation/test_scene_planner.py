#!/usr/bin/env python3
"""
Unit tests for Transition-Driven Scene Segmentation & Planning Engine.
Verifies that scene count is determined by actual narrative transitions
(time shifts, location changes, markdown breaks), not an arbitrary fixed quota.
"""

import unittest
from audiobook_factory.translation.scene_planner import ScenePlanner


class TestScenePlanner(unittest.TestCase):

    def test_01_short_chapter_remains_single_scene(self):
        text = (
            "Geralt sat in the temple library reading an ancient volume of history. "
            "The candles flickered gently against the stone walls.\n\n"
            "Nenneke entered quietly, holding a copper tray with warm broth. "
            "'Drink this, Geralt,' she said softly."
        )
        plan = ScenePlanner.plan_chapter(text, chapter_title="Chapter 1")
        self.assertEqual(len(plan.scenes), 1, "Short chapter should remain a single organic scene")
        self.assertIn("Geralt", plan.scenes[0].active_characters)
        self.assertIn("Nenneke", plan.scenes[0].active_characters)

    def test_02_narrative_transitions_drive_scene_boundaries(self):
        # Paragraphs with clear location/time shifts
        p1 = "Geralt sat inside the temple library studying alchemical folios. " * 30
        p2 = "Nenneke watched him carefully from across the dark wooden table. " * 30
        p3 = "Later that evening, Geralt stepped outside into the courtyard under the cold stars. " * 30
        p4 = "A cold wind swept across the stone battlements as guards walked by. " * 30
        p5 = "The next morning, Geralt rode out on the road toward the distant mountains. " * 30
        p6 = "Dust rose from Roach's hooves as travelers made way. " * 30

        full_chapter = f"{p1}\n\n{p2}\n\n{p3}\n\n{p4}\n\n{p5}\n\n{p6}"
        plan = ScenePlanner.plan_chapter(full_chapter, chapter_title="Chapter 2")

        # Must discover multiple scenes based on 'Later that evening' and 'The next morning'
        self.assertGreaterEqual(len(plan.scenes), 2)
        # Verify scene titles reflect transition-driven structure
        self.assertEqual(plan.scenes[0].scene_id, "scene_001")
        self.assertEqual(plan.scenes[1].scene_id, "scene_002")


if __name__ == "__main__":
    unittest.main()
