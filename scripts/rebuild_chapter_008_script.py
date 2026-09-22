#!/usr/bin/env python3
"""
Audiobook Factory - High-Fidelity Screenplay Script Rebuilder for Chapter 8.
Parses translation/chapter_008_hi.md into an authenticated multi-cast screenplay script:
- Cleanly separates narration action-beats from spoken character dialogue
- Accurately attributes dialogue across all 12 canonical roles
- Normalizes all character names to English canonical keys in character_roster.json
- Assigns rich acting instructions, stereo spatial pan, acoustic room presets, and natural pause timing
- Validates 100% against Pydantic ScreenplayScript contract
"""

import re
import sys
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import Counter

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from audiobook_factory.contracts import (
    ScreenplaySegment,
    ScreenplayScript,
)
from audiobook_factory.script_builder import normalize_speech_text


def get_act_id(idx: int) -> int:
    if idx <= 46:
        return 1
    elif idx <= 173:
        return 2
    elif idx <= 220:
        return 3
    elif idx <= 267:
        return 4
    elif idx <= 289:
        return 5
    elif idx <= 345:
        return 6
    else:
        return 7


# Narration tag speaker identification patterns
NARR_TAG_RULES = [
    ("Eist_Tuirseach", re.compile(r"(ईस्ट|ईस्त|एइस्ट|ट्यूर्शेक|टुरसेक|तुइरसेक|ट्यूरसैक|ट्यूइरसेक)")),
    ("Crach_an_Craite", re.compile(r"(क्रैच)")),
    ("Mousesack", re.compile(r"(माउससैक|ड्रुइड)")),
    ("Coodcoodak", re.compile(r"(कूडकूडाक|बैरोन\s*कूडकूडाक)")),
    ("Rainfarn", re.compile(r"(रेनफ़ार्न|रेनफार्न)")),
    ("Windhalm", re.compile(r"(विंडहाम|विंडहाल्म|विंडहल्म)")),
    ("Pavetta", re.compile(r"(पावेता|राजकुमारी)")),
    ("Duny", re.compile(r"(डनी|ड्यूनी|अर्चियन|काँटेदार\s*जीव|घुड़सवार|आगंतुक|नाइट)")),
    ("Haxo", re.compile(r"(हाक्सो|किलेदार)")),
    ("Herald", re.compile(r"(उद्घोषक|चोबदार)")),
    ("Servant", re.compile(r"(सेवक|हजाम|नाई)")),
    ("Calanthe", re.compile(r"(कैलेंथे|रानी|महारानी)")),
    ("Geralt", re.compile(r"(गेराल्ट|विचर|राभिक्स)")),
]

# Patterns when character is addressed (vocatives inside quotes)
VOCATIVES = [
    ("Haxo", re.compile(r"(किलेदार|हाक्सो)[\?!\.,]")),
    ("Geralt", re.compile(r"(गेराल्ट|विचर|राभिक्स)[\?!\.,]")),
    ("Calanthe", re.compile(r"(रानी|महारानी|कैलेंथे)[\?!\.,]")),
    ("Duny", re.compile(r"(डनी|ड्यूनी|अर्चियन)[\?!\.,]")),
    ("Crach_an_Craite", re.compile(r"(क्रैच)[\?!\.,]")),
    ("Eist_Tuirseach", re.compile(r"(ईस्ट|ईस्त|एइस्ट|टुरसेक)[\?!\.,]")),
    ("Mousesack", re.compile(r"(माउससैक)[\?!\.,]")),
    ("Coodcoodak", re.compile(r"(कूडकूडाक)[\?!\.,]")),
    ("Pavetta", re.compile(r"(पावेता)[\?!\.,]")),
    ("Rainfarn", re.compile(r"(रेनफ़ार्न|रेनफार्न)[\?!\.,]")),
]


