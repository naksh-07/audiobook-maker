#!/usr/bin/env python3
"""
Test Suite for Zero Hardcoding Contracts (AST Parser Verification)
===================================================================
Uses Python's AST (Abstract Syntax Tree) module to recursively inspect
every Python file in audiobook_factory/ and strictly assert:
1. Zero hardcoded character names across snake_case, camelCase, Title Case, and numbered formats.
2. Zero chapter branching conditions (e.g. 'if chapter_num == 4', 'if "4" in str(chapter)', 'if chapter == 1').
3. Zero hardcoded soundtrack filenames or titles in core engine files (including sound_bank.py)
   across snake_case, Title Case, and numbered track titles (e.g. '001 The White Wolf', '002 The Trail').
4. Active detector verification: asserts detector flags all synthetic negative cases.
"""

import ast
import re
import unittest
from pathlib import Path
from typing import List, Tuple, Dict, Any, Set

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
FACTORY_DIR = WORKSPACE_DIR / "audiobook_factory"

# Comprehensive list of franchise / hardcoded character tokens that must never be hardcoded in engine logic
FORBIDDEN_CHARACTERS = {
    "geralt",
    "dandelion",
    "nivellen",
    "bruxa",
    "yennefer",
    "foltest",
    "cirilla",
    "ciri",
    "triss",
    "nenneke",
    "velerad",
    "calanthe",
    "pavetta",
    "dunny",
    "renfri",
    "stregobor",
    "roach",
    "vesemir",
    "eskel",
    "lambert",
    "radovid",
    "emhyr",
    "dijkstra",
    "philippa",
    "keira",
}

# Devanagari transliterations of forbidden characters to close multi-script blind spots
FORBIDDEN_CHARACTERS_DEVANAGARI = {
    "गेराल्ट",
    "डैंडेलियन",
    "निवेलेन",
    "ब्रुक्सा",
    "येनेफ़र",
    "फॉलटेस्ट",
    "सिरी",
    "नेनेके",
    "वेलेराड",
    "कैलांथे",
    "पावेत्ता",
    "डन्नी",
    "रेन्फ्री",
    "स्ट्रेगोबोर",
    "रोच",
    "वेसेमिर",
    "एस्केल",
    "लैम्बर्ट",
    "राडोविद",
    "एम्हिर",
    "डाइक्स्ट्रा",
    "फिलिपा",
    "कीरा",
}

# Known hardcoded soundtrack track bases (covers snake_case, title case, and numbered tracks)
FORBIDDEN_SOUNDTRACK_BASES = {
    "the trail",
    "white wolf",
    "the white wolf",
    "sword of destiny",
    "silver for monsters",
    "commanding the fury",
    "kaer morhen",
    "hunt or be hunted",
    "steel for humans",
    "merchants of novigrad",
    "spikeroog",
    "clootie dumpling",
    "fields of ard skellig",
    "ard skellig",
    "blood and wine",
    "geralt theme",
    "toss a coin",
    "cloak and dagger",
    "hanged mans tree",
    "hanged man",
    "inn by the crossroads",
    "blade of silver",
}

# Core engine files that must be 100% soundtrack and novel agnostic (now strictly includes sound_bank.py)
CORE_ENGINE_FILES = {
    "agent_director.py",
    "cadence.py",
    "contracts.py",
    "creative_manifest.py",
    "extractor.py",
    "ffmpeg_agent.py",
    "key_manager.py",
    "manifest_renderer.py",
    "mastering.py",
    "orchestrator.py",
    "packager.py",
    "sanitizer.py",
    "script_builder.py",
    "sound_bank.py",
    "sound_bank_ingest.py",
    "soundscape.py",
    "state.py",
    "timeline_ledger.py",
    "translator.py",
    "tts_dispatcher.py",
}


def _split_into_word_tokens(text: str) -> Set[str]:
    """
    Splits text into individual normalized word tokens across Latin and Indic (Devanagari) scripts:
    - snake_case (e.g. 'meet_bruxa' -> 'meet', 'bruxa')
    - kebab-case (e.g. 'meet-bruxa' -> 'meet', 'bruxa')
    - camelCase / PascalCase (e.g. 'meetBruxa' -> 'meet', 'bruxa')
    - numbered prefixes (e.g. '001_geralt' -> '001', 'geralt')
    - Devanagari words (e.g. 'नमस्ते, गेराल्ट' -> 'नमस्ते', 'गेराल्ट')
    """
    # First split camelCase: insert space before uppercase preceded by lowercase
    expanded = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    # Split non-alphanumeric (splits on _, -, spaces, punctuation, preserving alphanumeric and Devanagari)
    words = re.split(r"[^a-zA-Z0-9\u0900-\u097F]+", expanded.lower())
    return {w for w in words if w}


