# Pronunciation, Language Fidelity, Alignment, and Multi-Speaker Dialogue Hardening Report (Prompt 4)

**Author**: Deep Forensic Agentic Pipeline Auditor  
**Date**: October 1, 2026  
**Canonical Project ID**: `proj-audiobook-maker`  
**Repository Working Copy**: `c:\Users\Suraj\Documents\Antigravity\Audiobook`  
**Verification Result**: 84/84 Passing Tests (12 New Golden Hardening Tests + 38 Regression Tests + 34 Pronunciation & Alignment Tests)

---

## 1. Hardening Objectives

Prompt 4 executes the critical mission:
> **Harden pronunciation, language fidelity, alignment, and multi-speaker dialogue quality using the existing architecture.**

The objective is premium studio audiobook dialogue that is:
- **Linguistically correct**: Nuanced Hindustani / Hindi, Sanskritized terms, Urdu vocabulary with correct nuktas, and natural colloquial English loanwords preserved without artificial textbook sanitization.
- **Correctly pronounced**: Explicit pronunciation overrides, foreign names, and BookBible entities reliably reach TTS synthesis without downstream data stripping.
- **Correctly aligned**: Word-level acoustic boundaries correctly mapped across Hindi/Hinglish code-switching, Romanized transliterations, and phonetic expansions of numerals, percentages, and currencies.
- **Naturally paced & conversationally believable**: Latencies calibrated to dramatic context (e.g. aposiopesis/emotional freeze at $\ge 1250$ms, suspense at $\ge 1100$ms, thinking at $\ge 900$ms, normal reaction at $\ge 650$ms, and rapid counter-punches at 120ms).
- **Acoustically crisp on interruptions**: Interrupted speech truncated with snappy 2ms micro-fades and 35ms silence gaps rather than smeared into 15ms room-tone tapers.
- **Free of swallowed or dropped words**: Acoustic audio QA actively audits generated audio against expected phonetic syllables; un-repaired speech defects strictly fail closed.
- **Coupled by conversational chemistry**: Adjacent dialogue turns evaluated and scored by `ConversationalChemistry` during `IntelligentTakeSelector` take selection and `TTSDispatcher` execution.

---

## 2. Subsystems Inspected

A thorough forensic audit was conducted across the following existing production subsystems:
1. **Pronunciation & Lexicon**:
   - `audiobook_factory/pronunciation/lexicon.py` (`PronunciationLexicon`, `PronunciationEntry`)
   - `audiobook_factory/pronunciation/resolver.py` (`PronunciationResolver`, 7-tier resolution hierarchy)
   - `audiobook_factory/pronunciation/spoken_text.py` (`SpokenTextEngine`, `SpokenTextResult`)
   - `audiobook_factory/pronunciation/audio_qa.py` (`PronunciationAudioQA`, `AudioQAResult`)
   - `audiobook_factory/pronunciation/repair.py` (`PronunciationRepairEngine`)
2. **Performance Contracts & Direction**:
   - `audiobook_factory/performance/contracts.py` (`PerformanceDirection`, `TakeVariant`)
   - `audiobook_factory/performance/director.py` (`PerformanceDirector.direct_segment`)
3. **Take Selection & Chemistry**:
   - `audiobook_factory/performance/take_selector.py` (`IntelligentTakeSelector`, `PairwiseTakeJudge`)
   - `audiobook_factory/performance/chemistry.py` (`ConversationalChemistry`, `ChemistryEvaluationResult`)
4. **TTS Dispatch & Candidate Generation**:
   - `audiobook_factory/tts_dispatcher.py` (`TTSDispatcher.synthesize_segment`)
5. **Forced Alignment**:
   - `audiobook_factory/forced_aligner.py` (`WorkstationForcedAligner`, `transliterate_devanagari_to_roman`, `normalize_text_for_alignment`)
6. **Dialogue Editing & Timing**:
   - `audiobook_factory/dialogue_editing/editor.py` (`DialogueEditor`)
   - `audiobook_factory/dialogue_editing/pause_editor.py` (`PauseEditor.realize_pause`)
   - `audiobook_factory/dialogue_editing/timing_realizer.py` (`TimingRealizer`)

---

## 3. Proven Defects and Omissions Found

The deep audit revealed five critical integration defects and downstream downgrades:

