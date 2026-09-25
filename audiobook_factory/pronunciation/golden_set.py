#!/usr/bin/env python3
"""
Audiobook Factory - Permanent Golden Pronunciation Regression Bank.
Contains difficult, regression-prone test cases across 8 essential dimensions:
1. Indian historical/mythological names
2. English proper nouns inside Hindi dialogue (Option 1A Hybrid)
3. Sanskrit loanwords (Tatsama)
4. Urdu / Hindustani vocabulary
5. Foreign fantasy / historical places
6. Acronyms & initialisms
7. Numerals, dates, currencies, and compound units
8. Intentional code-switched phrases
"""

from __future__ import annotations
from typing import Dict, Any, List, Tuple
from .contracts import PronunciationStatus, SpokenLanguage


GOLDEN_PRONUNCIATION_CASES: List[Dict[str, Any]] = [
    # 1. Indian Historical & Mythological Names
    {
        "id": "gold_01_yudhishthira",
        "category": "indian_mythological",
        "literary_input": "युधिष्ठिर ने मौन धारण कर लिया।",
        "expected_spoken_contains": "युधिष्ठिर",
        "expected_lang": SpokenLanguage.HINDI,
    },
    {
        "id": "gold_02_ashwatthama",
        "category": "indian_mythological",
        "literary_input": "अश्वत्थामा ने प्रतिज्ञा ली।",
        "expected_spoken_contains": "अश्वत्थामा",
        "expected_lang": SpokenLanguage.HINDI,
    },
    # 2. English Names inside Hindi Dialogue (Option 1A Hybrid)
    {
        "id": "gold_03_sherlock_holmes",
        "category": "foreign_name_in_hindi",
        "literary_input": "उसने कहा, “Sherlock Holmes यहाँ आया था।”",
        "expected_spoken_contains": "शरलॉक होम्स",
        "expected_lang": SpokenLanguage.ENGLISH,
    },
    {
        "id": "gold_04_watson_in_hindi",
        "category": "foreign_name_in_hindi",
        "literary_input": "कमरे में Dr. Watson बैठे थे।",
        "expected_spoken_contains": "डॉक्टर वॉटसन",
        "expected_lang": SpokenLanguage.ENGLISH,
    },
    # 3. Sanskrit Tatsama & Conjuncts
    {
        "id": "gold_05_sanskrit_moksha",
        "category": "sanskrit_tatsama",
        "literary_input": "उसे मोक्ष की प्राप्ति नहीं हुई।",
        "expected_spoken_contains": "मोक्ष",
        "expected_lang": SpokenLanguage.SANSKRIT,
    },
    {
        "id": "gold_06_sanskrit_astitva",
        "category": "sanskrit_tatsama",
        "literary_input": "संपूर्ण अस्तित्व उस एक क्षण पर टिका था।",
        "expected_spoken_contains": "अस्तित्व",
        "expected_lang": SpokenLanguage.SANSKRIT,
    },
    # 4. Urdu / Hindustani Vocabulary (Nukta Preservation)
    {
        "id": "gold_07_urdu_zindagi",
        "category": "urdu_nukta",
        "literary_input": "यह ज़िंदगी बहुत अजीब है।",
        "expected_spoken_contains": "ज़िंदगी",
        "expected_lang": SpokenLanguage.URDU,
    },
    {
        "id": "gold_08_urdu_waqt",
        "category": "urdu_nukta",
        "literary_input": "वक़्त किसी का इंतज़ार नहीं करता।",
        "expected_spoken_contains": "वक़्त",
        "expected_lang": SpokenLanguage.URDU,
    },
    # 5. Foreign Place Names
    {
        "id": "gold_09_kaer_morhen",
        "category": "foreign_place",
        "literary_input": "वे Kaer Morhen की ओर बढ़े।",
        "expected_spoken_contains": "केर मॉरहेन",
        "expected_lang": SpokenLanguage.FOREIGN,
    },
    # 6. Acronyms & Initialisms
    {
        "id": "gold_10_acronym_fbi",
        "category": "acronym",
        "literary_input": "FBI के एजेंट बाहर खड़े थे।",
        "expected_spoken_contains": "एफ़.बी.आई.",
        "expected_lang": SpokenLanguage.ENGLISH,
    },
    {
        "id": "gold_11_acronym_cbi",
        "category": "acronym",
        "literary_input": "मामला CBI को सौंप दिया गया।",
        "expected_spoken_contains": "सी.बी.आई.",
        "expected_lang": SpokenLanguage.HINDI,
    },
    {
        "id": "gold_12_acronym_vip",
        "category": "acronym",
        "literary_input": "वह एक VIP मेहमान था।",
        "expected_spoken_contains": "वी.आई.पी.",
        "expected_lang": SpokenLanguage.ENGLISH,
    },
    # 7. Numerals, Currencies, and Units
    {
        "id": "gold_13_currency_rupee",
        "category": "currency",
        "literary_input": "उसने ₹500 दिए।",
        "expected_spoken_contains": "पाँच सौ रुपये",
        "expected_lang": SpokenLanguage.HINDI,
    },
    {
        "id": "gold_14_currency_dollar",
        "category": "currency",
        "literary_input": "कीमत $100 थी।",
        "expected_spoken_contains": "सौ डॉलर",
        "expected_lang": SpokenLanguage.HINDI,
    },
    {
        "id": "gold_15_percentage",
        "category": "percentage",
        "literary_input": "मुनाफ़ा 25% बढ़ गया।",
        "expected_spoken_contains": "पच्चीस प्रतिशत",
        "expected_lang": SpokenLanguage.HINDI,
    },
    {
        "id": "gold_16_compound_units",
        "category": "compound_units",
        "literary_input": "किला यहाँ से 10km दूर है।",
        "expected_spoken_contains": "दस किलोमीटर",
        "expected_lang": SpokenLanguage.HINDI,
    },
    {
        "id": "gold_17_deva_numerals",
        "category": "numerals",
        "literary_input": "अध्याय ५ समाप्त हुआ।",
        "expected_spoken_contains": "पाँच",
        "expected_lang": SpokenLanguage.HINDI,
    },
    # 8. Intentional Code-Switched Sentences
    {
        "id": "gold_18_code_switch_doctor",
        "category": "code_switch",
        "literary_input": "Doctor ने कहा कि वह बच जाएगा।",
        "expected_spoken_contains": "Doctor",
        "expected_lang": SpokenLanguage.ENGLISH,
    },
    {
        "id": "gold_19_code_switch_station",
        "category": "code_switch",
        "literary_input": "गाड़ी Station पर रुक गई।",
        "expected_spoken_contains": "Station",
        "expected_lang": SpokenLanguage.ENGLISH,
    },
    # 9. Neural Performance Tags Protection
    {
        "id": "gold_20_acting_tag_whisper",
        "category": "acting_tag_protection",
        "literary_input": "[whispers] वह चुपके से बोला।",
        "expected_spoken_contains": "[whispers]",
        "expected_lang": SpokenLanguage.HINDI,
    },
]


def run_golden_pronunciation_suite(spoken_engine: Any) -> Dict[str, Any]:
    """
    Executes the golden pronunciation regression suite against a SpokenTextEngine instance.
    Returns audit summary with pass/fail counts and specific diagnostics.
    """
    passed_count = 0
    failed_cases = []

    for case in GOLDEN_PRONUNCIATION_CASES:
        res = spoken_engine.resolve_text(case["literary_input"])
        exp = case["expected_spoken_contains"]
        if exp in res.spoken_text:
            passed_count += 1
        else:
            failed_cases.append({
                "id": case["id"],
                "input": case["literary_input"],
                "expected": exp,
                "actual_spoken": res.spoken_text,
            })

    total = len(GOLDEN_PRONUNCIATION_CASES)
    is_all_passed = (passed_count == total)

    return {
        "total": total,
        "passed": passed_count,
        "failed": len(failed_cases),
        "all_passed": is_all_passed,
        "failures": failed_cases,
    }