def scan_for_forbidden_characters(py_file_path: Path, tree: ast.AST) -> List[Tuple[int, str, str]]:
    """
    Scans an AST tree for any occurrences of forbidden character names in:
    - String literals (ast.Constant with str value)
    - Variable / parameter names (ast.Name)
    - Function / method names (ast.FunctionDef, ast.AsyncFunctionDef)
    - Class names (ast.ClassDef)
    - Attribute names (ast.Attribute)
    Returns a list of (line_number, node_type, matched_text).
    """
    violations = []

    def check_text(text: str, node_type: str, lineno: int):
        words = _split_into_word_tokens(text)
        matched_latin = words & FORBIDDEN_CHARACTERS
        matched_dev = words & FORBIDDEN_CHARACTERS_DEVANAGARI
        for m in (matched_latin | matched_dev):
            violations.append((lineno, node_type, m))

    for node in ast.walk(tree):
        lineno = getattr(node, "lineno", 0)

        # 1. Check string constants
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            check_text(node.value, "Constant(str)", lineno)

        # 2. Check Name identifiers
        elif isinstance(node, ast.Name):
            check_text(node.id, f"Name({node.id})", lineno)

        # 3. Check FunctionDef identifiers
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            check_text(node.name, f"FunctionDef({node.name})", lineno)

        # 4. Check ClassDef identifiers
        elif isinstance(node, ast.ClassDef):
            check_text(node.name, f"ClassDef({node.name})", lineno)

        # 5. Check Attribute accesses
        elif isinstance(node, ast.Attribute):
            check_text(node.attr, f"Attribute({node.attr})", lineno)

    return violations


def is_chapter_branching_condition(test_node: ast.AST) -> Tuple[bool, str]:
    """
    Analyzes an AST test condition expression (from an if statement or ternary expression)
    to determine if it branches on specific chapter numbers or IDs.
    Examples of violations:
      - chapter_num == 4
      - chapter == 1
      - '4' in str(chapter)
      - chapter_id == 'chapter_004'
      - chapter in [1, 2, 4]
    Generic assertions or bounds checks like:
      - chapter_num < 1 (lower bound validation)
      - not chapter_audio_files
      - chapter_num is not None
    are permitted.
    """
    # 1. ast.Compare node
    if isinstance(test_node, ast.Compare):
        left_src = ast.unparse(test_node.left).lower()
        left_is_chap = any(k in left_src for k in ("chapter", "chap_num", "chapter_num", "chap"))

        for op, comp in zip(test_node.ops, test_node.comparators):
            comp_src = ast.unparse(comp).lower()
            comp_is_chap = any(k in comp_src for k in ("chapter", "chap_num", "chapter_num", "chap"))

            # Equality / Inequality comparison against a specific chapter literal
            if isinstance(op, (ast.Eq, ast.NotEq)):
                # Case: chapter_num == 4 or chapter == 1
                if left_is_chap and isinstance(comp, ast.Constant):
                    if isinstance(comp.value, (int, float)):
                        return True, f"{left_src} {type(op).__name__} {comp.value}"
                    if isinstance(comp.value, str) and (comp.value.isdigit() or "chapter_" in comp.value.lower()):
                        return True, f"{left_src} {type(op).__name__} '{comp.value}'"
                # Case: 4 == chapter_num or 1 == chapter
                if comp_is_chap and isinstance(test_node.left, ast.Constant):
                    if isinstance(test_node.left.value, (int, float)):
                        return True, f"{test_node.left.value} {type(op).__name__} {comp_src}"
                    if isinstance(test_node.left.value, str) and (test_node.left.value.isdigit() or "chapter_" in test_node.left.value.lower()):
                        return True, f"'{test_node.left.value}' {type(op).__name__} {comp_src}"

            # In / NotIn comparison: '4' in str(chapter) or chapter in [1, 2, 3]
            elif isinstance(op, (ast.In, ast.NotIn)):
                # Case: '4' in str(chapter) or '4' in chapter
                if comp_is_chap and isinstance(test_node.left, ast.Constant):
                    if isinstance(test_node.left.value, str) and any(c.isdigit() for c in test_node.left.value):
                        return True, f"'{test_node.left.value}' {type(op).__name__} {comp_src}"
                # Case: chapter in [1, 2, 3]
                if left_is_chap and isinstance(comp, (ast.List, ast.Tuple, ast.Set)):
                    if any(isinstance(elt, ast.Constant) and isinstance(elt.value, (int, str)) for elt in comp.elts):
                        return True, f"{left_src} {type(op).__name__} {comp_src}"

    # 2. Boolean operation (and/or)
    elif isinstance(test_node, ast.BoolOp):
        for val in test_node.values:
            is_branch, reason = is_chapter_branching_condition(val)
            if is_branch:
                return True, reason

    # 3. Unary not operation (e.g. not (chapter == 4))
    elif isinstance(test_node, ast.UnaryOp) and isinstance(test_node.op, ast.Not):
        return is_chapter_branching_condition(test_node.operand)

    return False, ""


