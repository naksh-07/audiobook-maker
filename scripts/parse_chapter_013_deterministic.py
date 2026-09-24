#!/usr/bin/env python3
"""
Audiobook Factory - Chapter 13 Deterministic Screenplay Builder.
Parses Chapter 13 ('The Voice of Reason 7' / 'तर्क की आवाज़ 7') into a high-precision,
broadcast-ready Screenplay JSON in milliseconds with zero LLM timeouts or JSON truncation.
Adheres strictly to Gate 2 schema and canonical speaker roster.
"""

import os
import sys
import re
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from audiobook_factory.gate_auditor import audit_gate2_script

# Ensure UTF-8 I/O for Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def clean_dialogue_tags(text: str) -> str:
    """Strip inlined Hindi speech attribution tags from dialogue."""
    cleaned = text.strip()
    # Remove leading/trailing quote characters
    cleaned = re.sub(r'^[“"\'‘]+|[”"\'’]+$', '', cleaned).strip()
    return cleaned


def parse_paragraph_to_segments(para: str, prev_speaker: str, scene_num: int) -> Tuple[List[Dict[str, Any]], str]:
    """
    Parse a single paragraph into discrete narration and dialogue segments.
    """
    segments = []
    p = para.strip()
    if not p:
        return segments, prev_speaker

    env = "forest_glade" if scene_num == 1 else "temple_courtyard"

    # Pattern to match quotes: "..." or “...”
    # Also handles split dialogue: "quote 1" tag "quote 2"
    quote_matches = list(re.finditer(r'([“"\'‘])(.*?)([”"\'’])', p, flags=re.DOTALL))

    if not quote_matches:
        # Pure narration paragraph
        # Check if it has action beats
        emotion = "neutral"
        intensity = "low"
        delivery = "calm_authoritative"
        sfx = []

        if "खून" in p and "हड्डियाँ" in p:
            emotion = "sad"
            intensity = "explosive"
            delivery = "whispering_fear"
            sfx = ["body_fall_thud"]
        elif "बिजली की सी गति" in p or "तलवार" in p and "टकराई" in p:
            intensity = "high"
            delivery = "combat_strain"
            sfx = ["sword_parry_clash", "body_fall_thud"]

        seg = {
            "type": "narration",
            "speaker": "Narrator",
            "text": p,
            "emotion": emotion,
            "intensity_level": intensity,
            "pre_roll_breath_ms": 0,
            "pause_after_ms": 400,
            "acting": {
                "delivery_style": delivery,
                "pacing": 1.0
            },
            "spatial": {
                "pan": 0.0,
                "proximity": "intimate_close"
            },
            "acoustic_env": env,
            "sfx_cues": sfx
        }
        return [seg], prev_speaker

    # If paragraph contains dialogue quotes
    # Extract surrounding tags and quote texts
    last_idx = 0
    dialogue_pieces = []
    tag_pieces = []

    for m in quote_matches:
        pre_text = p[last_idx:m.start()].strip()
        quote_text = m.group(2).strip()
        last_idx = m.end()

        if pre_text:
            tag_pieces.append(pre_text)
        dialogue_pieces.append(quote_text)

    post_text = p[last_idx:].strip()
    if post_text:
        tag_pieces.append(post_text)

    combined_tags = " ".join(tag_pieces)
    combined_dialogue = " ".join(dialogue_pieces)

    # Determine speaker from tags or dialogue cues
    speaker = "Narrator"
    tag_lower = combined_tags.lower()

    if any(k in tag_lower for k in ["गेराल्ट", "विचर", "रिविया"]):
        speaker = "Geralt"
    elif any(k in tag_lower for k in ["डैंडेलियन", "कवि", "भाट"]):
        speaker = "Dandelion"
    elif any(k in tag_lower for k in ["फ़ाल्विक", "काउंट"]):
        speaker = "Falwick"
    elif any(k in tag_lower for k in ["डेनिस", "क्रैनमर", "बौने", "बौना", "कप्तान"]):
        speaker = "Dennis_Cranmer"
    elif any(k in tag_lower for k in ["तैलिस", "टेल्स", "नौजवान नाइट"]):
        speaker = "Tailles"
    elif any(k in tag_lower for k in ["नेनेके", "पुजारिन"]):
        speaker = "Nenneke"
    elif any(k in tag_lower for k in ["इओला"]):
        speaker = "Iola"
    else:
        # Contextual dialogue attribution by rally or content
        if "मुँह बंद रखो" in combined_dialogue or "चलो, इसे निपटाते हैं" in combined_dialogue or "मैं तैयार हूँ" in combined_dialogue or "भारी है" in combined_dialogue or "सूअर की तरह हलाल" in combined_dialogue or "मुझे जाना ही होगा" in combined_dialogue:
            speaker = "Geralt"
        elif "लड़ना ही होगा?" in combined_dialogue or "अफ़सोस" in combined_dialogue or "कुछ मत कहो" in combined_dialogue or "नहीं भूलूँगा" in combined_dialogue:
            speaker = "Geralt"
        elif "यह क्या बखेड़ा है?" in combined_dialogue or "क्या गज़ब का तर्क है!" in combined_dialogue or "आपका यह तर्क वाकई लाजवाब है" in combined_dialogue or "दिल की गहराइयों में आप मुझे पसंद करती हैं" in combined_dialogue:
            speaker = "Dandelion"
        elif "हाँ, हर हाल में।" in combined_dialogue or "सत्यानाश" in combined_dialogue and prev_speaker == "Dandelion":
            speaker = "Falwick"
        elif "तो तुम तैयार हो" in combined_dialogue or "बेहतरीन" in combined_dialogue or "मेरी तलवार लो" in combined_dialogue or "पकड़ लो इसे!" in combined_dialogue or "दफ़ा हो जाओ" in combined_dialogue:
            speaker = "Falwick"
        elif "दोनों के पास बराबर का मौका है" in combined_dialogue:
            speaker = "Falwick"
        elif "इजाज़त दीजिए" in combined_dialogue or "बिल्कुल सही" in combined_dialogue or "झूठी कसमें मत खाइए" in combined_dialogue or "तुम्हारा सफ़र अच्छा रहे" in combined_dialogue:
            speaker = "Dennis_Cranmer"
        elif "माफ़ी माँगने के बारे में क्या ख़्याल है?" in combined_dialogue:
            speaker = "Geralt"
        elif "अलविदा" in combined_dialogue and prev_speaker == "Geralt":
            speaker = "Nenneke"
        elif "इओला! बोलो!" in combined_dialogue or "ले जाओ इसे" in combined_dialogue or "मत जाओ" in combined_dialogue:
            speaker = "Nenneke"
        elif "हाँ, हर हाल में।" in combined_dialogue or "हर हाल में" in combined_dialogue:
            speaker = "Falwick"
        else:
            # Fallback to smart toggle between Geralt and current scene counter-speaker
            if scene_num == 1:
                speaker = "Falwick" if prev_speaker == "Geralt" else "Geralt"
            else:
                speaker = "Nenneke" if prev_speaker == "Geralt" else "Geralt"

    # Set spatial staging
    spatial_map = {
        "Narrator": {"pan": 0.0, "proximity": "intimate_close"},
        "Geralt": {"pan": -0.20, "proximity": "normal_room"},
        "Dandelion": {"pan": -0.35, "proximity": "normal_room"},
        "Falwick": {"pan": 0.30, "proximity": "normal_room"},
        "Dennis_Cranmer": {"pan": 0.10, "proximity": "normal_room"},
        "Tailles": {"pan": 0.40, "proximity": "normal_room"},
        "Nenneke": {"pan": 0.25, "proximity": "normal_room"},
        "Iola": {"pan": 0.15, "proximity": "intimate_close"},
    }

    # Set acting delivery & emotion
    emotion = "neutral"
    intensity = "medium"
    delivery = "neutral"

    if speaker == "Geralt":
        delivery = "calm_authoritative"
        if "सत्यानाश" in combined_dialogue or "सूअर की तरह हलाल" in combined_dialogue:
            emotion = "growl"
            delivery = "cold_menace"
            intensity = "high"
    elif speaker == "Dandelion":
        delivery = "ironic_mockery"
        emotion = "excited"
    elif speaker == "Falwick":
        delivery = "bellowing_rage" if "पकड़ लो" in combined_dialogue or "कसम खाता हूँ" in combined_dialogue else "cold_menace"
        emotion = "angry" if "दहाड़ा" in combined_tags else "neutral"
    elif speaker == "Dennis_Cranmer":
        delivery = "calm_authoritative"
        emotion = "calm_raspy"
    elif speaker == "Nenneke":
        delivery = "bellowing_rage" if "इओला!" in combined_dialogue else "calm_authoritative"
        emotion = "angry" if "चिल्लाई" in combined_tags else "neutral"

    # Prepend vocal tags if appropriate
    clean_speech = combined_dialogue.strip()
    if speaker == "Geralt" and "सत्यानाश" in clean_speech:
        clean_speech = f"[whispers] {clean_speech}"
    elif speaker == "Falwick" and "पकड़ लो इसे!" in clean_speech:
        clean_speech = f"[shouting] {clean_speech}"
    elif speaker == "Nenneke" and "इओला! बोलो!" in clean_speech:
        clean_speech = f"[shouting] {clean_speech}"

    seg = {
        "type": "dialogue",
        "speaker": speaker,
        "text": clean_speech,
        "emotion": emotion,
        "intensity_level": intensity,
        "pre_roll_breath_ms": 150 if intensity == "high" else 0,
        "pause_after_ms": 400,
        "acting": {
            "delivery_style": delivery,
            "pacing": 1.0
        },
        "spatial": spatial_map.get(speaker, {"pan": 0.0, "proximity": "normal_room"}),
        "acoustic_env": env,
        "sfx_cues": []
    }

    # If there was a significant narrative action lead-in in the same paragraph
    # (e.g. "वे घोड़ों से नीचे उतरे। फ़ाल्विक और वह बौना धीरे-धीरे उनकी तरफ बढ़े। 'विचर, तुमने...'")
    if tag_pieces:
        # Check if pre-tag has significant prose (> 5 words)
        first_tag = tag_pieces[0].strip()
        if len(first_tag.split()) >= 6 and not any(first_tag.endswith(w) for w in ["कहा", "बोला", "चिल्लाया", "बुदबुदाया"]):
            narration_seg = {
                "type": "narration",
                "speaker": "Narrator",
                "text": first_tag,
                "emotion": "neutral",
                "intensity_level": "low",
                "pre_roll_breath_ms": 0,
                "pause_after_ms": 300,
                "acting": {
                    "delivery_style": "calm_authoritative",
                    "pacing": 1.0
                },
                "spatial": {"pan": 0.0, "proximity": "intimate_close"},
                "acoustic_env": env,
                "sfx_cues": []
            }
            return [narration_seg, seg], speaker

    return [seg], speaker


