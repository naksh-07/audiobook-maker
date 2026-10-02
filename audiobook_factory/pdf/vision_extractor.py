from __future__ import annotations
import os
import re
import json
import base64
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional


class PDFEscalationEngine:
    """Interface for escalating suspicious PDF pages."""

    def escalate_page(self, pdf_path: Path, page_num: int) -> Optional[str]:
        raise NotImplementedError


class GeminiVisionPDFExtractor(PDFEscalationEngine):
    """
    Selective Gemini Multimodal Document Escalator.
    Only called when local extraction identifies suspicious pages and API key is present.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            try:
                from audiobook_factory.key_manager import get_persistent_key_pool
                self.api_key = get_persistent_key_pool().get_key(service="text")
            except Exception:
                pass

    def escalate_page(self, pdf_path: Path, page_num: int) -> Optional[str]:
        """
        Extracts a single suspicious page via Gemini Multimodal document API.
        If pypdf is available, creates a single-page temporary PDF to minimize token usage.
        """
        if not self.api_key:
            return None

        try:
            import pypdf
            reader = pypdf.PdfReader(str(pdf_path))
            if page_num > len(reader.pages):
                return None

            writer = pypdf.PdfWriter()
            writer.add_page(reader.pages[page_num - 1])

            import io
            buf = io.BytesIO()
            writer.write(buf)
            buf.seek(0)
            page_bytes = buf.read()
        except Exception:
            return None

        # Call Gemini API with single page PDF
        b64_data = base64.b64encode(page_bytes).decode("utf-8")
        from audiobook_factory.model_manager import get_model_manager, TaskType
        model = get_model_manager().resolve_active_model(TaskType.EXTRACTION, api_key=self.api_key)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"

        prompt = (
            "Extract all prose text from this book page in clean Markdown reading order. "
            "Strip running headers and footers. Do not summarize."
        )
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {"inlineData": {"mimeType": "application/pdf", "data": b64_data}},
                    ]
                }
            ]
        }

        try:
            headers = {"Content-Type": "application/json"}
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=30.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                # Strip optional markdown code fences and conversational LLM preambles without mutating literary typography
                text = re.sub(r"^```(?:markdown|md|text)?\s*\n?", "", text.strip(), flags=re.IGNORECASE)
                text = re.sub(r"\n?```\s*$", "", text.strip())
                text = re.sub(
                    r"^(?:sure[,!]?\s+|certainly[,!]?\s+)?(?:here|below)\s+is\s+the\s+(?:extracted|transcribed|ocr|markdown|prose)[^\n]*:\s*\n+",
                    "",
                    text.strip(),
                    flags=re.IGNORECASE,
                )
                return text.strip()
        except Exception:
            return None