### Defect 1: Pronunciation QA Silent Bypass Defect (P0)
- **Finding**: In `tts_dispatcher.py` (lines 1500–1527), when `self.pronunciation_auditor.audit_take` flagged a critical pronunciation omission or defect and `attempt_repair` returned `None`, `winning_take.is_selected` remained `True` from earlier take selection.
- **Impact**: The defective take was permitted into `out_file` and downstream mixing, silently bypassing Gate 2.5.
- **Fix**: When repair fails, explicitly set `winning_take.is_selected = False` and set `selection_reason = "[PRONUNCIATION_QA_FAILED]..."`, tripping the fail-closed halt.

### Defect 2: Text vs. Spoken-Text Downgrade in Alignment & Take Selection (P0)
- **Finding**: While `SpokenTextEngine` expanded numbers, currencies, and foreign names into phonetic spoken forms for TTS (e.g., `₹500` -> `पाँच सौ रुपये`), raw unexpanded literary text was forwarded to `IntelligentTakeSelector.select_best_take` and `WorkstationForcedAligner`.
- **Impact**: `WorkstationForcedAligner.normalize_text_for_alignment` stripped digits, creating token count mismatches and false alignment failures.
- **Fix**: Added `spoken_text` and `pronunciation_metadata` to `PerformanceDirection` contracts. Updated `IntelligentTakeSelector` and `DialogueEditor` to prioritize `direction.spoken_text or text`. Added Hindi numeral expansion (`number_to_hindi_words`) into `forced_aligner.py`.

### Defect 3: Conversational Chemistry Disconnection (P0)
- **Finding**: `ConversationalChemistry.evaluate_dialogue_chemistry` was only referenced in `select_scene_takes` (which was dead code in standard single-segment synthesis). `select_best_take` evaluated takes in total isolation without awareness of the preceding speaker's energy, pitch, or timing.
- **Impact**: Dialogue turn chemistry, emotional contrast, and interruption sharpness had zero effect on take selection.
- **Fix**: Added `_prev_take` tracking in `TTSDispatcher`. Forwarded `prev_take` into `IntelligentTakeSelector.select_best_take`. Applied contextual chemistry scoring and penalization ($< 0.50$).

### Defect 4: Devanagari Conjunct Transliteration Mismatch (P1)
- **Finding**: In `transliterate_devanagari_to_roman`, the composite ligature `ज्ञ` (`ज + ् + ञ`) was transliterated as `jnyan` rather than the standard spoken phonetic `gyan` / `gyaan`.
- **Impact**: CTC forced alignment for words like `ज्ञान` suffered phoneme divergence against acoustic representations.
- **Fix**: Added pre-mapping in `transliterate_devanagari_to_roman` for standard Hindi conjuncts (`ज्ञ` -> `gy`, `क्ष` -> `ksh`, `त्र` -> `tr`, `श्र` -> `shr`).

### Defect 5: Noise-Floor Boundary Micro-Fade Collision with Abrupt Cuts (P1)
- **Finding**: In `DialogueEditor.smooth_take_boundaries`, elevated background noise floors triggered an expansion of micro-fades to 15ms Hann tapers to prevent vocoder noise drop clicks. However, this rule inadvertently expanded tail micro-fades on intentional dramatic cutoffs (`interruption_mode == "abrupt_cut"`).
- **Impact**: Crisp dramatic speech interruptions were smeared into unnatural 15ms acoustic fades.
- **Fix**: Exempted `interruption_mode == "abrupt_cut"` from tail micro-fade expansion, preserving the snappy 2.0ms zero-crossing cutoff.

---

## 4. Changes Made (Files, Functions, Contracts)

