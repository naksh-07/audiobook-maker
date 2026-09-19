#!/usr/bin/env python3
"""
Audiobook Factory - Pillar 1: Universal Document Extractor.
Extracts clean, structured text and chapters from EPUB, PDF, TXT, and Markdown files.
Zero external pip dependencies (Pure Python 3 Standard Library).
"""

import os
import re
import json
import base64
import zipfile
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from typing import List, Dict, Any, Tuple


class TextHTMLParser(HTMLParser):
    """Parses HTML/XHTML content from EPUBs into clean Markdown text."""

    def __init__(self):
        super().__init__()
        self.pieces = []
        self.in_heading = False
        self.heading_level = 1
        self.in_paragraph = False
        self.ignore_tags = {"script", "style", "head", "title", "meta", "link"}
        self.current_ignore = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.ignore_tags:
            self.current_ignore += 1
            return

        if self.current_ignore > 0:
            return

        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.in_heading = True
            self.heading_level = int(tag[1])
            self.pieces.append("\n\n" + "#" * self.heading_level + " ")
        elif tag in ("p", "div", "blockquote", "section", "article"):
            self.in_paragraph = True
            self.pieces.append("\n\n")
        elif tag == "br":
            self.pieces.append("\n")
        elif tag == "hr":
            self.pieces.append("\n\n---\n\n")

    def handle_endtag(self, tag):
        if tag in self.ignore_tags:
            self.current_ignore = max(0, self.current_ignore - 1)
            return

        if self.current_ignore > 0:
            return

        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.in_heading = False
            self.pieces.append("\n\n")
        elif tag in ("p", "div", "blockquote", "section", "article"):
            self.in_paragraph = False
            self.pieces.append("\n\n")

    def handle_data(self, data):
        if self.current_ignore == 0:
            text = data.strip()
            if text:
                self.pieces.append(data)

    def get_clean_text(self) -> str:
        raw = "".join(self.pieces)
        # Normalize whitespace and blank lines
        lines = [line.strip() for line in raw.split("\n")]
        cleaned = []
        consecutive_blanks = 0
        for line in lines:
            if not line:
                consecutive_blanks += 1
                if consecutive_blanks <= 2:
                    cleaned.append("")
            else:
                consecutive_blanks = 0
                cleaned.append(line)
        return "\n".join(cleaned).strip()


