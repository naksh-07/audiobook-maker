#!/usr/bin/env python3
"""
Audiobook Factory - Command Line Interface
Thin router delegating commands to modular packages in audiobook_factory.cli.
Maintains 100% backward compatibility for imports and monkeypatches.
"""

import os
import sys
import argparse
from pathlib import Path

# Configure UTF-8 for Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

WORKSPACE_DIR = Path(__file__).resolve().parent
PROJECTS_DIR = WORKSPACE_DIR / "audiobooks" / "projects"

# Re-export all modular command handlers from audiobook_factory.cli
from audiobook_factory.cli import (
    cmd_extract,
    cmd_translate,
    cmd_script,
    cmd_synthesize,
    cmd_master,
    cmd_produce,
    cmd_auto,
    cmd_soundscape,
    cmd_bgm,
    cmd_stems,
    cmd_package,
    cmd_direct,
    cmd_render,
    cmd_timeline,
    cmd_audit_book,
    cmd_audit,
    cmd_bank,
    cmd_stage_sounds,
)

__all__ = [
    "cmd_extract",
    "cmd_translate",
    "cmd_script",
    "cmd_synthesize",
    "cmd_master",
    "cmd_produce",
    "cmd_auto",
    "cmd_soundscape",
    "cmd_bgm",
    "cmd_stems",
    "cmd_package",
    "cmd_direct",
    "cmd_render",
    "cmd_timeline",
    "cmd_audit_book",
    "cmd_audit",
    "cmd_bank",
    "cmd_stage_sounds",
    "WORKSPACE_DIR",
    "PROJECTS_DIR",
    "main",
]


