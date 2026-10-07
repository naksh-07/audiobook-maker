#!/usr/bin/env python3
"""
Audiobook Factory - Language & Dialogue Calibration Corpus (Prompt 4 Hardening).
Defines a canonical 20-segment representative calibration corpus spanning:
1. Hindi narration
2. English narration
3. Hinglish dialogue
4. Indian proper names
5. Foreign names in Hindi
6. Foreign fantasy places
7. Devanagari numerals
8. Latin numerals and currencies
9. Compound measurement units
10. Acronyms & initialisms
11. Emotionally charged dominant threat
12. Fearful submissive reaction
13. Rapid dialogue counter
14. Short replies
15. Abrupt interruption cut
16. Immediate interrupting take-over
17. Multi-speaker turn transition
18. Intimate whisper exchange
19. Dramatic scene transition pause
20. Narration-dialogue sandwich
"""

from __future__ import annotations
from typing import Dict, Any, List
from pydantic import BaseModel, Field

from audiobook_factory.contracts import ScreenplaySegment
from audiobook_factory.pronunciation.contracts import SpokenLanguage, PronunciationStatus


class LanguageDialogueCalibrationItem(BaseModel):
    """Calibrated ground-truth specification for language, pronunciation, and dialogue turn."""
    uid: str
    index: int
    category: str
    speaker: str
    expected_language: SpokenLanguage
    literary_text: str
    expected_spoken_contains: str
    conversational_dynamic: str = "normal"
    turn_taking_intent: str = "immediate"
    expected_pause_ms_min: int = 0
    expected_pause_ms_max: int = 1500
    is_interruption: bool = False
    notes: str = ""