def clean_book_text(text: str) -> str:
    """Sanitize raw book text: fix broken hyphens, strip footnotes, normalize quotes."""
    if not text:
        return ""

    # 1. Fix broken hyphenated linebreaks: e.g. "impor-\ntant" -> "important"
    text = re.sub(r"(\b\w+)-\n+(\w+\b)", r"\1\2", text)

    # 2. Normalize smart quotes and em-dashes
    replacements = {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2014": " — ",
        "\u2013": " – ",
        "\u2026": "...",
        "\r\n": "\n",
        "\r": "\n",
    }
    for orig, repl in replacements.items():
        text = text.replace(orig, repl)

    # 3. Strip footnote reference marks: e.g. "[1]", "[23]"
    text = re.sub(r"\[\d+\]", "", text)

    # 4. Remove common running headers/page number lines: e.g. "Page 42 of 300", "- 42 -"
    text = re.sub(r"^[\s\-\–—]*page\s+\d+[\s\-\–—]*$", "", text, flags=re.IGNORECASE | re.MULTILINE)
    text = re.sub(r"^[\s\-\–—]*\d+[\s\-\–—]*$", "", text, flags=re.IGNORECASE | re.MULTILINE)

    # 5. Collapse excessive whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_epub(file_path: Path) -> Tuple[Dict[str, Any], List[str]]:
    """Extract chapters and metadata from an EPUB file using zipfile and xml parsing."""
    metadata = {
        "title": file_path.stem.replace("_", " ").title(),
        "author": "Unknown Author",
        "format": "EPUB",
    }
    chapter_texts = []

    with zipfile.ZipFile(file_path, "r") as zf:
        # Find container.xml to locate rootfile (.opf)
        try:
            container_xml = zf.read("META-INF/container.xml")
            root = ET.fromstring(container_xml)
            rootfile_path = None
            for elem in root.iter():
                if elem.tag.endswith("rootfile"):
                    rootfile_path = elem.attrib.get("full-path")
                    break
        except Exception:
            rootfile_path = None

        if not rootfile_path:
            # Fallback: look for any .opf file
            for name in zf.namelist():
                if name.endswith(".opf"):
                    rootfile_path = name
                    break

        if not rootfile_path:
            raise ValueError(f"Could not locate .opf manifest in EPUB: {file_path}")

        opf_dir = str(Path(rootfile_path).parent)
        if opf_dir == ".":
            opf_dir = ""

        opf_content = zf.read(rootfile_path)
        opf_root = ET.fromstring(opf_content)

        # Parse Metadata (Title & Author)
        for elem in opf_root.iter():
            if elem.tag.endswith("title") and elem.text:
                metadata["title"] = elem.text.strip()
            elif elem.tag.endswith("creator") and elem.text:
                metadata["author"] = elem.text.strip()

        # Parse Manifest
        manifest = {}
        for elem in opf_root.iter():
            if elem.tag.endswith("item"):
                item_id = elem.attrib.get("id")
                href = elem.attrib.get("href")
                if item_id and href:
                    if opf_dir:
                        full_href = f"{opf_dir}/{href}".replace("\\", "/")
                    else:
                        full_href = href
                    manifest[item_id] = full_href

        # Parse Spine reading order
        spine = []
        for elem in opf_root.iter():
            if elem.tag.endswith("itemref"):
                idref = elem.attrib.get("idref")
                if idref in manifest:
                    spine.append(manifest[idref])

        # Read XHTML documents in spine order
        for item_path in spine:
            try:
                content = zf.read(item_path).decode("utf-8", errors="ignore")
                parser = TextHTMLParser()
                parser.feed(content)
                text = clean_book_text(parser.get_clean_text())
                if len(text.split()) >= 30:  # Skip empty covers / copyright pages
                    chapter_texts.append(text)
            except Exception:
                continue

    return metadata, chapter_texts


def extract_gemini_pdf(file_path: Path, api_key: str | None = None) -> str:
    """Extract clean structured Markdown from PDF using Gemini multimodal document API."""
    if not api_key:
        api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is required for PDF extraction.")

    with open(file_path, "rb") as f:
        pdf_bytes = f.read()

    b64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"

    prompt = (
        "You are an expert literary book digitizer. Extract all prose content from this PDF book into clean, "
        "well-structured Markdown format. "
        "Rules:\n"
        "1. Identify chapters and prefix each chapter title with '# Chapter X: Title'.\n"
        "2. Strip running headers, running footers, and page numbers.\n"
        "3. Fix broken hyphenated words and preserve natural paragraph breaks.\n"
        "4. Output only the pure extracted book text in Markdown, without conversational intro or outro."
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "inlineData": {
                            "mimeType": "application/pdf",
                            "data": b64_pdf,
                        }
                    },
                ]
            }
        ]
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return clean_book_text(text)
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Gemini PDF extraction failed (HTTP {e.code}): {err_msg}")