| File | Functions / Classes | Modification Description |
|---|---|---|
| [`audiobook_factory/performance/contracts.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/performance/contracts.py) | `PerformanceDirection` | Added `spoken_text: Optional[str]` and `pronunciation_metadata: Optional[List[Dict[str, Any]]]` fields. |
| [`audiobook_factory/performance/director.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/performance/director.py) | `PerformanceDirector.direct_segment` | Extracted `spoken_text` and `pronunciation_metadata` from both dict and `ScreenplaySegment` inputs and passed into `PerformanceDirection`. |
| [`audiobook_factory/performance/take_selector.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/performance/take_selector.py) | `IntelligentTakeSelector.select_take_with_result`, `select_best_take`, `_score_contextual` | Added `prev_take` parameter. Computed dynamic `ConversationalChemistry` between `prev_take` and candidates. Penalized candidates with chemistry score $< 0.50$. Used `effective_text = direction.spoken_text or text` for alignment. Forwarded `prev_take` to `evaluator.evaluate_take`. |
| [`audiobook_factory/tts_dispatcher.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/tts_dispatcher.py) | `TTSDispatcher.synthesize_segment`, `__init__` | Added `self._prev_take = None`. Attached `spoken_text` and `pronunciation_metadata` to `p_dir`. Added fail-closed check for unresolved critical pronunciation tokens. Passed `prev_take` to `select_best_take`. Updated `self._prev_take = winning_take`. Hardened QA failure: un-repaired failures set `winning_take.is_selected = False` triggering fail-closed halt. |
| [`audiobook_factory/forced_aligner.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/forced_aligner.py) | `transliterate_devanagari_to_roman`, `normalize_text_for_alignment` | Pre-mapped ligatures (`ज्ञ` -> `gy`, `क्ष` -> `ksh`, `त्र` -> `tr`, `श्र` -> `shr`). Integrated `number_to_hindi_words` for phonetic numeral expansion during alignment tokenization. |
| [`audiobook_factory/dialogue_editing/editor.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/dialogue_editing/editor.py) | `DialogueEditor.smooth_take_boundaries`, `process_chapter` | Preserved 2.0ms micro-fade for `interruption_mode == "abrupt_cut"` during noise floor smoothing. Supported both dict and `ScreenplaySegment` inputs. Prioritized `spoken_text` over `text` for alignment. |
| [`audiobook_factory/pronunciation/calibration.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/pronunciation/calibration.py) | `LanguageDialogueCalibrationCorpus`, `CalibrationCorpusItem` | Created comprehensive 20-segment benchmark corpus covering foreign names, nuktas, Sanksrit conjuncts, numerals, code-switching, interruptions, and chemistry. |
| [`audiobook_factory/pronunciation/__init__.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/pronunciation/__init__.py) | Module exports | Exported `LanguageDialogueCalibrationCorpus` and `CalibrationCorpusItem`. |

---

## 5. Overrides-to-Synthesis Verification

- Verified via `test_pronunciation_overrides_reach_tts`:
  Explicit manual overrides added to `PronunciationLexicon` (Tier 1) correctly override general vocabulary and BookBible entities. For example, `Kaer Morhen` $\rightarrow$ `केर मॉरहेन` resolves cleanly into `spoken_text` while preserving `literary_text = "हम Kaer Morhen की ओर जा रहे हैं।"`.
- Verified via `test_names_retain_pronunciation_metadata`:
  Pronunciation metadata (original token, resolved token, phonemes, tier, confidence) is preserved on `ScreenplaySegment` and transmitted into `PerformanceDirection.pronunciation_metadata`.

---

## 6. Spoken vs Literary Separation Verification

- The separation invariant is strictly preserved:
  1. `ScreenplaySegment.text` remains sacred, immutable, and literary.
  2. `ScreenplaySegment.spoken_text` is populated with the resolved phonetic pronunciation.
  3. `PerformanceDirection.spoken_text` forwards the spoken representation to `TTSDispatcher`.
  4. Audio synthesis targets `spoken_text`, while subtitle/display/provenance tracking references `literary_text`.
- Verified via `TestSpokenTextEngine.test_01_literary_text_immutability` and `test_spoken_result_immutability`.

---

## 7. Hindi/Hinglish Fidelity Verification

- Natural Hindustani dialogue containing Urdu nuktas (`फ़ैसला`, `क़लम`, `ग़लती`), Sanskrit tatsama conjuncts (`ज्ञान`, `दृष्टि`, `सच्चिदानंद`), and natural English colloquialisms (`Doctor`, `Hospital`, `Police Station`) passes through `SpokenTextEngine` without artificial puritanical sanitization.
- Verified via `test_hindi_hinglish_code_switching_survives` and `test_urdu_nukta_patterns`.

---

## 8. Forced Alignment Benchmark Results

- The benchmark suite in `tests/test_golden_alignment_benchmark.py` and `test_forced_aligner_numeral_expansion` verified 18 distinct alignment scenarios:
  1. Numerals and currency symbols (`₹500`, `25%`) expand into phonetic Hindi words (`paanch sau`, `pachees`) rather than being dropped as non-alphabetic tokens.
  2. Sanskrit conjunct ligatures (`ज्ञ` -> `gy`) transliterate to standard phonetic forms matching speech acoustics.
  3. All 18 benchmark tests passed with high confidence ($\ge 0.85$).

---

## 9. Multi-Speaker Turn Preservation Verification

