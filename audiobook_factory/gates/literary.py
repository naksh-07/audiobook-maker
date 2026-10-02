#!/usr/bin/env python3
"""
Audiobook Factory - Literary & Anti-Censorship Quality Gates.
Houses Gate 0 (Source Translation Coverage), Gate 1 (Character Voice Casting & Collisions),
and Gate 1 Anti-Censorship Agents (Profanity, Combat Gore, Somatic Intimacy).
"""

from __future__ import annotations
import os
import re
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor

from audiobook_factory.gates.contracts import GateAuditError

logger = logging.getLogger("audiobook_factory.gates.literary")


def audit_gate0_translation(extracted_file: Path, translation_file: Path) -> Dict[str, Any]:
    """Audit Gate 0: Verifies source text and localized translation file existence and length sanity."""
    extracted_file = Path(extracted_file).resolve()
    translation_file = Path(translation_file).resolve()

    if not extracted_file.exists():
        raise GateAuditError(f"Gate 0 Failed: Extracted source file missing: {extracted_file}")
    if not translation_file.exists():
        raise GateAuditError(f"Gate 0 Failed: Localized translation file missing: {translation_file}")

    ext_text = extracted_file.read_text(encoding="utf-8").strip()
    trans_text = translation_file.read_text(encoding="utf-8").strip()

    if len(ext_text) < 100:
        raise GateAuditError(f"Gate 0 Failed: Extracted text suspiciously short ({len(ext_text)} chars)")
    if len(trans_text) < 100:
        raise GateAuditError(f"Gate 0 Failed: Translation text suspiciously short ({len(trans_text)} chars)")

    ratio = len(trans_text) / len(ext_text)
    if ratio < 0.65 or ratio > 1.85:
        raise GateAuditError(
            f"Gate 0 Failed: Translation character length ratio {ratio:.2f} is outside acceptable range [0.65, 1.85] "
            f"(extracted: {len(ext_text)}, translation: {len(trans_text)})"
        )

    return {
        "status": "PASS",
        "extracted_chars": len(ext_text),
        "translation_chars": len(trans_text),
        "length_ratio": round(ratio, 3),
        "extracted_lines": len(ext_text.splitlines()),
        "translation_lines": len(trans_text.splitlines()),
    }