def _setup_bank_subparsers(subs):
    subs.add_parser("scan", help="Scan and index audio files into Sound Bank")
    subs.add_parser("stats", help="Display Sound Bank statistics")
    subs.add_parser("seed", help="Seed virtual sound catalog from cloud CC0 sources")
    subs.add_parser("virtual-status", help="Display Sonic Intelligence virtual catalog & JIT cache status")

    p_search = subs.add_parser("search", help="Search sounds by keywords/tags/genome")
    p_search.add_argument("query", help="Keyword or search query")
    p_search.add_argument("--limit", default=5, type=int, help="Maximum matches")
    p_search.add_argument("--category", default=None, help="Filter category (foley, ambience, music, sfx)")
    p_search.add_argument("--virtual", action="store_true", help="Include remote virtual assets in search")
    p_search.add_argument("--explain", action="store_true", help="Display match scores and explainable breakdown")

    p_search_intel = subs.add_parser("search-intelligence", help="Phase 3 Hybrid Sonic Intelligence search (FTS5 + CLAP + AST + DSP)")
    p_search_intel.add_argument("query", help="Natural language search intent (English / Hindi / Hinglish)")
    p_search_intel.add_argument("--limit", default=5, type=int, help="Maximum matches")
    p_search_intel.add_argument("--no-diversity", action="store_true", help="Disable acoustic diversity filtering")
    p_search_intel.add_argument("--card", action="store_true", help="Print full AgentSoundCard v3.0 for top match")

    p_inspect = subs.add_parser("inspect", help="Display LLM Agent Sound Card for an asset")
    p_inspect.add_argument("asset_id", help="Asset ID or filename")

    p_prune = subs.add_parser("prune-cache", help="Prune JIT audio cache to target budget")
    p_prune.add_argument("--target-mb", type=float, default=None, help="Target cache size in MB")

    p_prefetch = subs.add_parser("prefetch", help="Pre-download virtual sound assets into local cache")
    p_prefetch.add_argument("asset_ids", nargs="*", help="Asset IDs to prefetch")
    p_prefetch.add_argument("--query", default=None, help="Search query to select assets for prefetch")
    p_prefetch.add_argument("--limit", default=5, type=int, help="Number of assets to prefetch when using --query")

    p_ingest_src = subs.add_parser("ingest-source", help="Ingest open-source audio collection metadata into catalog")
    p_ingest_src.add_argument("source", choices=["seed", "incompetech", "bbc_sfx", "sonniss_gdc", "kenney_oga", "all"], help="Source adapter name or 'seed'")
    p_ingest_src.add_argument("--limit", type=int, default=None, help="Maximum items to ingest")

    p_ingest = subs.add_parser("ingest", help="Ingest local audio directory into Sound Bank via UniversalSoundBankIngester")
    p_ingest.add_argument("dir", help="Directory of sound assets to ingest")
    p_ingest.add_argument("--no-recursive", action="store_true", help="Do not scan recursively")
    p_ingest.add_argument("--workers", type=int, default=4, help="Concurrent worker threads")

    p_harvest = subs.add_parser("harvest", help="Harvest sound library into Sonic Intelligence Catalog")
    p_harvest.add_argument("dir", help="Directory of sound assets to harvest")
    p_harvest.add_argument("--stages", choices=["all", "metadata_dsp", "ai_only"], default="all", help="Harvesting pipeline stages")
    p_harvest.add_argument("--no-recursive", action="store_true", help="Do not scan recursively")
    p_harvest.add_argument("--workers", type=int, default=4, help="Worker concurrency")
    p_harvest.add_argument("--batch-size", type=int, default=25, help="Batch commit & VRAM flush size")
    p_harvest.add_argument("--force", action="store_true", help="Force re-harvest of existing assets")
    p_harvest.add_argument("--retry-failed", action="store_true", help="Retry assets with previous errors")
    p_harvest.add_argument("--report", default=None, help="Save harvest results summary JSON to path")

    subs.add_parser("harvest-status", help="Display Sonic Intelligence library harvest status & coverage")
    subs.add_parser("rebuild-index", help="Rebuild SQLite FTS5 search index")

    p_pilot = subs.add_parser("pilot-metadata", aliases=["pilot"], help="Run non-destructive metadata-harvesting pilot on Foley/Ambience slices")
    p_pilot.add_argument("--export-dir", default="exports/metadata_pilot", help="Directory to save audit reports & canonical CSV export")
    p_pilot.add_argument("--limit", type=int, default=None, help="Optional limit per bundle")
    p_pilot.add_argument("--force", action="store_true", help="Force re-harvest of unchanged assets")

    p_stream = subs.add_parser("stream-harvest", aliases=["stream"], help="Run sliding-window batch ingestion")
    p_stream.add_argument("--source", choices=["bbc", "sonniss", "incompetech", "all"], default="bbc", help="Sound source collection")
    p_stream.add_argument("--batch-size-gb", type=float, default=10.0, help="Target batch size in GB before wiping scratch")
    p_stream.add_argument("--batch-limit-items", type=int, default=500, help="Max items per batch chunk")
    p_stream.add_argument("--max-batches", type=int, default=None, help="Stop after N batches (default: continue until complete)")
    p_stream.add_argument("--workers", type=int, default=4, help="Download concurrency threads")
    p_stream.add_argument("--ai-mode", choices=["full", "dsp_only"], default="full", help="AI embedding depth")
    p_stream.add_argument("--scratch", default=None, help="Custom scratch folder path")

    p_precache = subs.add_parser("precache-essential", help="Pre-download essential studio core bundle of everyday sounds for zero-network production")
    p_precache.add_argument("--workers", type=int, default=4, help="Download concurrency threads")

    p_backfill = subs.add_parser("backfill-metadata", help="Backfill physical UCS metadata (action_type, exciter, resonator) for BBC catalog")
    p_backfill.add_argument("--dry-run", action="store_true", help="Simulate extraction without writing to database")
    p_backfill.add_argument("--limit", type=int, default=None, help="Limit number of items to process")