- Verified via `test_speaker_identity_consistency_across_turns`:
  Multi-speaker dialogue sequences (e.g. Geralt $\rightarrow$ Yennefer $\rightarrow$ Geralt) maintain distinct speaker identities, separate voice configurations, and individual character states without acoustic leakage or speaker profile cross-contamination.

---

## 10. Dialogue Timing & Latency Verification

- Verified via `test_dialogue_turn_ordering_and_timing`:
  `PauseEditor` and `TimingRealizer` accurately realize dramatic turn latencies based on conversational power dynamics and emotional state:
  - **Aposiopesis / Emotional Freeze**: $\ge 1250$ms
  - **Suspense Pause**: $\ge 1100$ms
  - **Thinking / Realization Absorption**: $\ge 900$ms
  - **Normal Reaction Pause**: $\ge 650$ms
  - **Rapid Counter / Eager Retort**: $\le 150$ms (target: 120ms)

---

## 11. Interruption Handling Verification

- Verified via `test_real_audio_pipeline_smoke_test` and `test_golden_7_dialogue_scenarios`:
  - Interrupted dialogue lines ending with em-dashes (`—`) or marked with `interruption_behavior == "abrupt_cut"` are truncated with a 35ms silence pause.
  - Zero-crossing micro-fades are preserved at 2.0ms, avoiding the 15ms room-tone taper that would otherwise soften the sudden cut.

---

## 12. Acoustic Pronunciation QA Verification

- Verified via `test_missing_swallowed_word_detection` and `test_critical_pronunciation_qa_failure_cannot_silently_pass`:
  1. `PronunciationAudioQA` inspects generated WAV files for duration consistency, token omissions, and swallowed syllables. Short or missing audio triggers `PronunciationStatus.FAILED`.
  2. If `PronunciationRepairEngine` cannot synthesize a valid repair, the take is disqualified (`is_selected = False`), and `TTSDispatcher` strictly halts production under fail-closed policies (`TTS_ALLOW_DEGRADED_TAKES=false`).

---

## 13. Conversational Chemistry Integration Verification

- Verified via `test_conversational_chemistry_actively_consumed`:
  1. `IntelligentTakeSelector` consumes `ConversationalChemistry.evaluate_dialogue_chemistry(prev_take, cand)`.
  2. Submissive responses following dominant intimidation are awarded appropriate chemistry bonuses ($\ge 0.70$), while mismatched latencies or jarring energy jumps are penalized.

---

## 14. Provenance Tracking Verification

- Verified via `test_alignment_and_provenance_remain_attached`:
  Winning `TakeVariant` objects preserve character-accurate alignment results, `PerformanceDirection`, and `provenance_mode` (`SOURCE_DIRECT` vs `DRAMATIC_INTERPRETATION`).

---

## 15. Failure Mode Analysis (Before vs. After)

| Failure Mode | Before Hardening | After Hardening |
|---|---|---|
| **Un-repaired Pronunciation QA Failure** | Logged as warning; unselected take continued to master file. | `winning_take.is_selected = False`; production halts immediately with `RuntimeError`. |
| **Numeric & Currency Alignment** | Digits stripped; aligner threw token count mismatch; alignment bypassed. | Numerals phonetically expanded in Hindi (`₹500` $\rightarrow$ `paanch sau`); word alignment succeeds. |
| **Dialogue Chemistry** | Evaluated only in dead code; take selection was turn-blind. | Dynamically computed against `prev_take` during take selection; poor chemistry penalized. |
| **Abrupt Cut Interruption** | Elevated noise floor expanded tail micro-fade to 15ms, softening cutoff. | Abrupt cuts explicitly exempted from noise smoothing; crisp 2.0ms micro-fade preserved. |
| **Devanagari Ligature Alignment** | `ज्ञ` mapped to `jny`, diverging from spoken `gy`. | Pre-mapped to `gy`, aligning seamlessly with speech acoustic models. |

---

## 16. Calibration Corpus Results

The 20-segment `LanguageDialogueCalibrationCorpus` was verified via `test_language_dialogue_calibration_corpus_execution`:

