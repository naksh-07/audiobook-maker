#!/usr/bin/env python3
"""
Unit Tests for Robust Chapter Segmenter and Meso-Tier Semantic Splitter.
"""

import unittest
from audiobook_factory.chapter_segmenter import (
    segment_chapters_from_text,
    split_large_chapter_on_semantic_boundary,
)


class TestChapterSegmenter(unittest.TestCase):

    def test_markdown_and_roman_and_word_headings(self):
        book_prose = """
# The Boy Who Lived

Mr. and Mrs. Dursley were proud to say that they were perfectly normal.
They were the last people you'd expect to be involved in anything strange.

## The Vanishing Glass

Nearly ten years had passed since the Dursleys had come home.
The house looked just the same as it had on that long ago evening.

Chapter III: The Letters from No One

The escape of the Brazilian boa constrictor earned Harry his longest punishment.
By the time he was allowed out of his cupboard, the summer holidays had started.

FOUR: The Keeper of the Keys

BOOM. They knocked again. Dudley jerked awake.
Where's the cannon? he said stupidly.

अध्याय 5: डायागन एली

अगली सुबह हैरी जल्दी ही जाग गया।
यद्यपि वह जानता था कि अब सुबह हो चुकी है, उसने अपनी आँखें बंद रखीं।
"""
        chapters = segment_chapters_from_text(book_prose)
        self.assertGreaterEqual(len(chapters), 5)
        titles = [c["title"] for c in chapters]
        self.assertTrue(any("The Boy Who Lived" in t for t in titles))
        self.assertTrue(any("The Vanishing Glass" in t for t in titles))
        self.assertTrue(any("The Letters from No One" in t for t in titles))
        self.assertTrue(any("The Keeper of the Keys" in t for t in titles))
        self.assertTrue(any("डायागन एली" in t for t in titles))

    def test_ambiguity_protection_against_dialogue_and_uppercase(self):
        # Text with loud shouting or uppercase words inside dialogue that should NOT be chapters
        tricky_prose = """
Chapter 1: The Dark Forest

The soldiers marched into the thicket under the heavy rain.

"HALT!" shouted the sergeant. "NOBODY MOVE!"

They stopped where they stood. The woods were dead silent.

"ARE YOU READY?" whispered the scout from the shadows.
"""
        chapters = segment_chapters_from_text(tricky_prose)
        self.assertEqual(len(chapters), 1)
        self.assertIn("The Dark Forest", chapters[0]["title"])
        self.assertIn("HALT!", chapters[0]["content"])

    def test_prologue_preservation(self):
        prose_with_prologue = """
A long long time ago, before the conjunction of the spheres, ancient magic ruled the wilderness.
Monsters roamed freely across the valleys, preying on mortal villages and unwary travelers.
The kings built strong stone fortresses, but stone was no match for the beasts of the darkness.
This is the history of the continent before the first witchers were made.

Chapter 1: The First Witcher

Geralt arrived at the gates of Wyzim on a cold autumn evening.
"""
        chapters = segment_chapters_from_text(prose_with_prologue)
        self.assertEqual(len(chapters), 2)
        self.assertIn("Prologue", chapters[0]["title"])
        self.assertIn("Chapter 1", chapters[1]["title"])

    def test_semantic_splitting_on_scene_break(self):
        part_a = "Geralt rode Roach through the dense forest. " * 1000  # ~7,000 words
        divider = "\n\n* * *\n\n"
        part_b = "At dawn he arrived at the tavern of Blaviken. " * 1000  # ~8,000 words
        long_content = part_a + divider + part_b

        parts = split_large_chapter_on_semantic_boundary("Chapter 1", long_content, max_words=12000)
        self.assertEqual(len(parts), 2)
        self.assertEqual(parts[0]["title"], "Chapter 1 (Part 1)")
        self.assertEqual(parts[1]["title"], "Chapter 1 (Part 2)")
        self.assertLessEqual(parts[0]["words"], 12000)
        self.assertLessEqual(parts[1]["words"], 12000)

    def test_semantic_splitting_on_paragraph_boundary(self):
        # No scene break, but two large paragraphs
        para_a = "The storm raged outside the ancient castle walls. " * 1000  # ~8,000 words
        para_b = "Inside the fireplace flickered with a warm comforting glow. " * 1000  # ~9,000 words
        long_content = para_a + "\n\n" + para_b

        parts = split_large_chapter_on_semantic_boundary("Chapter 2", long_content, max_words=12000)
        self.assertEqual(len(parts), 2)
        self.assertIn("Part 1", parts[0]["title"])
        self.assertIn("Part 2", parts[1]["title"])


if __name__ == "__main__":
    unittest.main()