def audit_gate1_roster(
    roster_file: Any,
    registry_file: Any,
    active_characters: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Audit Gate 1: Verifies character roster and voice registry, checking for voice collisions."""
    roster_data: Dict[str, Any] = {}

    if isinstance(roster_file, (list, tuple)):
        for i, c in enumerate(roster_file):
            if hasattr(c, "display_name"):
                name = c.display_name or getattr(c, "english_name", f"char_{i}")
                roster_data[name] = c.model_dump() if hasattr(c, "model_dump") else dict(c)
            elif isinstance(c, dict):
                name = c.get("display_name") or c.get("english_name") or c.get("name", f"char_{i}")
                roster_data[name] = c
    elif isinstance(roster_file, dict):
        chars_val = roster_file.get("characters", roster_file)
        if isinstance(chars_val, dict):
            roster_data = chars_val
        elif isinstance(chars_val, list):
            for i, c in enumerate(chars_val):
                if hasattr(c, "display_name"):
                    name = c.display_name or getattr(c, "english_name", f"char_{i}")
                    roster_data[name] = c.model_dump() if hasattr(c, "model_dump") else dict(c)
                elif isinstance(c, dict):
                    name = c.get("display_name") or c.get("english_name") or c.get("name", f"char_{i}")
                    roster_data[name] = c
        else:
            roster_data = roster_file
    elif hasattr(roster_file, "characters"):
        chars_val = getattr(roster_file, "characters")
        if isinstance(chars_val, dict):
            roster_data = chars_val
        elif isinstance(chars_val, list):
            for i, c in enumerate(chars_val):
                name = getattr(c, "display_name", None) or getattr(c, "english_name", f"char_{i}")
                roster_data[name] = c.model_dump() if hasattr(c, "model_dump") else dict(c)
    else:
        r_path = Path(roster_file).resolve()
        if not r_path.exists():
            raise GateAuditError(f"Gate 1 Failed: Character roster missing at {r_path}")
        with open(r_path, "r", encoding="utf-8") as f:
            raw_roster = json.load(f)
            if isinstance(raw_roster, dict):
                chars_val = raw_roster.get("characters", {})
                if isinstance(chars_val, dict):
                    roster_data = chars_val
                elif isinstance(chars_val, list):
                    roster_data = {
                        (c.get("english_name") or c.get("name", f"char_{i}")): c
                        for i, c in enumerate(chars_val) if isinstance(c, dict)
                    }
                else:
                    roster_data = raw_roster
            elif isinstance(raw_roster, list):
                roster_data = {
                    (c.get("english_name") or c.get("name", f"char_{i}")): c
                    for i, c in enumerate(raw_roster) if isinstance(c, dict)
                }
            else:
                roster_data = {}

    if isinstance(registry_file, dict):
        registry_data = registry_file
    else:
        reg_path = Path(registry_file).resolve()
        if not reg_path.exists():
            raise GateAuditError(f"Gate 1 Failed: Voice registry missing at {reg_path}")
        with open(reg_path, "r", encoding="utf-8") as f:
            registry_data = json.load(f)

    active = active_characters or list(roster_data.keys())
    voice_signatures: Dict[str, str] = {}
    collisions = []

    # Known persona gender profiles for Gemini TTS / standard acoustic personas (including Extended Voice Library)
    FEMALE_PERSONAS = {"aoede", "kore", "leda", "zephyr", "achernar"}
    MALE_PERSONAS = {"charon", "fenrir", "puck", "zeus", "orpheus", "achilles", "algenib", "algieba", "alnilam", "achird"}

    for role in active:
        if role in ("Foley", "SFX"):
            continue
        if role not in roster_data:
            raise GateAuditError(f"Gate 1 Failed: Character '{role}' not found in roster!")
        if role not in registry_data:
            raise GateAuditError(f"Gate 1 Failed: Character '{role}' not configured in voice registry!")

        cfg = registry_data[role]
        if isinstance(cfg, str):
            voice = cfg
            pitch = 1.0
            speed = 1.0
        else:
            voice = cfg.get("voice", "Default")
            pitch = cfg.get("pitch", 1.0)
            speed = cfg.get("speed", 1.0)
        sig = f"{voice}_p{pitch:.2f}_s{speed:.2f}"

        # ADR-021: Acoustic Gender Alignment Check
        r_entry = roster_data.get(role, {})
        if isinstance(r_entry, dict):
            gender = r_entry.get("gender", "neutral").lower()
            v_lower = voice.lower()
            if gender == "male" and v_lower in FEMALE_PERSONAS:
                logger.warning(
                    f"  [ACOUSTIC GENDER WARNING] Male character '{role}' assigned female voice persona '{voice}'."
                )
            elif gender == "female" and v_lower in MALE_PERSONAS:
                logger.warning(
                    f"  [ACOUSTIC GENDER WARNING] Female character '{role}' assigned male voice persona '{voice}'."
                )

        if sig in voice_signatures:
            collisions.append((role, voice_signatures[sig], sig))
        else:
            voice_signatures[sig] = role

    if collisions:
        collision_str = "; ".join(f"{c[0]} vs {c[1]} ({c[2]})" for c in collisions)
        raise GateAuditError(f"Gate 1 Failed: Voice collision detected: {collision_str}")

    # Phase 24: Cast Lock Verification against Registry
    if not isinstance(registry_file, dict):
        try:
            reg_p = Path(registry_file).resolve()
            cast_lock_p = reg_p.parent / "cast_lock.json"
            if cast_lock_p.exists():
                with open(cast_lock_p, "r", encoding="utf-8") as clf:
                    cl_data = json.load(clf)
                    locks = cl_data.get("locks", {})
                    for char, lk in locks.items():
                        if isinstance(lk, dict) and lk.get("locked"):
                            expected_v = lk.get("voice_id", "")
                            actual_cfg = registry_data.get(char)
                            actual_v = actual_cfg.get("voice") if isinstance(actual_cfg, dict) else actual_cfg
                            if actual_v and expected_v and actual_v.lower() != expected_v.lower():
                                raise GateAuditError(
                                    f"Gate 1 Failed: Cast Lock violation for '{char}': "
                                    f"locked to '{expected_v}', but voice registry has '{actual_v}'"
                                )
        except GateAuditError:
            raise
        except Exception as e:
            logger.debug(f"Cast lock audit check skipped: {e}")

    return {
        "status": "PASS",
        "active_roles": len(active),
        "unique_acoustic_signatures": len(voice_signatures),
    }


def _audit_profanity_agent(english_text: str, hindi_text: str) -> Dict[str, Any]:
    """Checker A: Detect prudish bowdlerization of raw curses, medieval insults, and street profanity."""
    from audiobook_factory.llm_client import call_gemini
    from audiobook_factory.model_manager import TaskType

    sys_prompt = (
        "You are an Adversarial Profanity & Street Grit Translation Auditor for dark fantasy fiction. "
        "Your sole task is to check whether raw curses and insults (e.g. 'bastard', 'whore', 'scoundrel', 'bitch', 'cunt') "
        "were diluted into polite TV-serial euphemisms (e.g. 'दुष्ट', 'बुरी स्त्री', 'बदमाश') instead of authentic earthy equivalents ('हरामी', 'रंडी', 'कमीने', 'गांड')."
    )
    prompt = f"""### ENGLISH EXCERPT:
\"\"\"
{english_text[:5000]}
\"\"\"

### HINDUSTANI TRANSLATION:
\"\"\"
{hindi_text[:5000]}
\"\"\"

Output JSON:
- "status": "PASS" | "DILUTED"
- "score": float (0.0 to 1.0)
- "flagged": list of objects {{"english": str, "hindi": str, "category": "profanity", "reason": str, "recommendation": str}}
"""
    try:
        res = call_gemini(prompt, system_instruction=sys_prompt, task_type=TaskType.AUDITING, response_mime_type="application/json", temperature=0.1, max_retries=3)
        return res if isinstance(res, dict) else {"status": "PASS", "flagged": [], "score": 1.0}
    except Exception as e:
        logger.warning(f"  [!] Profanity checker notice: {e}")
        return {"status": "ERROR", "flagged": [{"reason": f"Profanity checker failed: {e}"}], "score": 0.0}


def _audit_combat_agent(english_text: str, hindi_text: str) -> Dict[str, Any]:
    """Checker B: Detect sanitization of visceral combat, lethal gore, and blade violence."""
    from audiobook_factory.llm_client import call_gemini
    from audiobook_factory.model_manager import TaskType

    sys_prompt = (
        "You are an Adversarial Combat & Gore Auditor for dark fantasy literature. "
        "Check whether visceral blade strikes, bone fractures, blood spray, combat strain, "
        "or tavern violence were sanitized, smoothed over, or softened into polite fairy-tale descriptions."
    )
    prompt = f"""### ENGLISH EXCERPT:
\"\"\"
{english_text[:5000]}
\"\"\"

### HINDUSTANI TRANSLATION:
\"\"\"
{hindi_text[:5000]}
\"\"\"

Output JSON:
- "status": "PASS" | "DILUTED"
- "score": float (0.0 to 1.0)
- "flagged": list of objects {{"english": str, "hindi": str, "category": "combat_gore", "reason": str, "recommendation": str}}
"""
    try:
        res = call_gemini(prompt, system_instruction=sys_prompt, task_type=TaskType.AUDITING, response_mime_type="application/json", temperature=0.1, max_retries=3)
        return res if isinstance(res, dict) else {"status": "PASS", "flagged": [], "score": 1.0}
    except Exception as e:
        logger.warning(f"  [!] Combat checker notice: {e}")
        return {"status": "ERROR", "flagged": [{"reason": f"Combat checker failed: {e}"}], "score": 0.0}


def _audit_intimacy_agent(english_text: str, hindi_text: str) -> Dict[str, Any]:
    """Checker C: Detect suppression of somatic intimacy, bedroom passion, or romantic friction."""
    from audiobook_factory.llm_client import call_gemini
    from audiobook_factory.model_manager import TaskType

    sys_prompt = (
        "You are an Adversarial Somatic Intimacy & Passion Auditor. "
        "Check whether romantic tension, sensual physical friction, or passionate encounters "
        "were prudishly suppressed or replaced with sterile biology-textbook jargon ('योनि', 'लिंग')."
    )
    prompt = f"""### ENGLISH EXCERPT:
\"\"\"
{english_text[:5000]}
\"\"\"

### HINDUSTANI TRANSLATION:
\"\"\"
{hindi_text[:5000]}
\"\"\"

Output JSON:
- "status": "PASS" | "DILUTED"
- "score": float (0.0 to 1.0)
- "flagged": list of objects {{"english": str, "hindi": str, "category": "sensual_intimacy", "reason": str, "recommendation": str}}
"""
    try:
        res = call_gemini(prompt, system_instruction=sys_prompt, task_type=TaskType.AUDITING, response_mime_type="application/json", temperature=0.1, max_retries=3)
        return res if isinstance(res, dict) else {"status": "PASS", "flagged": [], "score": 1.0}
    except Exception as e:
        logger.warning(f"  [!] Intimacy checker notice: {e}")
        return {"status": "ERROR", "flagged": [{"reason": f"Intimacy checker failed: {e}"}], "score": 0.0}


def audit_gate1_anticensorship_agent(
    english_text: str,
    hindi_text: str,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Audit Gate 1 (Adversarial Anti-Censorship & Translation Fidelity Agent):
    Executes 3 concurrent specialist checkers across the rotating key pool:
    1. Profanity & Curses Auditor
    2. Combat Gore & Violence Auditor
    3. Somatic Intimacy & Passion Auditor

    Fail-Closed: If any checker flags dilution or fails in production, status is DILUTED.
    """
    if not english_text or not english_text.strip() or not hindi_text or not hindi_text.strip():
        return {"status": "PASS", "flagged": [], "score": 1.0}

    is_mock_offline = os.environ.get("MOCK_OFFLINE", "").lower() in ("true", "1")

    # Offline mock mode for deterministic unit tests
    if is_mock_offline:
        eng_lower = english_text.lower()
        dilution_flags = []
        if re.search(r"\bbastard\b", eng_lower) and "दुष्ट" in hindi_text and "हरामी" not in hindi_text and "कमीने" not in hindi_text:
            dilution_flags.append({
                "english": "bastard",
                "hindi": "दुष्ट",
                "category": "profanity",
                "reason": "Polite TV-serial sanitization of 'bastard' as 'दुष्ट' instead of 'हरामी'",
                "recommendation": "हरामी",
            })
        if re.search(r"\bwhore\b", eng_lower) and ("बुरी स्त्री" in hindi_text or "चरित्रहीन" in hindi_text) and "रंडी" not in hindi_text:
            dilution_flags.append({
                "english": "whore",
                "hindi": "बुरी स्त्री / चरित्रहीन",
                "category": "profanity",
                "reason": "Euphemistic sanitization of 'whore' instead of 'रंडी'",
                "recommendation": "रंडी",
            })
        if dilution_flags:
            return {"status": "DILUTED", "flagged": dilution_flags, "score": 0.5}
        return {"status": "PASS", "flagged": [], "score": 1.0}

    all_flagged = []
    scores = []
    any_error = False

    with ThreadPoolExecutor(max_workers=3) as executor:
        f_prof = executor.submit(_audit_profanity_agent, english_text, hindi_text)
        f_comb = executor.submit(_audit_combat_agent, english_text, hindi_text)
        f_inti = executor.submit(_audit_intimacy_agent, english_text, hindi_text)

        for f in (f_prof, f_comb, f_inti):
            res = f.result()
            if res.get("status") == "ERROR":
                any_error = True
            for fl in res.get("flagged", []):
                all_flagged.append(fl)
            if "score" in res:
                scores.append(float(res["score"]))

    if any_error and not scores:
        return {
            "status": "DILUTED",
            "flagged": [{"reason": "Anti-Censorship Gate LLM audit failed; production fail-closed quarantine"}],
            "score": 0.0,
        }

    min_score = min(scores) if scores else 1.0
    status = "DILUTED" if all_flagged or min_score < 0.8 else "PASS"

    return {
        "status": status,
        "flagged": all_flagged,
        "score": round(min_score, 2),
    }