def main():
    parser = argparse.ArgumentParser(
        prog="audiobook-factory",
        description="Production Audiobook Factory CLI (Extraction, Translation, TTS & M4B Packaging)",
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Pipeline step to execute")

    # extract
    p_extract = subparsers.add_parser("extract", help="Extract and segment book file into clean Markdown chapters")
    p_extract.add_argument("file", help="Input book path (.epub, .pdf, .txt, .md)")
    p_extract.add_argument("--force-gate", action="store_true", help="Bypass Extraction Quality Gate REVIEW failure and force production")

    # translate
    p_translate = subparsers.add_parser("translate", help="Translate extracted chapters into literary Hindi")
    p_translate.add_argument("book", help="Project book slug (folder name)")
    p_translate.add_argument("--model", default="gemini-flash-latest", help="Gemini translation model")

    # script
    p_script = subparsers.add_parser("script", help="Generate screenplay script JSON with speaker tags")
    p_script.add_argument("book", help="Project book slug")
    p_script.add_argument("--hindi", action="store_true", help="Use translated Hindi chapters")
    p_script.add_argument("--dramatized", action="store_true", help="Multi-voice character attribution mode")

    # soundscape
    p_sc = subparsers.add_parser("soundscape", help="Generate Director Soundscape JSON Plans with moods and SFX")
    p_sc.add_argument("book", help="Project book slug")

    # synthesize
    p_synth = subparsers.add_parser("synthesize", help="Synthesize audio segments via Gemini Cloud TTS")
    p_synth.add_argument("book", help="Project book slug")
    p_synth.add_argument("--backend", default="gemini_tts", choices=["gemini_tts"], help="TTS engine (default: gemini_tts)")
    p_synth.add_argument("--voice", default="Aoede", help="Default voice persona")

    # master
    p_master = subparsers.add_parser("master", help="Concatenate segments and master audio with EBU R128")
    p_master.add_argument("book", help="Project book slug")

    # bgm
    p_bgm = subparsers.add_parser("bgm", help="Generate ambient score and apply dynamic sidechain ducking")
    p_bgm.add_argument("book", help="Project book slug")
    p_bgm.add_argument("--engine", default="ambient_bed", choices=["ambient_bed"], help="Music scoring engine (default: ambient_bed)")
    p_bgm.add_argument("--duck-db", default=-16.0, type=float, help="Sidechain attenuation in dB (default: -16)")

    # package
    p_pack = subparsers.add_parser("package", help="Assemble final M4B container with chapters")
    p_pack.add_argument("book", help="Project book slug or path")
    p_pack.add_argument("--cover", default=None, help="Cover art image path")
    p_pack.add_argument("--enforce-gate6", action="store_true", help="Abort packaging if any Gate 6 verification check fails")

    # audit-book
    p_audit_book = subparsers.add_parser("audit-book", help="Run Macro-Tier Gate 6 master audit across entire book project")
    p_audit_book.add_argument("project_dir", help="Project directory or book slug")

    # auto
    p_auto = subparsers.add_parser("auto", help="Run entire end-to-end pipeline in one command")
    p_auto.add_argument("file", help="Input book path")
    p_auto.add_argument("--hindi", action="store_true", help="Translate English book to Hindi")
    p_auto.add_argument("--backend", default="gemini_tts", choices=["gemini_tts"], help="TTS engine (default: gemini_tts)")
    p_auto.add_argument("--voice", default="Aoede", help="Voice persona")
    p_auto.add_argument("--dramatized", action="store_true", help="Multi-voice dramatization")
    p_auto.add_argument("--cover", default=None, help="Cover art image path")
    p_auto.add_argument("--workers", default=3, type=int, help="Number of concurrent TTS synthesis workers (default: 3)")
    p_auto.add_argument("--force-gate", action="store_true", help="Bypass Extraction Quality Gate REVIEW failure and force production")
    p_auto.add_argument("--force-rebuild", action="store_true", help="Invalidate cached manifests and artifacts to force complete re-generation")
    p_auto.add_argument("--stage-start", default=None, choices=["extract", "translate", "script", "tts", "produce", "direct", "mix", "package"], help="Resume pipeline from a specific stage without re-running earlier completed stages")

    # produce
    p_produce = subparsers.add_parser("produce", help="Produce cinematic chapters with 5-track standard & timeline ledger")
    p_produce.add_argument("book", help="Project book slug")
    p_produce.add_argument("--chapter", type=int, default=None, help="Specific chapter number to produce")
    p_produce.add_argument("--all", action="store_true", help="Produce all chapters in sequence")
    p_produce.add_argument("--voice", default="Aoede", help="Lead voice persona")
    p_produce.add_argument("--workers", default=3, type=int, help="TTS synthesis workers")
    p_produce.add_argument("--duck-db", default=-16.0, type=float, help="Sidechain attenuation dB")
    p_produce.add_argument("--force-rebuild", action="store_true", help="Invalidate cached manifests and artifacts to force complete re-generation")
    p_produce.add_argument("--stage-start", default=None, choices=["tts", "direct", "mix"], help="Resume chapter production from a specific sub-stage")

    # bank
    p_bank = subparsers.add_parser("bank", help="Manage and search local Sound Bank (SQLite FTS5)")
    p_bank_subs = p_bank.add_subparsers(dest="action", help="Bank action")
    _setup_bank_subparsers(p_bank_subs)

    # soundbank (alias for bank)
    p_sbank = subparsers.add_parser("soundbank", help="Manage Sound Bank (alias for bank)")
    p_sb_subs = p_sbank.add_subparsers(dest="action", help="Sound Bank action")
    _setup_bank_subparsers(p_sb_subs)

    # direct
    p_direct = subparsers.add_parser("direct", help="Direct chapter into CreativeManifest via AgentDirector")
    p_direct.add_argument("book", help="Project book slug")
    p_direct.add_argument("--chapter", type=int, required=True, help="Chapter number to direct")
    p_direct.add_argument("--output", "-o", default=None, help="Custom output manifest JSON path")

    # render
    p_render = subparsers.add_parser("render", help="Compile and render CreativeManifest with Deterministic Engine")
    p_render.add_argument("--manifest", required=True, help="Path to creative_manifest.json")
    p_render.add_argument("--vocal", default=None, help="Optional path to vocal dialogue stem")
    p_render.add_argument("--output", default=None, help="Optional output audio master path")
    p_render.add_argument("--skip-gate3-5", action="store_true", help="Skip Gate 3.5 Pre-Flight Feasibility Guard")

    # audit
    p_audit = subparsers.add_parser("audit", help="Run multi-gate independent verification audit on a chapter")
    p_audit.add_argument("book", help="Project book slug")
    p_audit.add_argument("--chapter", type=int, required=True, help="Chapter number to audit")

    # timeline
    p_timeline = subparsers.add_parser("timeline", help="Generate Gate 4.5 Master Timeline & Audio Transcript Ledger")
    p_timeline.add_argument("book", help="Project book slug")
    p_timeline.add_argument("--chapter", type=int, required=True, help="Chapter number")
    p_timeline.add_argument("--stitch", action="store_true", help="Also stitch sample-accurate vocal master track")

    # stems
    p_stems = subparsers.add_parser("stems", help="Inspect and verify exported discrete DME stems and stem ledger")
    p_stems.add_argument("book", help="Project book slug")
    p_stems.add_argument("--chapter", type=int, required=True, help="Chapter number to inspect")

    # stage-sounds
    p_stage = subparsers.add_parser("stage-sounds", help="Stage 4.5: Pre-download and verify virtual sound assets for a chapter manifest")
    p_stage.add_argument("book", nargs="?", default=None, help="Project book slug")
    p_stage.add_argument("--chapter", type=int, default=None, help="Chapter number")
    p_stage.add_argument("--manifest", default=None, help="Direct path to creative_manifest.json")
    p_stage.add_argument("--workers", type=int, default=4, help="Concurrent download workers (default: 4)")
    p_stage.add_argument("--strict", action="store_true", default=True, help="Fail closed if any asset fails verification (default: True)")

    args = parser.parse_args()

    if not args.subcommand:
        parser.print_help()
        sys.exit(1)

    cmds = {
        "extract": cmd_extract,
        "translate": cmd_translate,
        "script": cmd_script,
        "soundscape": cmd_soundscape,
        "synthesize": cmd_synthesize,
        "master": cmd_master,
        "bgm": cmd_bgm,
        "package": cmd_package,
        "bank": cmd_bank,
        "soundbank": cmd_bank,
        "produce": cmd_produce,
        "auto": cmd_auto,
        "direct": cmd_direct,
        "render": cmd_render,
        "audit": cmd_audit,
        "audit-book": cmd_audit_book,
        "timeline": cmd_timeline,
        "stems": cmd_stems,
        "stage-sounds": cmd_stage_sounds,
    }
    try:
        cmds[args.subcommand](args)
    except KeyboardInterrupt:
        print("\n\n[!] Production aborted by user (Ctrl+C). Checkpoints safely preserved on disk.", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"\n[!] Pipeline Error: {e}", file=sys.stderr)
        if os.environ.get("DEBUG"):
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
