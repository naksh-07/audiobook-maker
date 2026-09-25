import pytest
from audiobook_factory.pronunciation.language_detector import detect_token_language
from audiobook_factory.pronunciation.contracts import SpokenLanguage
from audiobook_factory.pronunciation.resolver import PronunciationResolver, number_to_hindi_words
from audiobook_factory.pronunciation.spoken_text import SpokenTextEngine
from audiobook_factory.pronunciation.lexicon import PronunciationLexicon, PronunciationEntry
from audiobook_factory.pronunciation.contracts import PronunciationStatus, PronunciationSource, SpokenLanguage

class TestLanguageDetectorAudit:
    def test_urdu_nukta_patterns(self):
        # Should classify as Urdu
        assert detect_token_language("क़लम") == SpokenLanguage.URDU
        assert detect_token_language("ख़ुशी") == SpokenLanguage.URDU
        assert detect_token_language("ग़लत") == SpokenLanguage.URDU
        assert detect_token_language("ज़िंदगी") == SpokenLanguage.URDU
        assert detect_token_language("फ़ैसला") == SpokenLanguage.URDU
        
        # Test standalone char with nukta
        assert detect_token_language("प़") == SpokenLanguage.HINDI # No nukta in URDU_NUKTA_PATTERNS and NUKTA_CHAR is \u093c, so this one actually has nukta? Let's check \u093c. "प़" is प + \u093c
        
    def test_sanskrit_conjuncts(self):
        # Should classify as Sanskrit
        assert detect_token_language("क्षेत्र") == SpokenLanguage.SANSKRIT
        assert detect_token_language("ज्ञान") == SpokenLanguage.SANSKRIT
        assert detect_token_language("श्रद्धा") == SpokenLanguage.SANSKRIT
        assert detect_token_language("ऋतु") == SpokenLanguage.SANSKRIT
        assert detect_token_language("भाषा") == SpokenLanguage.SANSKRIT

    def test_combining_marks_not_split(self):
        # ensure \w or \u0900-\u097f matches words with matras without splitting them
        from audiobook_factory.pronunciation.language_detector import classify_sentence_language
        result = classify_sentence_language("वह क़लम से लिखता है।")
        tokens = [t for lst in result["tokens_by_language"].values() for t in lst]
        assert "क़लम" in tokens
        
class TestResolverAudit:
    def setup_method(self):
        self.resolver = PronunciationResolver(lexicon=PronunciationLexicon())
        
    def test_numeral_expansions(self):
        assert number_to_hindi_words(25) == "पच्चीस"
        assert number_to_hindi_words(100000000) == "दस करोड़" # actually 10000000 is 1 crore, 100000000 is 10 crore
        
    def test_currency_symbol_preservation_and_expansion(self):
        res = self.resolver._apply_deterministic_rules("₹500", SpokenLanguage.HINDI)
        assert res is not None
        assert res[0] == "पाँच सौ रुपये"
        
        res2 = self.resolver._apply_deterministic_rules("$100", SpokenLanguage.HINDI)
        assert res2 is not None
        assert res2[0] == "सौ डॉलर"
        
    def test_compound_units(self):
        res = self.resolver._apply_deterministic_rules("10km", SpokenLanguage.HINDI)
        assert res is not None
        assert res[0] == "दस किलोमीटर"
        
        res2 = self.resolver._apply_deterministic_rules("5kg", SpokenLanguage.HINDI)
        assert res2 is not None
        assert res2[0] == "पाँच किलोग्राम"
        
        res3 = self.resolver._apply_deterministic_rules("25%", SpokenLanguage.HINDI)
        assert res3 is not None
        assert res3[0] == "पच्चीस प्रतिशत"
        
    def test_acronym_phonetics(self):
        res = self.resolver._apply_deterministic_rules("FBI", SpokenLanguage.ENGLISH)
        assert res is not None
        assert res[0] == "एफ़.बी.आई."
        
        res2 = self.resolver._apply_deterministic_rules("CBI", SpokenLanguage.ENGLISH)
        assert res2 is not None
        assert res2[0] == "सी.बी.आई."

class TestSpokenTextAudit:
    def setup_method(self):
        lexicon = PronunciationLexicon()
        lexicon.entries["sherlock_holmes"] = PronunciationEntry(
            canonical_id="sherlock_holmes",
            canonical_text="Sherlock Holmes",
            spoken_form="शरलॉक होम्स",
            status=PronunciationStatus.VERIFIED,
            source=PronunciationSource.MANUAL_OVERRIDE,
            expected_language=SpokenLanguage.HINDI
        )
        lexicon.entries["sherlock"] = PronunciationEntry(
            canonical_id="sherlock",
            canonical_text="Sherlock",
            spoken_form="शरलॉक",
            status=PronunciationStatus.VERIFIED,
            source=PronunciationSource.MANUAL_OVERRIDE,
            expected_language=SpokenLanguage.HINDI
        )
        self.resolver = PronunciationResolver(lexicon=lexicon)
        self.engine = SpokenTextEngine(resolver=self.resolver)
        
    def test_multi_word_matching_order(self):
        # Sherlock Holmes should be matched first before Sherlock
        res = self.engine.resolve_text("Sherlock Holmes and Sherlock")
        assert "शरलॉक होम्स" in res.spoken_text
        # the remaining Sherlock should be just "शरलॉक"
        assert res.spoken_text.count("शरलॉक") == 2
        
    def test_neural_acting_tags_protection(self):
        text = "[whispers] I am here, [gasp] Sherlock! [shouting] Help!"
        res = self.engine.resolve_text(text)
        
        assert "[whispers]" in res.spoken_text
        assert "[gasp]" in res.spoken_text
        assert "[shouting]" in res.spoken_text
        
        # Display text should not have tags
        assert "[whispers]" not in res.display_text
        assert "[gasp]" not in res.display_text
        assert "[shouting]" not in res.display_text
        assert "I am here, Sherlock! Help!" in res.display_text.strip()