class LanguageDialogueCalibrationCorpus:
    """
    Standardized benchmark corpus for evaluating pronunciation accuracy,
    language fidelity, forced alignment boundaries, speaker consistency,
    conversational turn latency, and dialogue chemistry.
    """

    ITEMS: List[LanguageDialogueCalibrationItem] = [
        # 1. Hindi Narration
        LanguageDialogueCalibrationItem(
            uid="calib_01_hi_narration",
            index=1,
            category="hindi_narration",
            speaker="Narrator",
            expected_language=SpokenLanguage.HINDI,
            literary_text="रात का घना सन्नाटा उस प्राचीन हवेली की दीवारों पर धीरे-धीरे पसर रहा था।",
            expected_spoken_contains="सन्नाटा",
            conversational_dynamic="narrative_exposition",
            turn_taking_intent="narrative",
            expected_pause_ms_min=300,
            expected_pause_ms_max=600,
            notes="Formal literary Hindi narrative cadence.",
        ),
        # 2. English Narration
        LanguageDialogueCalibrationItem(
            uid="calib_02_en_narration",
            index=2,
            category="english_narration",
            speaker="Narrator",
            expected_language=SpokenLanguage.ENGLISH,
            literary_text="The shadows lengthened across the cobblestones as the cold autumn wind began to howl.",
            expected_spoken_contains="cobblestones",
            conversational_dynamic="narrative_exposition",
            turn_taking_intent="narrative",
            expected_pause_ms_min=300,
            expected_pause_ms_max=600,
            notes="Atmospheric English literary narration.",
        ),
        # 3. Hinglish Dialogue
        LanguageDialogueCalibrationItem(
            uid="calib_03_hinglish_colloquial",
            index=3,
            category="hinglish_dialogue",
            speaker="Vikram",
            expected_language=SpokenLanguage.HINDI,
            literary_text="Doctor ने साफ़ कह दिया है कि मरीज को तुरंत City Hospital ले जाना पड़ेगा।",
            expected_spoken_contains="Doctor",
            conversational_dynamic="colloquial_code_switch",
            turn_taking_intent="immediate",
            expected_pause_ms_min=200,
            expected_pause_ms_max=500,
            notes="Natural Hindustani speech with integrated English loanwords.",
        ),
        # 4. Indian Proper Names
        LanguageDialogueCalibrationItem(
            uid="calib_04_indian_proper_names",
            index=4,
            category="indian_proper_names",
            speaker="Narrator",
            expected_language=SpokenLanguage.HINDI,
            literary_text="कुरुक्षेत्र के मैदान में युधिष्ठिर और अश्वत्थामा आमने-सामने खड़े थे।",
            expected_spoken_contains="युधिष्ठिर",
            conversational_dynamic="epic_narrative",
            turn_taking_intent="narrative",
            expected_pause_ms_min=350,
            expected_pause_ms_max=650,
            notes="Epic Sanskrit-derived mythological character names.",
        ),
        # 5. Foreign Names in Hindi Dialogue
        LanguageDialogueCalibrationItem(
            uid="calib_05_foreign_names_in_hindi",
            index=5,
            category="foreign_names_in_hindi",
            speaker="Inspector",
            expected_language=SpokenLanguage.HINDI,
            literary_text="मैंने स्वयं Sherlock Holmes और Dr. Watson को लंदन में देखा था।",
            expected_spoken_contains="शरलॉक होम्स",
            conversational_dynamic="dialogue_statement",
            turn_taking_intent="immediate",
            expected_pause_ms_min=250,
            expected_pause_ms_max=550,
            notes="Option 1A Hybrid phonetically respelled foreign entities in Hindi dialogue.",
        ),
        # 6. Foreign Fantasy Places
        LanguageDialogueCalibrationItem(
            uid="calib_06_foreign_fantasy_place",
            index=6,
            category="foreign_places",
            speaker="Inspector",
            expected_language=SpokenLanguage.HINDI,
            literary_text="सर्दियों के पहले हमें Baker Street की सुरक्षा पंक्ति में पहुँचना होगा।",
            expected_spoken_contains="बेकर स्ट्रीट",
            conversational_dynamic="grim_dialogue",
            turn_taking_intent="immediate",
            expected_pause_ms_min=250,
            expected_pause_ms_max=500,
            notes="Foreign proper geography preserved without transliteration corruption.",
        ),
        # 7. Devanagari Numerals
        LanguageDialogueCalibrationItem(
            uid="calib_07_devanagari_numerals",
            index=7,
            category="devanagari_numerals",
            speaker="Narrator",
            expected_language=SpokenLanguage.HINDI,
            literary_text="ग्रंथ का अध्याय ५ अब आरंभ होता है।",
            expected_spoken_contains="पाँच",
            conversational_dynamic="chapter_header",
            turn_taking_intent="narrative",
            expected_pause_ms_min=400,
            expected_pause_ms_max=800,
            notes="Devanagari digit 5 expanded deterministically to पाँच.",
        ),
        # 8. Latin Numerals & Currencies
        LanguageDialogueCalibrationItem(
            uid="calib_08_latin_numerals_currencies",
            index=8,
            category="currency_and_numbers",
            speaker="Merchant",
            expected_language=SpokenLanguage.HINDI,
            literary_text="इस सौदे के लिए मुझे ₹500 और 25% कमीशन चाहिए।",
            expected_spoken_contains="पाँच सौ रुपये",
            conversational_dynamic="transactional_dialogue",
            turn_taking_intent="immediate",
            expected_pause_ms_min=250,
            expected_pause_ms_max=500,
            notes="Currency symbol ₹500 expanded to पाँच सौ रुपये and 25% to पच्चीस प्रतिशत.",
        ),
        # 9. Compound Units
        LanguageDialogueCalibrationItem(
            uid="calib_09_compound_units",
            index=9,
            category="compound_units",
            speaker="Scout",
            expected_language=SpokenLanguage.HINDI,
            literary_text="शत्रु की सेना यहाँ से 10km दूर पहाड़ी पर डेरा डाले हुए है।",
            expected_spoken_contains="दस किलोमीटर",
            conversational_dynamic="urgent_report",
            turn_taking_intent="immediate",
            expected_pause_ms_min=200,
            expected_pause_ms_max=450,
            notes="Compound metric unit 10km expanded to दस किलोमीटर.",
        ),
        # 10. Acronyms & Initialisms
        LanguageDialogueCalibrationItem(
            uid="calib_10_acronyms_initialisms",
            index=10,
            category="acronyms",
            speaker="Agent",
            expected_language=SpokenLanguage.HINDI,
            literary_text="इस अभियान की रिपोर्ट सीधे FBI और CBI के विशेष कक्ष को भेजी जाएगी।",
            expected_spoken_contains="एफ़.बी.आई.",
            conversational_dynamic="formal_briefing",
            turn_taking_intent="immediate",
            expected_pause_ms_min=250,
            expected_pause_ms_max=500,
            notes="Uppercase acronyms FBI and CBI expanded with dot-separated Hindi phonetics.",
        ),
        # 11. Emotionally Charged Dominant Threat
        LanguageDialogueCalibrationItem(
            uid="calib_11_emotional_threat",
            index=11,
            category="chemistry_threat",
            speaker="Baron",
            expected_language=SpokenLanguage.HINDI,
            literary_text="अगर तुमने दोबारा झूठ बोलने की हिम्मत की, तो तुम्हारी जुबान कटवा दूँगा!",
            expected_spoken_contains="जुबान",
            conversational_dynamic="intimidation",
            turn_taking_intent="dominant_threat",
            expected_pause_ms_min=500,
            expected_pause_ms_max=900,
            notes="High adrenaline intimidation line expecting hesitant submissive reply.",
        ),
        # 12. Fearful Submissive Reaction
        LanguageDialogueCalibrationItem(
            uid="calib_12_emotional_submissive",
            index=12,
            category="chemistry_submissive",
            speaker="Servant",
            expected_language=SpokenLanguage.HINDI,
            literary_text="म-मुझसे भूल हो गई हुज़ूर... बख्श दीजिए!",
            expected_spoken_contains="हुज़ूर",
            conversational_dynamic="fearful_submission",
            turn_taking_intent="delayed_reaction",
            expected_pause_ms_min=600,
            expected_pause_ms_max=1100,
            notes="Yielded vocal energy following threat with delayed response latency.",
        ),
        # 13. Rapid Dialogue Counter
        LanguageDialogueCalibrationItem(
            uid="calib_13_rapid_counter",
            index=13,
            category="chemistry_rapid",
            speaker="Rival",
            expected_language=SpokenLanguage.HINDI,
            literary_text="तुम गलत सोच रहे हो, फैसला मेरा होगा!",
            expected_spoken_contains="फैसला",
            conversational_dynamic="eager_counter",
            turn_taking_intent="eager_counter",
            expected_pause_ms_min=80,
            expected_pause_ms_max=200,
            notes="Aggressive counter retort with compressed 120ms turn-taking gap.",
        ),
        # 14. Short Replies
        LanguageDialogueCalibrationItem(
            uid="calib_14_short_reply",
            index=14,
            category="short_reply",
            speaker="Sorceress",
            expected_language=SpokenLanguage.HINDI,
            literary_text="कभी नहीं।",
            expected_spoken_contains="कभी नहीं",
            conversational_dynamic="terse_dismissal",
            turn_taking_intent="immediate",
            expected_pause_ms_min=200,
            expected_pause_ms_max=450,
            notes="Minimalist dialogue line with decisive inflection.",
        ),
        # 15. Interruption Cutoff (Speaker A Cut Off)
        LanguageDialogueCalibrationItem(
            uid="calib_15_interruption_cutoff",
            index=15,
            category="interruption_cut",
            speaker="Companion",
            expected_language=SpokenLanguage.HINDI,
            literary_text="लेकिन सुनो, मुझे लगा था कि हम वहाँ—",
            expected_spoken_contains="लेकिन",
            conversational_dynamic="interruption",
            turn_taking_intent="abrupt_cut",
            expected_pause_ms_min=25,
            expected_pause_ms_max=60,
            is_interruption=True,
            notes="Line ends with em-dash, triggering abrupt cut (35ms silence, 2ms crossfade).",
        ),
        # 16. Interruption Eager Takeover (Speaker B Cuts In)
        LanguageDialogueCalibrationItem(
            uid="calib_16_interruption_eager",
            index=16,
            category="interruption_takeover",
            speaker="Protagonist",
            expected_language=SpokenLanguage.HINDI,
            literary_text="खामोश रहो! कोई आ रहा है।",
            expected_spoken_contains="खामोश",
            conversational_dynamic="counter",
            turn_taking_intent="immediate",
            expected_pause_ms_min=0,
            expected_pause_ms_max=50,
            is_interruption=False,
            notes="Interrupting speaker onset at 0ms pause before line.",
        ),
        # 17. Multi-Speaker Turn Transition
        LanguageDialogueCalibrationItem(
            uid="calib_17_multi_speaker_turn",
            index=17,
            category="multi_speaker_transition",
            speaker="Veteran_Ally",
            expected_language=SpokenLanguage.HINDI,
            literary_text="अगर दोनों की बहस खत्म हो गई हो, तो हम आगे बढ़ें?",
            expected_spoken_contains="बहस",
            conversational_dynamic="third_party_intervention",
            turn_taking_intent="normal",
            expected_pause_ms_min=250,
            expected_pause_ms_max=500,
            notes="Third distinct character breaking into dialogue without identity leakage.",
        ),
        # 18. Intimate Whisper Exchange
        LanguageDialogueCalibrationItem(
            uid="calib_18_intimate_whisper",
            index=18,
            category="intimate_whisper",
            speaker="Sorceress",
            expected_language=SpokenLanguage.HINDI,
            literary_text="[whispers] आँखें बंद करो और बस मेरी आवाज़ सुनो।",
            expected_spoken_contains="[whispers]",
            conversational_dynamic="intimate_closeness",
            turn_taking_intent="whisper_proximity",
            expected_pause_ms_min=300,
            expected_pause_ms_max=600,
            notes="Protected acting tag with close-mic proximity and gentle pre-roll breath.",
        ),
        # 19. Dramatic Scene Transition Pause
        LanguageDialogueCalibrationItem(
            uid="calib_19_scene_transition_pause",
            index=19,
            category="scene_transition",
            speaker="Narrator",
            expected_language=SpokenLanguage.HINDI,
            literary_text="और इसी के साथ उस नगर का अंतिम प्रकाश भी बुझ गया।",
            expected_spoken_contains="प्रकाश",
            conversational_dynamic="dramatic_silence",
            turn_taking_intent="scene_boundary",
            expected_pause_ms_min=1100,
            expected_pause_ms_max=1600,
            notes="High tension dramatic silence before next scene beat.",
        ),
        # 20. Narration -> Dialogue -> Narration Sandwich
        LanguageDialogueCalibrationItem(
            uid="calib_20_narration_sandwich",
            index=20,
            category="narrative_sandwich",
            speaker="Narrator",
            expected_language=SpokenLanguage.HINDI,
            literary_text="दरवाज़ा खुला और कमरे के अंदर एक अजनबी ने कदम रखा।",
            expected_spoken_contains="अजनबी",
            conversational_dynamic="transition_lead_in",
            turn_taking_intent="narrative",
            expected_pause_ms_min=300,
            expected_pause_ms_max=550,
            notes="Smooth transition between narrative setup and subsequent character speech.",
        ),
    ]

    @classmethod
    def get_screenplay_segments(cls) -> List[ScreenplaySegment]:
        """Converts calibration corpus into standardized ScreenplaySegment instances."""
        segments: List[ScreenplaySegment] = []
        for it in cls.ITEMS:
            seg_type = "narration" if it.speaker in ("Narrator", "Foley") else "dialogue"
            seg = ScreenplaySegment(
                uid=it.uid,
                index=it.index,
                type=seg_type,
                speaker=it.speaker,
                text=it.literary_text,
                pause_after_ms=(it.expected_pause_ms_min + it.expected_pause_ms_max) // 2,
                conversational_dynamic=it.conversational_dynamic,
                is_interruption=it.is_interruption,
            )
            segments.append(seg)
        return segments

    @classmethod
    def evaluate_item_pronunciation(
        cls,
        item: LanguageDialogueCalibrationItem,
        resolved_spoken: str,
    ) -> bool:
        """Evaluates whether resolved spoken text matches the calibrated ground-truth expectation."""
        return item.expected_spoken_contains in resolved_spoken