def scan_for_chapter_branching(py_file_path: Path, tree: ast.AST) -> List[Tuple[int, str, str]]:
    """
    Scans an AST tree for any if statements or ternary expressions that contain
    hardcoded chapter branching conditions.
    """
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.IfExp)):
            is_branch, reason = is_chapter_branching_condition(node.test)
            if is_branch:
                violations.append((node.lineno, ast.unparse(node.test), reason))
    return violations


def is_forbidden_soundtrack_reference(text: str) -> Tuple[bool, str]:
    """
    Checks if a string reference contains a hardcoded soundtrack title,
    supporting:
    - Numbered titles: '001 The White Wolf', '002 The Trail', '014 Silver for Monsters'
    - Title Case: 'The White Wolf', 'The Trail', 'Silver for Monsters'
    - snake_case: 'the_white_wolf.mp3', 'the_trail.wav', 'silver_for_monsters'
    - Cased or uncased formats with or without file extensions.
    """
    clean = re.sub(r"[^a-zA-Z0-9]+", " ", text.lower()).strip()
    clean_nospace = clean.replace(" ", "")

    for base in FORBIDDEN_SOUNDTRACK_BASES:
        base_clean = re.sub(r"[^a-zA-Z0-9]+", " ", base.lower()).strip()
        base_nospace = base_clean.replace(" ", "")

        # Space-separated match (e.g. '001 the white wolf' contains 'the white wolf')
        if base_clean in clean:
            return True, base
        # No-space match (e.g. 'thewhitewolf' in '001thewhitewolf' or 'silverformonsters')
        if base_nospace in clean_nospace:
            return True, base

    return False, ""


def scan_for_hardcoded_soundtracks(py_file_path: Path, tree: ast.AST) -> List[Tuple[int, str, str]]:
    """
    Scans an AST tree for any occurrences of hardcoded soundtrack titles or filenames in string constants.
    """
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            is_forbidden, matched_track = is_forbidden_soundtrack_reference(node.value)
            if is_forbidden:
                violations.append((node.lineno, node.value, matched_track))
    return violations