| Segment ID | Domain Category | Literary Text Excerpt | Result |
|---|---|---|---|
| `CAL-01` | Foreign Fantasy Name | *Geralt of Rivia ने अपनी तलवार खींची।* | **PASS** |
| `CAL-02` | Foreign Fantasy Place | *वे Kaer Morhen के पुराने किले में पहुँचे।* | **PASS** |
| `CAL-03` | Classic Detective Name | *Sherlock Holmes ने सिगार का एक कश लिया।* | **PASS** |
| `CAL-04` | Urdu Nukta Contrast | *फैसला और फासला में बहुत फर्क होता है।* | **PASS** |
| `CAL-05` | Urdu Nukta Preservation | *यह केवल एक इत्तेफ़ाक़ था, कोई साज़िश नहीं।* | **PASS** |
| `CAL-06` | Sanskrit Conjunct | *ज्ञान और विज्ञान का संगम ही मुक्ति का मार्ग है।* | **PASS** |
| `CAL-07` | Sanskrit Conjunct | *उनकी दृष्टि अत्यंत तीक्ष्ण और गंभीर थी।* | **PASS** |
| `CAL-08` | Indian Currency | *उसकी जेब में केवल ₹500 का एक नोट था।* | **PASS** |
| `CAL-09` | Large Numeral | *कंपनी का घाटा 25% तक बढ़ चुका था।* | **PASS** |
| `CAL-10` | Exact Calendar Year | *यह घटना 1947 के विभाजन के समय की है।* | **PASS** |
| `CAL-11` | Hinglish Colloquial | *Doctor ने कहा कि patient को तुरंत ICU में शिफ्ट करना होगा।* | **PASS** |
| `CAL-12` | Hinglish Colloquial | *Meeting के बाद manager ने सबको coffee offer की।* | **PASS** |
| `CAL-13` | English Acronym | *FBI और CIA दोनों इस केस की जांच कर रहे हैं।* | **PASS** |
| `CAL-14` | Technical Acronym | *नया CCTV कैमरा 4K resolution में रिकॉर्ड करता है।* | **PASS** |
| `CAL-15` | Multi-Speaker Chemistry | *'तुमने मुझे धोखा दिया!' 'मेरे पास कोई और रास्ता नहीं था...'* | **PASS** |
| `CAL-16` | Power Shift Dynamic | *'बैठ जाओ,' उसने आदेश दिया। वह चुपचाप बैठ गया।* | **PASS** |
| `CAL-17` | Abrupt Interruption | *'लेकिन मैं तुम्हें बताना चाहता था कि—' 'चुप रहो!'* | **PASS** |
| `CAL-18` | Overlapping Dialogue | *'यह सरासर गलत है!' 'गलत या सही, नियम यही है!'* | **PASS** |
| `CAL-19` | Emotional Freeze | *'माँ अब इस दुनिया में नहीं रहीं...' (लम्बी खामोशी)* | **PASS** |
| `CAL-20` | Rapid Counter-Punch | *'तुम हार चुके हो!' 'अभी नहीं!'* | **PASS** |

**Corpus Success Rate**: 20/20 Passed (100%).

---

## 17. Real Audio Smoke Test Results

`test_real_audio_pipeline_smoke_test` executed a real audio test simulating a 3-segment dramatic exchange:
1. **Segment 1**: Geralt speaks Hindi dialogue with fantasy entity: `"Dandelion, हमें Kaer Morhen पहुँचना होगा।"`.
2. **Segment 2**: Dandelion speaks an interrupted cutoff line: `"लेकिन मुझे लगा था कि तुम—"`.
3. **Segment 3**: Geralt retorts with immediate counter: `"खामोश रहो! कोई आ रहा है।"`.

### Results:
- Real 16-bit PCM 24kHz WAV speech files synthesized and loaded.
- `DialogueEditor.process_chapter` generated 3 edited chunks and valid edit plans.
- Segment 2 correctly received `interruption_mode = "abrupt_cut"`, `pause_after_ms = 35`, and `crossfade_out_ms = 2.0`.
- Boundary noise smoothing did not degrade the abrupt cut.
- `DialogueQCReport.passed == True`.

---

## 18. Summary of Changes and Future Readiness

Prompt 4 hardened the repository's pronunciation, language fidelity, forced alignment, and dialogue editing subsystems without introducing redundant V2 architectures. All existing components (`PronunciationResolver`, `SpokenTextEngine`, `PronunciationAudioQA`, `ConversationalChemistry`, `IntelligentTakeSelector`, `WorkstationForcedAligner`, and `DialogueEditor`) are now tightly coupled through immutable contracts and fail-closed gates.

The system is now fully verified and prepared for downstream **Prompt 5: Sound Design, Ambience Beds, and Multitrack Cinematic Mixing**.
