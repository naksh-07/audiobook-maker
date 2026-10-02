from __future__ import annotations
import re
import statistics
from typing import List, Dict, Any, Tuple, Optional, Set

from audiobook_factory.book_model import ConfidenceLevel
from audiobook_factory.chapter_segmenter import COMBINED_CHAPTER_REGEX
from audiobook_factory.pdf.models import PageQualityAudit, ExtractionCandidateEvaluation


class PDFQualityAnalyzer:
    """
    Heuristic analyzer for PDF page extraction quality and escalation candidate comparison.
    Evaluates density, repeated headers/footers, OCR symbol noise, reading-order coherence,
    and column layout anomalies.
    """

    REFUSAL_PATTERNS = (
        r"\bi cannot extract\b",
        r"\bi am unable to\b",
        r"\bas an ai\b",
        r"\bi'm sorry,?\s+but i can'?t\b",
        r"\bcannot assist with this request\b",
        r"^(?:sure[,!]?\s+|certainly[,!]?\s+)?here\s+is\s+the\s+(?:extracted|transcribed|ocr|markdown|prose)\b",
        r"^below\s+is\s+the\s+(?:extracted|transcribed)\b",
        r"^```",
    )

    @classmethod
    def evaluate_extraction_quality(cls, text: str) -> ExtractionCandidateEvaluation:
        """
        Computes reading-order, text-integrity, sentence-coherence, and anomaly signals
        for a page text candidate.
        """
        cleaned = (text or "").strip()
        if not cleaned:
            return ExtractionCandidateEvaluation(
                reading_order_score=0.0,
                text_integrity_score=0.0,
                sentence_coherence_score=0.0,
                composite_score=0.0,
                anomaly_count=1,
                anomalies=["Empty page text."],
            )

        lines = [ln.strip() for ln in cleaned.splitlines() if ln.strip()]
        words = cleaned.split()
        word_count = len(words)
        char_count = len(cleaned)
        line_count = len(lines)
        anomalies: List[str] = []

        # 1. Text Integrity & Anomaly Signals
        replacement_chars = cleaned.count("\ufffd")
        if replacement_chars > 0:
            anomalies.append(f"Contains {replacement_chars} Unicode replacement characters (\\ufffd).")

        symbols = len(
            re.findall(
                r"[^a-zA-Z0-9\s\u00C0-\u024F\u1E00-\u1EFF\u0900-\u097F\.,'\"‘’“”\?\!\-\—\–\:\;\(\)\[\]…\/]",
                cleaned,
            )
        )
        symbol_ratio = symbols / max(1, char_count)
        if char_count > 30 and symbol_ratio > 0.08:
            anomalies.append(f"High OCR symbol/noise ratio ({symbol_ratio:.1%}).")

        # Count clean lexical words vs gibberish/corrupted tokens
        clean_words = 0
        gibberish_words = 0
        for w in words:
            w_stripped = w.strip(".,'\"‘’“”?!-—–:;()[]…/")
            if not w_stripped:
                continue
            # Token with internal noise symbols or replacement char
            if "\ufffd" in w_stripped or re.search(
                r"[^a-zA-Z0-9\u00C0-\u024F\u1E00-\u1EFF\u0900-\u097F\-'’]", w_stripped
            ):
                gibberish_words += 1
            elif (
                re.search(r"[a-zA-Z\u00C0-\u024F\u1E00-\u1EFF\u0900-\u097F]", w_stripped)
                and re.search(r"\d", w_stripped)
                and len(w_stripped) > 4
            ):
                # Mixed alphanumeric OCR glitch like 'th3r3' or '1lI0O'
                gibberish_words += 1
            else:
                clean_words += 1

        gibberish_ratio = gibberish_words / max(1, word_count)
        if gibberish_ratio > 0.15 and word_count >= 5:
            anomalies.append(f"High gibberish/corrupt token ratio ({gibberish_ratio:.1%}).")

        # Check for LLM refusal / conversational preamble leakage
        lower_text = cleaned.lower()
        refusal_detected = any(re.search(pat, lower_text) for pat in cls.REFUSAL_PATTERNS)
        if refusal_detected:
            anomalies.append("Detected LLM refusal or meta-response text.")

        # Check for severe n-gram repetition loops
        repetition_anomaly = False
        if word_count >= 24:
            norm_tokens = [w.lower().strip(".,'\"?!") for w in words]
            fourgrams: Dict[Tuple[str, ...], int] = {}
            for i in range(len(norm_tokens) - 3):
                fg = tuple(norm_tokens[i : i + 4])
                fourgrams[fg] = fourgrams.get(fg, 0) + 1
            max_repeat = max(fourgrams.values()) if fourgrams else 0
            if max_repeat >= 5 and (max_repeat * 4) / word_count > 0.30:
                repetition_anomaly = True
                anomalies.append(f"Severe 4-gram repetition loop detected ({max_repeat}x).")

        # 2. Reading-Order & Line-Flow Coherence Signals
        short_lines = [
            ln for ln in lines
            if 0 < len(ln) < 30
            and not re.match(COMBINED_CHAPTER_REGEX, ln, flags=re.IGNORECASE)
            and not re.match(r"^(\*|\-|\_)\s*\1\s*\1+$", ln)
        ]
        short_ratio = len(short_lines) / max(1, line_count)
        lowercase_starts = sum(1 for ln in lines if ln and ln[0].islower())

        if line_count >= 10 and short_ratio > 0.50 and lowercase_starts > 4:
            anomalies.append(f"Fragmented multi-column line wrapping (short ratio {short_ratio:.1%}).")

        # Check mid-sentence abrupt line jumps / column interleaving
        mid_sentence_breaks = 0
        if line_count >= 2:
            for i in range(line_count - 1):
                cur_ln = lines[i]
                nxt_ln = lines[i + 1]
                cur_ends_open = not cur_ln.endswith((".", "!", "?", ":", ";", '"', "'", "”", "’", "।", "*"))
                # Interleaved column symptom: short line ending mid-clause followed by Capitalized unrelated start,
                # or many short fragmented lowercase lines
                if len(cur_ln) < 35 and cur_ends_open:
                    mid_sentence_breaks += 1
                elif re.search(r"\S\s{4,}\S", cur_ln):
                    mid_sentence_breaks += 1
        mid_break_ratio = mid_sentence_breaks / max(1, line_count)
        if mid_break_ratio > 0.45 and line_count >= 4:
            anomalies.append(f"Disrupted reading order / column interleaving ({mid_break_ratio:.1%}).")

        # 3. Compute Normalized Scores in [0.0, 1.0]
        integrity_penalty = (
            min(0.60, symbol_ratio * 4.0)
            + min(0.50, replacement_chars * 0.20)
            + min(0.60, gibberish_ratio * 2.0)
            + (0.80 if refusal_detected else 0.0)
            + (0.50 if repetition_anomaly else 0.0)
        )
        text_integrity_score = max(0.0, round(1.0 - integrity_penalty, 4))

        reading_order_penalty = 0.0
        if line_count >= 6:
            reading_order_penalty += max(0.0, (short_ratio - 0.25) * 0.85)
            reading_order_penalty += max(0.0, (mid_break_ratio - 0.20) * 0.75)
        elif line_count >= 2 and mid_break_ratio > 0.50:
            reading_order_penalty += 0.35
        # Penalize unresolved wide internal whitespace gutters
        wide_gutter_lines = sum(1 for ln in lines if re.search(r"\S\s{5,}\S", ln))
        if wide_gutter_lines >= 2:
            reading_order_penalty += min(0.45, (wide_gutter_lines / max(1, line_count)) * 0.6)
        reading_order_score = max(0.0, round(1.0 - reading_order_penalty, 4))

        # Sentence coherence: presence of valid terminal punctuation and reasonable sentence structure
        has_terminal = any(cleaned.endswith(p) or p in cleaned for p in (".", "!", "?", "।", '"', "”", "’"))
        sentence_coherence_score = 1.0 if has_terminal else 0.65
        if word_count < 5:
            sentence_coherence_score *= 0.60
        if lowercase_starts > 0.65 * max(1, line_count) and line_count >= 6:
            sentence_coherence_score *= 0.70
        sentence_coherence_score = round(max(0.0, min(1.0, sentence_coherence_score)), 4)

        composite_score = round(
            0.40 * reading_order_score
            + 0.45 * text_integrity_score
            + 0.15 * sentence_coherence_score,
            4,
        )

        return ExtractionCandidateEvaluation(
            word_count=word_count,
            clean_word_count=clean_words,
            char_count=char_count,
            line_count=line_count,
            symbol_noise_ratio=round(symbol_ratio, 4),
            replacement_char_count=replacement_chars,
            gibberish_token_ratio=round(gibberish_ratio, 4),
            short_fragment_ratio=round(short_ratio, 4),
            mid_sentence_break_ratio=round(mid_break_ratio, 4),
            repetition_anomaly=repetition_anomaly,
            refusal_detected=refusal_detected,
            reading_order_score=reading_order_score,
            text_integrity_score=text_integrity_score,
            sentence_coherence_score=sentence_coherence_score,
            composite_score=composite_score,
            anomaly_count=len(anomalies),
            anomalies=anomalies,
        )

    @classmethod
    def compare_extraction_candidates(
        cls,
        local_text: str,
        gemini_text: Optional[str],
        local_audit: Optional[PageQualityAudit] = None,
    ) -> Dict[str, Any]:
        """
        Compares local pypdf extraction against Gemini Vision escalation output across
        reading-order, text-integrity, anomaly count, and content coverage signals.
        Does NOT blindly prefer whichever candidate has more words.
        """
        local_eval = cls.evaluate_extraction_quality(local_text or "")
        if not gemini_text or not gemini_text.strip():
            return {
                "accept_gemini": False,
                "winner": "local",
                "reason": "Gemini escalation returned empty text.",
                "local_score": local_eval.composite_score,
                "gemini_score": 0.0,
                "local_eval": local_eval,
                "gemini_eval": None,
            }

        gemini_eval = cls.evaluate_extraction_quality(gemini_text)

        # Hard disqualifiers for Gemini candidate
        if gemini_eval.refusal_detected:
            return {
                "accept_gemini": False,
                "winner": "local",
                "reason": "Rejected Gemini output due to refusal/meta-chatter detection.",
                "local_score": local_eval.composite_score,
                "gemini_score": gemini_eval.composite_score,
                "local_eval": local_eval,
                "gemini_eval": gemini_eval,
            }

        if gemini_eval.repetition_anomaly and not local_eval.repetition_anomaly:
            return {
                "accept_gemini": False,
                "winner": "local",
                "reason": "Rejected Gemini output due to severe repetition loop anomaly.",
                "local_score": local_eval.composite_score,
                "gemini_score": gemini_eval.composite_score,
                "local_eval": local_eval,
                "gemini_eval": gemini_eval,
            }

        if gemini_eval.replacement_char_count > local_eval.replacement_char_count:
            return {
                "accept_gemini": False,
                "winner": "local",
                "reason": "Rejected Gemini output because it introduced Unicode replacement characters.",
                "local_score": local_eval.composite_score,
                "gemini_score": gemini_eval.composite_score,
                "local_eval": local_eval,
                "gemini_eval": gemini_eval,
            }

        if gemini_eval.text_integrity_score < 0.65 and gemini_eval.text_integrity_score <= local_eval.text_integrity_score:
            return {
                "accept_gemini": False,
                "winner": "local",
                "reason": f"Rejected Gemini output due to low text integrity ({gemini_eval.text_integrity_score:.2f}).",
                "local_score": local_eval.composite_score,
                "gemini_score": gemini_eval.composite_score,
                "local_eval": local_eval,
                "gemini_eval": gemini_eval,
            }

        # Truncation guard: if local had substantial clean prose, reject Gemini if it lost >45% of clean words
        if (
            local_eval.clean_word_count >= 25
            and local_eval.text_integrity_score >= 0.70
            and gemini_eval.clean_word_count < int(0.55 * local_eval.clean_word_count)
        ):
            return {
                "accept_gemini": False,
                "winner": "local",
                "reason": (
                    f"Rejected Gemini output due to content truncation "
                    f"({gemini_eval.clean_word_count} vs {local_eval.clean_word_count} clean words)."
                ),
                "local_score": local_eval.composite_score,
                "gemini_score": gemini_eval.composite_score,
                "local_eval": local_eval,
                "gemini_eval": gemini_eval,
            }

        # Case 1: Sparse / low-density local extraction (e.g. scanned page or missing font map)
        if local_eval.clean_word_count < 15:
            if (
                gemini_eval.clean_word_count > local_eval.clean_word_count
                and gemini_eval.composite_score >= 0.70
                and gemini_eval.anomaly_count == 0
            ):
                return {
                    "accept_gemini": True,
                    "winner": "gemini",
                    "reason": (
                        f"Accepted Gemini output: recovered clean prose ({gemini_eval.clean_word_count} clean words, "
                        f"score {gemini_eval.composite_score:.2f} vs {local_eval.composite_score:.2f})."
                    ),
                    "local_score": local_eval.composite_score,
                    "gemini_score": gemini_eval.composite_score,
                    "local_eval": local_eval,
                    "gemini_eval": gemini_eval,
                }
            return {
                "accept_gemini": False,
                "winner": "local",
                "reason": "Rejected Gemini output on low-density page: insufficient quality or clean words.",
                "local_score": local_eval.composite_score,
                "gemini_score": gemini_eval.composite_score,
                "local_eval": local_eval,
                "gemini_eval": gemini_eval,
            }

        # Case 2: Populated local page with layout/reading-order or OCR anomalies
        # Accept Gemini even if it has equal or slightly fewer words (e.g. due to healed hyphens or stripped noise),
        # provided it has stronger reading-order, text-integrity, or fewer anomalies!
        has_adequate_coverage = gemini_eval.clean_word_count >= int(0.65 * local_eval.clean_word_count)
        stronger_reading_order = (
            gemini_eval.reading_order_score > local_eval.reading_order_score + 0.08
            and gemini_eval.text_integrity_score >= local_eval.text_integrity_score - 0.03
        )
        stronger_integrity = (
            gemini_eval.text_integrity_score > local_eval.text_integrity_score + 0.08
            and gemini_eval.reading_order_score >= local_eval.reading_order_score - 0.03
        )
        fewer_anomalies = (
            gemini_eval.anomaly_count < local_eval.anomaly_count
            and gemini_eval.composite_score >= local_eval.composite_score
        )
        higher_composite = gemini_eval.composite_score > local_eval.composite_score + 0.04

        if has_adequate_coverage and (stronger_reading_order or stronger_integrity or fewer_anomalies or higher_composite):
            return {
                "accept_gemini": True,
                "winner": "gemini",
                "reason": (
                    f"Accepted Gemini output based on superior quality signals "
                    f"(score {gemini_eval.composite_score:.2f} vs {local_eval.composite_score:.2f}, "
                    f"reading_order {gemini_eval.reading_order_score:.2f} vs {local_eval.reading_order_score:.2f}, "
                    f"integrity {gemini_eval.text_integrity_score:.2f} vs {local_eval.text_integrity_score:.2f})."
                ),
                "local_score": local_eval.composite_score,
                "gemini_score": gemini_eval.composite_score,
                "local_eval": local_eval,
                "gemini_eval": gemini_eval,
            }

        return {
            "accept_gemini": False,
            "winner": "local",
            "reason": (
                f"Retained local extraction: Gemini candidate did not improve quality "
                f"(score {gemini_eval.composite_score:.2f} vs local {local_eval.composite_score:.2f})."
            ),
            "local_score": local_eval.composite_score,
            "gemini_score": gemini_eval.composite_score,
            "local_eval": local_eval,
            "gemini_eval": gemini_eval,
        }

    @classmethod
    def should_accept_escalation(
        cls,
        local_text: str,
        gemini_text: Optional[str],
        local_audit: Optional[PageQualityAudit] = None,
    ) -> Tuple[bool, str]:
        """Convenience wrapper returning (accept_bool, diagnostic_reason)."""
        comp = cls.compare_extraction_candidates(local_text, gemini_text, local_audit=local_audit)
        return bool(comp["accept_gemini"]), str(comp["reason"])

    @classmethod
    def audit_pages(cls, raw_pages: List[str]) -> Tuple[List[PageQualityAudit], List[str]]:
        """
        Audits raw page text and strips detected running headers/footers across consecutive pages.
        Returns: (List[PageQualityAudit], cleaned_pages)
        """
        audits: List[PageQualityAudit] = []
        cleaned_pages: List[str] = []

        # Step 1: Detect recurring headers (first lines) and footers (last lines)
        header_candidates: Dict[str, Set[int]] = {}
        footer_candidates: Dict[str, Set[int]] = {}

        for p_idx, page in enumerate(raw_pages, 1):
            lines = [ln.strip() for ln in page.splitlines() if ln.strip()]
            if len(lines) >= 3:
                first_line = lines[0].lower()
                last_line = lines[-1].lower()
                # Ignore pure numbers as page numbers are handled separately
                if not first_line.isdigit() and len(first_line) > 3:
                    header_candidates.setdefault(first_line, set()).add(p_idx)
                if not last_line.isdigit() and len(last_line) > 3:
                    footer_candidates.setdefault(last_line, set()).add(p_idx)

        # Lines repeating across >= 3 pages are designated running headers/footers
        running_headers = {text for text, pages in header_candidates.items() if len(pages) >= 3}
        running_footers = {text for text, pages in footer_candidates.items() if len(pages) >= 3}

        # Step 2: Per-page quality analysis
        for p_idx, page in enumerate(raw_pages, 1):
            lines = [ln.strip() for ln in page.splitlines()]
            # Filter out running headers and footers
            filtered_lines: List[str] = []
            for idx, ln in enumerate(lines):
                ln_lower = ln.strip().lower()
                if idx == 0 and ln_lower in running_headers:
                    continue
                if idx == len(lines) - 1 and ln_lower in running_footers:
                    continue
                filtered_lines.append(ln)

            cleaned_text = "\n".join(filtered_lines).strip()
            cleaned_pages.append(cleaned_text)

            words = cleaned_text.split()
            word_count = len(words)
            char_count = len(cleaned_text)
            line_count = len(filtered_lines)

            warnings: List[str] = []
            is_suspicious = False

            # Signal 1: Blank or abnormally low text density on interior page
            if 0 < word_count < 15 and char_count < 80:
                warnings.append(f"Low text density ({word_count} words on page).")
                is_suspicious = True

            # Signal 2: OCR noise / symbol density (e.g. broken scanned text)
            if char_count > 50:
                symbols = len(
                    re.findall(
                        r"[^a-zA-Z0-9\s\u00C0-\u024F\u1E00-\u1EFF\u0900-\u097F\.,'\"‘’“”\?\!\-\—\–\:\;\(\)\[\]…\/]",
                        cleaned_text,
                    )
                )
                symbol_ratio = symbols / char_count
                if symbol_ratio > 0.08:
                    warnings.append(f"High symbol/noise ratio ({symbol_ratio:.1%}). Likely OCR defect.")
                    is_suspicious = True

            # Signal 3: Unicode replacement character
            if "\ufffd" in cleaned_text:
                warnings.append("Page contains Unicode replacement characters (\\ufffd).")
                is_suspicious = True

            # Signal 4: Multi-column interleaving indicator (many short lines with lowercase start)
            if line_count >= 10:
                short_lines = [ln for ln in filtered_lines if 0 < len(ln) < 30]
                short_ratio = len(short_lines) / line_count
                lowercase_starts = sum(1 for ln in filtered_lines if ln and ln[0].islower())
                if short_ratio > 0.50 and lowercase_starts > 4:
                    warnings.append(f"Possible multi-column or fragmented line wrapping (short ratio {short_ratio:.1%}).")
                    is_suspicious = True

            eval_metrics = cls.evaluate_extraction_quality(cleaned_text)
            status: ConfidenceLevel = "LOW" if is_suspicious else "HIGH"
            audits.append(PageQualityAudit(
                page_number=p_idx,
                status=status,
                word_count=word_count,
                char_count=char_count,
                line_count=line_count,
                is_suspicious=is_suspicious,
                warnings=warnings,
                quality_score=eval_metrics.composite_score,
                reading_order_score=eval_metrics.reading_order_score,
                text_integrity_score=eval_metrics.text_integrity_score,
            ))

        return audits, cleaned_pages