def main():
    project_dir = ROOT_DIR / "audiobooks" / "projects" / "witcher1"
    translation_file = project_dir / "translation" / "chapter_013_hi.md"
    output_script_file = project_dir / "scripts" / "chapter_013_hi_script.json"

    if not translation_file.exists():
        raise FileNotFoundError(f"Translation file not found: {translation_file}")

    with open(translation_file, "r", encoding="utf-8") as f:
        text = f.read()

    raw_paras = [p.strip() for p in text.split("\n\n") if p.strip()]

    scene_num = 1
    all_segments = []
    prev_speaker = "Narrator"
    idx = 1

    for p in raw_paras:
        if p.startswith("# तर्क की आवाज़ 7") or p == "## I":
            continue
        if p == "## II":
            scene_num = 2
            continue

        segs, prev_speaker = parse_paragraph_to_segments(p, prev_speaker, scene_num)
        for s in segs:
            s["index"] = idx
            idx += 1
            all_segments.append(s)

    print(f"[*] Parsed {len(all_segments)} screenplay segments deterministically.")

    # Speaker distribution
    dist: Dict[str, int] = {}
    for s in all_segments:
        spk = s["speaker"]
        dist[spk] = dist.get(spk, 0) + 1

    print("[*] Speaker Distribution:")
    for spk, count in sorted(dist.items(), key=lambda x: -x[1]):
        print(f"    - {spk}: {count} segments")

    script_data = {
        "metadata": {
            "project_id": "witcher1",
            "chapter_id": "chapter_013",
            "title": "तर्क की आवाज़ 7",
            "total_segments": len(all_segments),
            "language": "hi",
            "parser_version": "3.8_sota_deterministic"
        },
        "segments": all_segments
    }

    with open(output_script_file, "w", encoding="utf-8") as out_f:
        json.dump(script_data, out_f, ensure_ascii=False, indent=2)

    print(f"[+] Screenplay saved to: {output_script_file.name}")

    # Audit Gate 2
    print("\n[*] Auditing Gate 2 (Screenplay Schema & Canonical Speakers)...")
    audit_res = audit_gate2_script(output_script_file, project_dir=project_dir)
    print(f"[OK] Gate 2 Audit Passed: {audit_res}")


if __name__ == "__main__":
    main()