def segment_chapters_from_text(raw_text: str) -> List[Dict[str, str]]:
    """Segment a continuous text into structured chapters."""
    # Common chapter heading regexes
    chapter_patterns = [
        r"^(?:\s*#+\s*)?(?:chapter\s+\d+|chapter\s+[a-z]+|act\s+\d+|prologue|epilogue|introduction)\b.*$",
        r"^(?:\s*#+\s*)?(?:अध्याय\s+\d+|भाग\s+\d+|प्रस्तावना)\b.*$",
    ]

    combined_pattern = "|".join(f"(?:{p})" for p in chapter_patterns)
    splits = list(re.finditer(combined_pattern, raw_text, flags=re.IGNORECASE | re.MULTILINE))

    if not splits:
        # Fallback: split into ~3,000 word chunks on paragraph boundaries
        paragraphs = raw_text.split("\n\n")
        chapters = []
        current_chunk = []
        current_words = 0
        chap_num = 1

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            words = len(para.split())
            current_chunk.append(para)
            current_words += words

            if current_words >= 2500:
                chapters.append({
                    "title": f"Chapter {chap_num}",
                    "content": "\n\n".join(current_chunk),
                    "words": current_words,
                })
                chap_num += 1
                current_chunk = []
                current_words = 0

        if current_chunk:
            chapters.append({
                "title": f"Chapter {chap_num}",
                "content": "\n\n".join(current_chunk),
                "words": current_words,
            })
        return chapters

    # If chapter headings are found:
    chapters = []
    for idx, match in enumerate(splits):
        title = match.group(0).strip().lstrip("#").strip()
        start = match.end()
        end = splits[idx + 1].start() if idx + 1 < len(splits) else len(raw_text)
        content = raw_text[start:end].strip()

        if len(content.split()) > 20:  # Avoid empty stubs
            chapters.append({
                "title": title,
                "content": content,
                "words": len(content.split()),
            })

    # If first segment exists before chapter 1 (e.g. prologue/intro)
    if splits and splits[0].start() > 200:
        intro_content = raw_text[:splits[0].start()].strip()
        if len(intro_content.split()) >= 100:
            chapters.insert(0, {
                "title": "Prologue / Introduction",
                "content": intro_content,
                "words": len(intro_content.split()),
            })

    return chapters


def process_book_file(input_file: Path, output_base_dir: Path) -> Dict[str, Any]:
    """Universal pipeline entry: ingests book file and outputs standardized project directory."""
    input_file = Path(input_file).resolve()
    if not input_file.exists():
        raise FileNotFoundError(f"Input book file not found: {input_file}")

    book_slug = re.sub(r"[^\w\-]", "_", input_file.stem.lower()).strip("_")
    project_dir = output_base_dir / book_slug
    extracted_dir = project_dir / "extracted"
    extracted_dir.mkdir(parents=True, exist_ok=True)

    metadata = {
        "book_id": book_slug,
        "source_file": str(input_file),
        "title": input_file.stem.replace("_", " ").title(),
        "author": "Unknown Author",
        "format": input_file.suffix.lower().lstrip("."),
    }

    ext = input_file.suffix.lower()
    chapters = []

    print(f"[*] Extracting book: '{input_file.name}' (Format: {ext.upper()})...")

    if ext == ".epub":
        meta, raw_chapters = extract_epub(input_file)
        metadata.update(meta)
        for idx, chap_text in enumerate(raw_chapters, 1):
            sub_chaps = segment_chapters_from_text(chap_text)
            if sub_chaps:
                chapters.extend(sub_chaps)
            else:
                chapters.append({
                    "title": f"Chapter {idx}",
                    "content": chap_text,
                    "words": len(chap_text.split()),
                })
    elif ext in (".txt", ".md"):
        with open(input_file, "r", encoding="utf-8", errors="ignore") as f:
            raw_text = clean_book_text(f.read())
        chapters = segment_chapters_from_text(raw_text)
    elif ext == ".pdf":
        raw_text = extract_gemini_pdf(input_file)
        chapters = segment_chapters_from_text(raw_text)
    else:
        raise ValueError(f"Unsupported file format: {ext}. Supported formats: .epub, .txt, .md, .pdf")

    # Renumber and save chapters as markdown
    total_words = 0
    saved_chapters = []
    for idx, chap in enumerate(chapters, 1):
        chap_num = f"{idx:03d}"
        file_name = f"chapter_{chap_num}.md"
        file_path = extracted_dir / file_name
        title = chap.get("title", f"Chapter {idx}")
        content = chap.get("content", "")
        words = len(content.split())
        total_words += words

        md_content = f"# {title}\n\n{content}\n"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        saved_chapters.append({
            "number": idx,
            "title": title,
            "file": file_name,
            "words": words,
            "estimated_minutes": round(words / 140, 1),  # ~140 wpm spoken rate
        })

    metadata["total_chapters"] = len(saved_chapters)
    metadata["total_words"] = total_words
    metadata["estimated_total_hours"] = round(total_words / (140 * 60), 2)
    metadata["chapters"] = saved_chapters

    # Save project metadata
    meta_path = project_dir / "metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print(f"[+] Extracted {len(saved_chapters)} chapters ({total_words} words, ~{metadata['estimated_total_hours']} hrs) -> {extracted_dir}")
    return metadata
