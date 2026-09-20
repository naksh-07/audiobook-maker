#!/usr/bin/env python3
"""
Unit tests for Linguistic Sanitizer and Translation Guardrail Engine.
"""

from audiobook_factory.sanitizer import (
    validate_and_sanitize_translation,
    sanitize_screenplay_segment,
    count_devanagari_chars,
    count_latin_words,
    strip_markdown_fences,
)


def test_refusal_patterns_rejected():
    refusals = [
        "I cannot provide a direct translation of this excerpt from the novel, but I can offer a broad summary...",
        "As an AI language model, I cannot translate violent content.",
        "Here is the translation of the passage:\n\nयह कहानी है।",
        "### Scene Overview\nIn this scene Geralt fights.",
        "Would you like a summary of the next chapter or segment of the story?",
        "Option 1: Literary Hindi\nयह अनुवाद है।",
    ]
    for text in refusals:
        is_valid, cleaned, reason = validate_and_sanitize_translation(text, is_hindi=True)
        assert not is_valid, f"Expected rejection for: {text[:50]}, but passed with reason: {reason}"


def test_devanagari_purity_accepted():
    valid_hindi = (
        "रिविया के उस विचर ने फिर भी कुछ नहीं कहा। ओस्ट्रिट ने अपनी आवाज़ ऊँची की। "
        "\"और मेरा वक़्त ज़ाया मत करो। मेरी आधी रात तक यहाँ खड़े रहने की कोई मंशा नहीं है। "
        "क्या तुम्हें समझ नहीं आ रहा?\""
    )
    is_valid, cleaned, reason = validate_and_sanitize_translation(valid_hindi, is_hindi=True)
    assert is_valid, f"Expected valid Hindi, but rejected: {reason}"
    assert "विचर" in cleaned


def test_markdown_fence_stripping():
    fenced = "```markdown\nयह एक सुंदर अनुवाद है।\n```"
    is_valid, cleaned, reason = validate_and_sanitize_translation(fenced, is_hindi=True)
    assert is_valid
    assert not cleaned.startswith("```")
    assert not cleaned.endswith("```")
    assert "यह एक सुंदर अनुवाद है।" in cleaned


def test_screenplay_segment_sanitizer():
    # Valid Hindi segment
    seg_valid = {
        "index": 1,
        "type": "narration",
        "speaker": "Narrator",
        "text": "गेराल्ट ने अपनी तलवार खींची और आगे बढ़ा।",
        "emotion": "neutral",
        "pause_after_ms": 600,
    }
    res = sanitize_screenplay_segment(seg_valid, is_hindi=True)
    assert res is not None
    assert res["text"] == "गेराल्ट ने अपनी तलवार खींची और आगे बढ़ा।"

    # Leaked English refusal segment
    seg_refusal = {
        "index": 2,
        "type": "narration",
        "speaker": "Narrator",
        "text": "I cannot provide a direct translation of this excerpt.",
        "emotion": "neutral",
        "pause_after_ms": 600,
    }
    assert sanitize_screenplay_segment(seg_refusal, is_hindi=True) is None

    # Leaked English conversation segment
    seg_english = {
        "index": 3,
        "type": "narration",
        "speaker": "Narrator",
        "text": "Would you like a summary of the next chapter or segment of the story?",
        "emotion": "neutral",
        "pause_after_ms": 600,
    }
    assert sanitize_screenplay_segment(seg_english, is_hindi=True) is None

    # Markdown header in text
    seg_md = {
        "index": 4,
        "type": "narration",
        "speaker": "Narrator",
        "text": "### **गेराल्ट चुपचाप खड़ा रहा।**",
        "emotion": "neutral",
        "pause_after_ms": 600,
    }
    res_md = sanitize_screenplay_segment(seg_md, is_hindi=True)
    assert res_md is not None
    assert res_md["text"] == "गेराल्ट चुपचाप खड़ा रहा।"
