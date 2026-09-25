#!/usr/bin/env python3
"""
Unit tests executing the permanent Golden Pronunciation Regression Bank.
"""

import unittest
from audiobook_factory.pronunciation.lexicon import PronunciationLexicon
from audiobook_factory.pronunciation.resolver import PronunciationResolver
from audiobook_factory.pronunciation.spoken_text import SpokenTextEngine
from audiobook_factory.pronunciation.golden_set import run_golden_pronunciation_suite, GOLDEN_PRONUNCIATION_CASES


class TestGoldenPronunciationCases(unittest.TestCase):

    def setUp(self):
        self.lexicon = PronunciationLexicon()
        self.lexicon.seed_default_lexicon()
        self.resolver = PronunciationResolver(self.lexicon)
        self.engine = SpokenTextEngine(self.resolver)

    def test_all_golden_pronunciation_cases_pass(self):
        report = run_golden_pronunciation_suite(self.engine)
        if not report["all_passed"]:
            fail_summary = "\n".join([f"- {f['id']}: expected '{f['expected']}' in '{f['actual_spoken']}'" for f in report["failures"]])
            self.fail(f"Golden pronunciation suite failed ({report['passed']}/{report['total']}):\n{fail_summary}")
        self.assertTrue(report["all_passed"])
        self.assertEqual(report["passed"], report["total"])


if __name__ == "__main__":
    unittest.main()