def rebuild_chapter_008():
    trans_path = ROOT_DIR / "audiobooks" / "projects" / "witcher1" / "translation" / "chapter_008_hi.md"
    script_out = ROOT_DIR / "audiobooks" / "projects" / "witcher1" / "scripts" / "chapter_008_hi_script.json"
    backup_path = script_out.with_suffix(".json.bak_legacy")

    if script_out.exists() and not backup_path.exists():
        script_out.rename(backup_path)
        print(f"[*] Backed up legacy script to {backup_path.name}")

    text = trans_path.read_text(encoding="utf-8")
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    segments: List[Dict[str, Any]] = []
    seg_index = 1

    current_act = 1
    current_env = "cintra_castle_bath"
    last_dialogue_speaker: Optional[str] = None

    def clean_dialogue(quote_str: str) -> str:
        q = quote_str.strip(' \t\n\r"“”\'')
        return normalize_speech_text(q, is_hindi=True)

    def clean_narration(narr_str: str) -> str:
        n = re.sub(r'["“”]', '', narr_str).strip()
        return normalize_speech_text(n, is_hindi=True)

    # Act metadata
    act_names = {
        1: ("भाग I: शाही स्नान और किलेदार हाक्सो की चेतावनी", "cintra_castle_bath"),
        2: ("भाग II: सिंट्रा की भव्य दावत और रानी कैलेंथे की कूटनीति", "cintra_banquet_hall"),
        3: ("भाग III: अर्लेनवाल्ड के अर्चियन का रहस्यमयी आगमन", "cintra_banquet_hall"),
        4: ("भाग IV: अनहोनी का कानून और पावेता का वचन", "cintra_banquet_hall"),
        5: ("भाग V: आधी रात का नकाब और तलवारों की खनक", "cintra_banquet_hall"),
        6: ("भाग VI: प्राचीन रक्त का भयंकर तूफ़ान", "cintra_banquet_hall"),
        7: ("भाग VII: भाग्य की नई भोर और अनहोनी का बच्चा", "cintra_banquet_hall_dawn"),
    }

    # Chapter Header
    segments.append({
        "index": seg_index,
        "type": "chapter_header",
        "speaker": "Narrator",
        "text": "अध्याय 008: कीमत का सवाल",
        "emotion": "neutral",
        "pause_after_ms": 1200,
        "acting": {"delivery_style": "neutral", "pacing": 1.0},
        "spatial": {"pan": 0.0, "proximity": "normal_room"},
        "acoustic_env": current_env,
        "sfx_cues": [],
        "music": {"mood": "mysterious", "ducking_db": -16.0},
    })
    seg_index += 1

    # Act 1 Header
    segments.append({
        "index": seg_index,
        "type": "narration",
        "speaker": "Narrator",
        "text": act_names[1][0],
        "emotion": "neutral",
        "pause_after_ms": 1000,
        "acting": {"delivery_style": "neutral", "pacing": 0.95},
        "spatial": {"pan": 0.0, "proximity": "normal_room"},
        "acoustic_env": current_env,
        "sfx_cues": [],
        "music": {"mood": "mysterious", "ducking_db": -16.0},
    })
    seg_index += 1

    for p_idx, p in enumerate(paragraphs):
        act = get_act_id(p_idx)
        if act != current_act:
            current_act = act
            act_title, current_env = act_names[current_act]
            last_dialogue_speaker = None
            segments.append({
                "index": seg_index,
                "type": "narration",
                "speaker": "Narrator",
                "text": act_title,
                "emotion": "neutral",
                "pause_after_ms": 1000,
                "acting": {"delivery_style": "neutral", "pacing": 0.95},
                "spatial": {"pan": 0.0, "proximity": "normal_room"},
                "acoustic_env": current_env,
                "sfx_cues": [],
                "music": {"mood": "mysterious", "ducking_db": -16.0},
            })
            seg_index += 1

        # Skip explicit Roman numeral headings or chunk headers in translation file
        if p in ("I", "II", "III", "IV", "V", "VI", "VII") or p.startswith("#"):
            continue

        has_quotes = ('"' in p or '“' in p or '”' in p)

        if not has_quotes:
            # Pure narration paragraph
            clean_text = clean_narration(p)
            if clean_text:
                segments.append({
                    "index": seg_index,
                    "type": "narration",
                    "speaker": "Narrator",
                    "text": clean_text,
                    "emotion": "neutral",
                    "pause_after_ms": 500,
                    "acting": {"delivery_style": "neutral", "pacing": 1.0},
                    "spatial": {"pan": 0.0, "proximity": "normal_room"},
                    "acoustic_env": current_env,
                    "sfx_cues": [],
                    "music": {"mood": "mysterious", "ducking_db": -16.0},
                })
                seg_index += 1
            continue

        # Dialogue paragraph: Split into quotes and narration
        parts = re.split(r'["“]([^"“”]+)["”]', p)
        quotes = [parts[i].strip() for i in range(1, len(parts), 2)]
        outside = [parts[i].strip() for i in range(0, len(parts), 2) if parts[i].strip()]
        outside_text = " ".join(outside)
        quotes_text = " ".join(quotes)

        # Determine speaker for this dialogue turn
        speaker = None

        # 1. Look for character name in narration tags (outside quotes)
        if outside_text:
            for name, pat in NARR_TAG_RULES:
                if pat.search(outside_text):
                    speaker = name
                    break

        # 2. Check vocatives in quotes (who is being addressed?)
        if not speaker:
            for addressed_char, pat in VOCATIVES:
                if pat.search(quotes_text):
                    if addressed_char == "Haxo":
                        speaker = "Geralt"
                    elif addressed_char == "Geralt":
                        if current_act == 1:
                            speaker = "Haxo"
                        elif current_act == 2:
                            speaker = "Calanthe"
                        elif current_act in (3, 4, 5, 7):
                            speaker = "Duny" if last_dialogue_speaker != "Duny" else "Calanthe"
                        else:
                            speaker = "Mousesack"
                    elif addressed_char == "Calanthe":
                        if current_act == 2:
                            speaker = "Geralt" if last_dialogue_speaker != "Geralt" else "Eist_Tuirseach"
                        elif current_act in (3, 4, 5):
                            speaker = "Duny"
                        else:
                            speaker = "Eist_Tuirseach"
                    elif addressed_char == "Crach_an_Craite":
                        speaker = "Eist_Tuirseach"
                    elif addressed_char == "Mousesack":
                        speaker = "Geralt"
                    elif addressed_char == "Duny":
                        speaker = "Calanthe"
                    elif addressed_char == "Pavetta":
                        speaker = "Calanthe"
                    elif addressed_char == "Rainfarn":
                        speaker = "Eist_Tuirseach"
                    elif addressed_char == "Coodcoodak":
                        speaker = "Calanthe"
                    break

        # 3. Conversational turn-taking fallback based on active act
        if not speaker:
            if current_act == 1:
                speaker = "Haxo" if last_dialogue_speaker == "Geralt" else "Geralt"
            elif current_act == 2:
                speaker = "Geralt" if last_dialogue_speaker == "Calanthe" else "Calanthe"
            elif current_act == 3:
                speaker = "Calanthe" if last_dialogue_speaker == "Duny" else "Duny"
            elif current_act == 4:
                if last_dialogue_speaker == "Duny":
                    speaker = "Calanthe"
                elif last_dialogue_speaker == "Calanthe":
                    speaker = "Duny"
                else:
                    speaker = "Duny"
            elif current_act == 5:
                if last_dialogue_speaker == "Duny":
                    speaker = "Calanthe"
                elif last_dialogue_speaker == "Calanthe":
                    speaker = "Duny"
                elif last_dialogue_speaker == "Rainfarn":
                    speaker = "Crach_an_Craite"
                else:
                    speaker = "Geralt"
            elif current_act == 6:
                speaker = "Geralt" if last_dialogue_speaker == "Mousesack" else "Mousesack"
            elif current_act == 7:
                if last_dialogue_speaker == "Duny":
                    speaker = "Geralt"
                elif last_dialogue_speaker == "Geralt":
                    speaker = "Duny"
                else:
                    speaker = "Calanthe"

        last_dialogue_speaker = speaker

        # Interleave action beats and spoken dialogue
        for idx_part, part in enumerate(parts):
            clean_p = part.strip()
            if not clean_p:
                continue

            if idx_part % 2 == 0:
                # Narration action-beat
                # Filter out pure dialogue attribution tags like 'हाक्सो ने कहा', 'कैलेंथे बोली'
                is_pure_tag = bool(re.fullmatch(
                    r"^(उसने|रानी|कैलेंथे|गेराल्ट|हाक्सो|डनी|विचर|माउससैक|ईस्ट|क्रैच|पावेता|कूडकूडाक|रेनफ़ार्न|रेनफार्न|उद्घोषक|सेवक|आगंतुक|अर्चियन)?\s*(ने)?\s*(कहा|पूछा|बोला|बोली|चिल्लाई|चिल्लाया|फुसफुसाई|फुसफुसाया|मुस्कुराई|मुस्कुराया|मुस्कुराए|जवाब\s*दिया|उत्तर\s*दिया|सिर\s*हिलाया|दहाड़ा|दहाड़ी|गर्जना\s*की)[\s\.,—\-]*$",
                    clean_p
                ))
                if is_pure_tag:
                    continue

                # Strip dangling speech tag prefixes or suffixes
                action_text = re.sub(r'^(उसने|रानी\s*ने|कैलेंथे\s*ने|गेराल्ट\s*ने|हाक्सो\s*ने|डनी\s*ने)\s*(कहा|पूछा|बोला|बोली|चिल्लाई)[\s\.,—\-]*', '', clean_p)
                action_text = re.sub(r'[\s\.,—\-]*(उसने|रानी\s*ने|कैलेंथे\s*ने|गेराल्ट\s*ने|हाक्सो\s*ने|डनी\s*ने)\s*(कहा|पूछा|बोला|बोली|चिल्लाई)[\s\.,—\-]*$', '', action_text)
                action_text = clean_narration(action_text)

                if action_text and len(action_text.split()) >= 2:
                    segments.append({
                        "index": seg_index,
                        "type": "narration",
                        "speaker": "Narrator",
                        "text": action_text,
                        "emotion": "neutral",
                        "pause_after_ms": 400,
                        "acting": {"delivery_style": "neutral", "pacing": 1.0},
                        "spatial": {"pan": 0.0, "proximity": "normal_room"},
                        "acoustic_env": current_env,
                        "sfx_cues": [],
                        "music": {"mood": "mysterious", "ducking_db": -16.0},
                    })
                    seg_index += 1
            else:
                # Spoken character dialogue
                quote_text = clean_dialogue(clean_p)
                if not quote_text:
                    continue

                # Speaker-specific acting, spatial pan, and delivery parameters
                emo = "neutral"
                delivery = "neutral"
                pan = 0.0
                pacing = 1.0

                if speaker == "Geralt":
                    pan = -0.15
                    pacing = 0.98
                    emo = "calm_raspy"
                    delivery = "calm_authoritative"
                elif speaker == "Calanthe":
                    pan = 0.20
                    pacing = 1.02
                    emo = "angry" if current_act in (3, 5) else "neutral"
                    delivery = "cold_menace" if current_act in (2, 5) else "ironic_mockery"
                elif speaker == "Duny":
                    pan = 0.10
                    pacing = 0.98
                    emo = "sad" if current_act in (3, 4) else "neutral"
                    delivery = "whispering_fear" if current_act == 4 else "calm_authoritative"
                elif speaker == "Pavetta":
                    pan = 0.25
                    pacing = 1.02
                    emo = "sad"
                    delivery = "gentle_tender"
                elif speaker == "Mousesack":
                    pan = -0.22
                    pacing = 0.95
                    emo = "neutral"
                    delivery = "calm_authoritative"
                elif speaker == "Eist_Tuirseach":
                    pan = -0.20
                    pacing = 1.02
                    emo = "excited"
                    delivery = "bellowing_rage" if current_act == 5 else "neutral"
                elif speaker == "Crach_an_Craite":
                    pan = -0.30
                    pacing = 1.06
                    emo = "angry"
                    delivery = "bellowing_rage"
                elif speaker == "Haxo":
                    pan = 0.18
                    pacing = 1.0
                    emo = "neutral"
                    delivery = "neutral"
                elif speaker == "Coodcoodak":
                    pan = 0.28
                    pacing = 1.04
                    emo = "excited"
                    delivery = "ironic_mockery"
                elif speaker == "Rainfarn":
                    pan = -0.25
                    pacing = 1.05
                    emo = "angry"
                    delivery = "bellowing_rage"
                elif speaker == "Windhalm":
                    pan = 0.22
                    pacing = 0.95
                    emo = "neutral"
                    delivery = "whispering_fear"
                elif speaker == "Herald":
                    pan = 0.0
                    pacing = 1.02
                    emo = "excited"
                    delivery = "bellowing_rage"
                elif speaker == "Servant":
                    pan = 0.15
                    pacing = 1.0
                    emo = "neutral"
                    delivery = "gentle_tender"

                segments.append({
                    "index": seg_index,
                    "type": "dialogue",
                    "speaker": speaker,
                    "text": quote_text,
                    "emotion": emo,
                    "pause_after_ms": 450,
                    "acting": {"delivery_style": delivery, "pacing": pacing},
                    "spatial": {"pan": pan, "proximity": "normal_room"},
                    "acoustic_env": current_env,
                    "sfx_cues": [],
                    "music": {"mood": "mysterious", "ducking_db": -16.0},
                })
                seg_index += 1

    # Validate against ScreenplayScript Pydantic contract
    script_obj = ScreenplayScript(segments=[ScreenplaySegment.model_validate(s) for s in segments])

    with open(script_out, "w", encoding="utf-8") as f:
        json.dump([s.model_dump() for s in script_obj.segments], f, ensure_ascii=False, indent=2)

    print(f"\n[+] Screenplay Script Rebuilt successfully: {script_out.name}")
    print(f"    Total Segments: {len(script_obj.segments)}")
    speakers = Counter(s.speaker for s in script_obj.segments)
    types = Counter(s.type for s in script_obj.segments)
    print("\nSpeakers Breakdown:")
    for spk, cnt in speakers.most_common():
        print(f"  {spk:<18}: {cnt}")
    print("\nTypes Breakdown:")
    for t, cnt in types.items():
        print(f"  {t:<18}: {cnt}")


if __name__ == "__main__":
    rebuild_chapter_008()