class TestZeroHardcodingContracts(unittest.TestCase):
    """
    Zero-Hardcoding Contract Test Suite:
    Guarantees that audiobook_factory remains 100% novel-agnostic,
    with zero character bindings, zero chapter branching, and zero soundtrack hardcodings.
    """

    @classmethod
    def setUpClass(cls):
        cls.py_files = sorted(list(FACTORY_DIR.glob("**/*.py")))
        assert len(cls.py_files) > 15, "Expected at least 15 Python files in audiobook_factory/"

    def test_01_assert_zero_hardcoded_character_names(self):
        """Recursively scans every Python file in audiobook_factory/ for forbidden character names."""
        all_violations = []

        for py_path in self.py_files:
            rel_path = py_path.relative_to(WORKSPACE_DIR)
            content = py_path.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(py_path))
            file_violations = scan_for_forbidden_characters(py_path, tree)

            for lineno, node_desc, matched_char in file_violations:
                all_violations.append(
                    f"File: {rel_path}:{lineno} | Found forbidden character '{matched_char}' in {node_desc}"
                )

        if all_violations:
            self.fail(
                f"Detected {len(all_violations)} hardcoded character violation(s) in codebase:\n"
                + "\n".join(all_violations)
            )

    def test_02_assert_zero_chapter_branching_conditions(self):
        """Recursively scans every Python file in audiobook_factory/ for chapter branching conditions."""
        all_violations = []

        for py_path in self.py_files:
            rel_path = py_path.relative_to(WORKSPACE_DIR)
            content = py_path.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(py_path))
            file_violations = scan_for_chapter_branching(py_path, tree)

            for lineno, code_snippet, reason in file_violations:
                all_violations.append(
                    f"File: {rel_path}:{lineno} | Violation: {reason} | Code: '{code_snippet}'"
                )

        if all_violations:
            self.fail(
                f"Detected {len(all_violations)} hardcoded chapter branching condition(s):\n"
                + "\n".join(all_violations)
            )

    def test_03_assert_zero_hardcoded_soundtracks_in_core_engine(self):
        """
        Scans all core engine Python files in audiobook_factory/ (strictly including sound_bank.py)
        for hardcoded soundtrack names across snake_case, Title Case, and numbered tracks.
        """
        all_violations = []

        for py_path in self.py_files:
            if py_path.name not in CORE_ENGINE_FILES:
                continue

            rel_path = py_path.relative_to(WORKSPACE_DIR)
            content = py_path.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(py_path))
            file_violations = scan_for_hardcoded_soundtracks(py_path, tree)

            for lineno, raw_str, track_name in file_violations:
                all_violations.append(
                    f"File: {rel_path}:{lineno} | Hardcoded soundtrack '{track_name}' found in string: '{raw_str}'"
                )

        if all_violations:
            self.fail(
                f"Detected {len(all_violations)} hardcoded soundtrack reference(s) in core files:\n"
                + "\n".join(all_violations)
            )

    def test_04_detector_synthetic_negative_cases(self):
        """
        Validates that the AST detectors accurately catch forbidden character names
        (snake_case, camelCase, Title Case, numbered), chapter branching conditions,
        and hardcoded soundtracks (numbered, title case, snake_case) when present.
        """
        # 1. Test character name detection across formats
        bad_char_code = """
def process_scene():
    hero = "Geralt"
    sidekick = "Dandelion"
    dev_hero = "सलाम, गेराल्ट"
    dev_bard = "डैंडेलियन"
    def meet_bruxa():
        pass
    def meetBruxa():
        pass
    tag = "001_yennefer"
"""
        tree_char = ast.parse(bad_char_code)
        violations = scan_for_forbidden_characters(Path("bad.py"), tree_char)
        found_chars = {v[2].lower() for v in violations}
        self.assertIn("geralt", found_chars)
        self.assertIn("dandelion", found_chars)
        self.assertIn("bruxa", found_chars)
        self.assertIn("yennefer", found_chars)
        self.assertIn("गेराल्ट", found_chars)
        self.assertIn("डैंडेलियन", found_chars)

        # 2. Test chapter branching condition detection
        bad_branch_codes = [
            "if chapter_num == 4: pass",
            "if chapter == 1: pass",
            "if '4' in str(chapter): pass",
            "if chapter_id == 'chapter_004': pass",
            "if chapter in [1, 2, 4]: pass",
            "result = True if chapter_num == 4 else False",
        ]
        for snippet in bad_branch_codes:
            tree_branch = ast.parse(snippet)
            branch_violations = scan_for_chapter_branching(Path("bad.py"), tree_branch)
            self.assertGreater(
                len(branch_violations), 0,
                f"AST detector failed to flag chapter branching condition: {snippet}"
            )

        # 3. Test allowable generic conditions (must NOT be flagged)
        good_conditions = [
            "if not chapter_items: pass",
            "if chapter_num is not None: pass",
            "if chapter_num < 1: pass",
            "if 'chapters' in metadata: pass",
            "if not first_chap_file.exists(): pass",
        ]
        for snippet in good_conditions:
            tree_good = ast.parse(snippet)
            good_violations = scan_for_chapter_branching(Path("good.py"), tree_good)
            self.assertEqual(
                len(good_violations), 0,
                f"AST detector erroneously flagged valid condition: {snippet} (Reason: {good_violations})"
            )

        # 4. Test soundtrack detection across numbered, title case, and snake_case formats
        bad_soundtrack_code = """
track_numbered_1 = "001 The White Wolf"
track_numbered_2 = "002 The Trail"
track_title = "The Trail"
track_snake = "the_trail.mp3"
track_battle = "014 Silver for Monsters"
track_combat = "steel_for_humans.wav"
track_expansion = "206 Blood and Wine"
"""
        tree_st = ast.parse(bad_soundtrack_code)
        st_violations = scan_for_hardcoded_soundtracks(Path("bad.py"), tree_st)
        found_tracks = {v[2] for v in st_violations}
        self.assertTrue(any("white wolf" in t for t in found_tracks))
        self.assertTrue(any("the trail" in t for t in found_tracks))
        self.assertTrue(any("silver for monsters" in t for t in found_tracks))
        self.assertTrue(any("steel for humans" in t for t in found_tracks))
        self.assertTrue(any("blood and wine" in t for t in found_tracks))


if __name__ == "__main__":
    unittest.main()
