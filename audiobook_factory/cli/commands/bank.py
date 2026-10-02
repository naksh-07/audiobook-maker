from __future__ import annotations
import os
import re
import json
import time
from pathlib import Path

from audiobook_factory.cli.context import get_projects_dir, get_workspace_dir
from audiobook_factory.sound_bank import SoundBank

def cmd_bank(args):
    """Manage and inspect local Sound Bank (SQLite FTS5 index) and Virtual Sonic Catalog."""
    from audiobook_factory.sound_bank import SoundBank
    bank = SoundBank()

    action = getattr(args, "action", "stats") or "stats"

    if action == "seed":
        from audiobook_factory.catalog_seeder import seed_virtual_sound_catalog
        print("[*] Seeding virtual sound catalog from CC0 repositories (Kenney, Wikimedia)...")
        res = seed_virtual_sound_catalog(bank)
        print(f"[+] Seeding complete: {res}")
        s = bank.stats()
        print(f"    Total Sounds Indexed: {s['total_sounds']} ({s['total_duration_min']} min)")
    elif action == "scan":
        print("[*] Scanning and indexing audio assets into Sound Bank...")
        stats = bank.scan_and_index(extra_dirs=[
            get_workspace_dir() / "audiobooks" / "soundscapes" / "stems",
            get_workspace_dir() / "audiobooks" / "soundscapes" / "sfx",
        ])
        print(f"[+] Scan complete: {stats}")
    elif action == "virtual-status":
        stats = bank.stats()
        cache_stats = bank.cache_manager.get_cache_stats()
        with bank._get_conn() as conn:
            virt_count = conn.execute("SELECT COUNT(*) FROM sound_catalog WHERE is_downloaded = 0").fetchone()[0]
            dl_count = conn.execute("SELECT COUNT(*) FROM sound_catalog WHERE is_downloaded = 1").fetchone()[0]
            sources = conn.execute("SELECT source_collection, COUNT(*) FROM sound_catalog GROUP BY source_collection").fetchall()
        print("\n=======================================================")
        print("   SONIC INTELLIGENCE CATALOG & JIT CACHE STATUS       ")
        print("=======================================================")
        print(f"  Total Indexed Assets: {stats['total_sounds']}")
        print(f"  Downloaded (Local)  : {dl_count}")
        print(f"  Virtual (Remote JIT): {virt_count}")
        print(f"  Cache Usage         : {cache_stats['current_size_mb']:.1f} MB / {cache_stats['max_size_mb']:.1f} MB ({cache_stats['utilization_pct']:.1f}%)")
        print(f"  Protected Files     : {cache_stats['protected_files']}")
        print(f"  Evictable Files     : {cache_stats['evictable_files']}")
        print("  Source Collections  :")
        for sc, cnt in sources:
            sc_label = sc if sc else "local_curated"
            print(f"    - {sc_label}: {cnt} items")
        print("=======================================================\n")
    elif action == "search":
        use_virtual = getattr(args, "virtual", False)
        explain = getattr(args, "explain", False)
        cat = getattr(args, "category", None)
        if use_virtual or explain:
            results = bank.search_virtual_catalog(args.query, category=cat, limit=args.limit)
            print(f"\n[*] Found {len(results)} matches for '{args.query}' in Sonic Intelligence Catalog:")
            for r in results:
                dl_tag = "[Downloaded]" if r.get("is_downloaded") else "[Cloud/Virtual]"
                print(f"  [{r.get('category', 'SFX')}] {dl_tag} {r.get('title') or r.get('filename')} (ID: {r.get('id')}, Dur: {r.get('duration_sec', 0.0):.1f}s)")
                if explain and "why_matched" in r:
                    print(f"      Score: {r.get('search_score', 0):.2f} | Reason: {', '.join(r['why_matched'])}")
                if r.get("source_url"):
                    print(f"      Remote URL: {r.get('source_url')}")
                elif r.get("filepath"):
                    print(f"      Path: {r.get('filepath')}")
        else:
            results = bank.search(args.query, category=cat, limit=args.limit)
            print(f"\n[*] Found {len(results)} matches for '{args.query}':")
            for r in results:
                dl_tag = "[Downloaded]" if r.get("is_downloaded") else "[Cloud/Virtual]"
                print(f"  [{r['category']}] {dl_tag} {r['filename']} (Mood: {r['mood']}, Dur: {r['duration_sec']:.1f}s)")
                print(f"      Path: {r['filepath']}")
    elif action == "search-intelligence":
        apply_div = not getattr(args, "no_diversity", False)
        print(f"[*] Running Phase 3 Sonic Intelligence retrieval for: '{args.query}'...")
        res = bank.search_intelligence(args.query, limit=args.limit, apply_diversity=apply_div)
        latency = res.execution_telemetry.get("total_latency_ms", 0.0)
        intents_str = ", ".join(res.query_plan.intent_types) if res.query_plan.intent_types else "GENERAL"
        print(f"\n=======================================================")
        print(f"   SONIC INTELLIGENCE RETRIEVAL RESULTS ({len(res.ranked_cards)} matches)")
        print(f"   Plan Intents: {intents_str} (Lang: {res.query_plan.detected_language}) | Candidates: {res.total_candidates_considered} | Time: {latency:.1f}ms")
        print(f"=======================================================")
        for idx, card in enumerate(res.ranked_cards, 1):
            score_str = f"{card.retrieval_score:.3f}" if card.retrieval_score is not None else "N/A"
            print(f"  {idx}. [Score: {score_str}] Track #{card.asset_id}: {card.title or card.filename}")
            print(f"     Category: {card.category} | Dur: {card.duration_sec:.1f}s | Brightness: {card.spectral_brightness} | LUFS: {card.integrated_lufs}")
            if card.why_matched:
                print(f"     Evidence: {'; '.join(card.why_matched)}")
            print()
        if getattr(args, "card", False) and res.ranked_cards:
            print(f"\n--- Top Match AgentSoundCard v3.0 (Track #{res.ranked_cards[0].asset_id}) ---")
            print(res.ranked_cards[0].to_agent_markdown())
    elif action == "inspect":
        card = None
        try:
            aid_int = int(args.asset_id)
            card = bank.get_agent_sound_card_v3(aid_int)
            if card:
                print(card.model_dump_json(indent=2))
        except (ValueError, TypeError):
            pass
        if not card:
            card_legacy = bank.get_agent_sound_card(args.asset_id)
            if card_legacy:
                print(card_legacy)
            else:
                print(f"[-] Asset not found in catalog: {args.asset_id}")
    elif action == "prune-cache":
        target = getattr(args, "target_mb", None)
        pruned_bytes, pruned_count = bank.cache_manager.prune_to_budget(target_mb=target)
        print(f"[+] Pruned {pruned_count} cache files ({pruned_bytes / (1024*1024):.2f} MB).")
        stats = bank.cache_manager.get_cache_stats()
        print(f"    Current Cache: {stats['current_size_mb']:.1f} MB / {stats['max_size_mb']:.1f} MB ({stats['utilization_pct']:.1f}%)")
    elif action == "prefetch":
        asset_ids = list(getattr(args, "asset_ids", []) or [])
        query = getattr(args, "query", None)
        if query:
            cand_results = bank.search_virtual_catalog(query, limit=getattr(args, "limit", 5))
            asset_ids.extend([c["id"] for c in cand_results if c.get("id")])
        if not asset_ids:
            print("[-] No assets specified to prefetch. Provide asset IDs or --query.")
            return
        print(f"[*] Prefetching {len(asset_ids)} virtual assets into local cache...")
        success = 0
        for aid in asset_ids:
            try:
                p = bank.download_virtual_asset(aid)
                if p and p.exists():
                    success += 1
                    print(f"  [+] Downloaded: {p.name}")
            except Exception as e:
                print(f"  [-] Failed {aid}: {e}")
        print(f"[OK] Prefetched {success}/{len(asset_ids)} assets.")
    elif action == "ingest-source":
        src = getattr(args, "source", "seed")
        limit = getattr(args, "limit", None)
        from audiobook_factory.virtual_catalog import (
            IncompetechAdapter,
            BBCSoundEffectsAdapter,
            SonnissGDCAdapter,
            KenneyOGAAdapter,
            hydrate_from_seed,
        )
        if src == "seed":
            print("[*] Hydrating virtual sound catalog from compressed seed...")
            cnt = hydrate_from_seed(bank)
            print(f"[+] Seed hydration complete: {cnt} records processed.")
        elif src == "all":
            adapters = [SonnissGDCAdapter(), KenneyOGAAdapter(), IncompetechAdapter(), BBCSoundEffectsAdapter()]
            for adp in adapters:
                print(f"[*] Ingesting from adapter {adp.source_name} (limit={limit})...")
                res = adp.ingest_to_bank(bank, limit=limit)
                print(f"  [+] {adp.source_name}: {res}")
        else:
            adapter_map = {
                "incompetech": IncompetechAdapter,
                "bbc_sfx": BBCSoundEffectsAdapter,
                "sonniss_gdc": SonnissGDCAdapter,
                "kenney_oga": KenneyOGAAdapter,
            }
            adp_cls = adapter_map.get(src)
            if not adp_cls:
                print(f"[-] Unknown source adapter: {src}")
                return
            adp = adp_cls()
            print(f"[*] Ingesting from adapter {adp.source_name} (limit={limit})...")
            res = adp.ingest_to_bank(bank, limit=limit)
            print(f"[+] {adp.source_name} ingestion complete: {res}")
    elif action == "stats":
        s = bank.stats()
        print("\n=======================================================")
        print("   SOUND BANK STATUS SUMMARY                          ")
        print("=======================================================")
        print(f"  Total Sounds Indexed: {s['total_sounds']}")
        print(f"  Total Duration      : {s['total_duration_min']} minutes")
        print(f"  Total Storage Size  : {s['total_size_mb']} MB")
        print(f"  Categories Breakdown: {s['categories']}")
        print(f"  Moods Breakdown     : {s['moods']}")
        print(f"  SQLite FTS5 DB      : {s['database_path']}")
        print("=======================================================\n")
    elif action == "ingest":
        from audiobook_factory.sound_bank_ingest import UniversalSoundBankIngester
        ingester = UniversalSoundBankIngester()
        dir_path = Path(args.dir).resolve()
        rec = not getattr(args, "no_recursive", False)
        wrk = getattr(args, "workers", 4)
        print(f"[*] Ingesting sound assets from {dir_path} into Sound Bank via UniversalSoundBankIngester...")
        stats = ingester.ingest_directory(dir_path, recursive=rec, max_workers=wrk)
        print(
            f"[+] Ingestion complete: {stats['ingested']} indexed, {stats['failed']} failed, "
            f"{stats['total_duration_sec']/60:.1f} minutes of audio in bank."
        )
    elif action == "harvest":
        dir_path = Path(args.dir).resolve()
        rec = not getattr(args, "no_recursive", False)
        stg = getattr(args, "stages", "all")
        wrk = getattr(args, "workers", 4)
        bs = getattr(args, "batch_size", 25)
        frc = getattr(args, "force", False)
        rf = getattr(args, "retry_failed", False)
        rep = getattr(args, "report", None)
        print(f"[*] Starting Sonic Intelligence Harvest on: {dir_path}")
        print(f"    Stages: {stg} | Recursive: {rec} | Workers: {wrk} | Force: {frc}")
        stats = bank.harvest_library(
            directory=dir_path,
            recursive=rec,
            stage=stg,
            max_workers=wrk,
            batch_size=bs,
            force=frc,
            retry_failed=rf,
        )
        print("\n=======================================================")
        print("   SONIC INTELLIGENCE HARVEST SUMMARY                 ")
        print("=======================================================")
        print(f"  Total Discovered    : {stats['total_discovered']}")
        print(f"  Processed / Enriched: {stats['processed']}")
        print(f"  Skipped (Up-to-Date): {stats['skipped_valid']}")
        print(f"  Failed / Isolated   : {stats['failed']}")
        print(f"  Metadata Extracted  : {stats['metadata_extracted']}")
        print(f"  DSP Analyzed        : {stats['dsp_analyzed']}")
        print(f"  AI Enriched         : {stats['ai_enriched']}")
        print(f"  Total Duration      : {stats['elapsed_sec']:.1f}s ({stats['items_per_sec']:.1f} it/s)")
        print("=======================================================\n")
        if rep:
            p_rep = Path(rep).resolve()
            p_rep.parent.mkdir(parents=True, exist_ok=True)
            with open(p_rep, "w", encoding="utf-8") as f:
                json.dump(stats, f, indent=2)
            print(f"[+] Harvest report saved to: {p_rep}")
    elif action == "harvest-status":
        s = bank.get_harvest_status()
        print("\n=======================================================")
        print("   SONIC INTELLIGENCE HARVEST STATUS                  ")
        print("=======================================================")
        print(f"  Total Catalog Sounds : {s['total_sounds']}")
        print(f"  Local Sounds on Disk : {s['local_sounds']}")
        print(f"  DSP Analyzed Facts   : {s['dsp_analyzed']} ({s['dsp_coverage_pct']}%)")
        print(f"  CLAP Embeddings      : {s['clap_embedded']} ({s['clap_coverage_pct']}%)")
        print(f"  AudioSet Classifier  : {s['classifier_tagged']} ({s['classifier_coverage_pct']}%)")
        print(f"  Failed Analysis Runs : {s['failed_runs']}")
        print(f"  Formats Breakdown    : {s['format_breakdown']}")
        print(f"  Categories Breakdown : {s['category_breakdown']}")
        print(f"  Database             : {s['database_path']}")
        print("=======================================================\n")
    elif action == "rebuild-index":
        print("[*] Rebuilding SQLite FTS5 search index...")
        ok = bank.rebuild_search_index()
        if ok:
            print("[+] Successfully rebuilt sound_catalog_fts search index.")
        else:
            print("[-] Failed to rebuild FTS5 search index.")
    elif action in ("pilot-metadata", "pilot"):
        export_dir = getattr(args, "export_dir", "exports/metadata_pilot")
        limit = getattr(args, "limit", None)
        force = getattr(args, "force", False)
        print(f"[*] Starting Non-Destructive Metadata-Harvesting Pilot...")
        print(f"    Export Directory: {export_dir} | Limit/bundle: {limit} | Force: {force}")
        res = bank.run_metadata_pilot(
            export_dir=export_dir,
            limit_per_bundle=limit,
            force=force,
        )
        print("\n=======================================================")
        print("   METADATA-HARVESTING PILOT SUMMARY                  ")
        print("=======================================================")
        print(f"  Discovered Assets   : {res.get('total_discovered', 0)}")
        print(f"  Upserted to Catalog : {res.get('total_upserted', 0)}")
        print(f"  Duplicates Detected : {res.get('total_duplicates', 0)}")
        print(f"  Failed Extractions  : {res.get('total_failed', 0)}")
        print(f"  Execution Time      : {res.get('elapsed_seconds', 0.0):.2f}s")
        print(f"  Canonical CSV       : {res.get('canonical_csv_path', 'N/A')}")
        print(f"  Audit Report JSON   : {res.get('report_json_path', 'N/A')}")
        print(f"  Summary Markdown    : {res.get('summary_md_path', 'N/A')}")
        print("=======================================================\n")
    elif action in ("stream-harvest", "stream"):
        source = getattr(args, "source", "bbc")
        batch_size_gb = getattr(args, "batch_size_gb", 10.0)
        batch_limit_items = getattr(args, "batch_limit_items", 500)
        max_batches = getattr(args, "max_batches", None)
        workers = getattr(args, "workers", 4)
        ai_mode = getattr(args, "ai_mode", "full")
        scratch = getattr(args, "scratch", None)
        res = bank.stream_harvest(
            source=source,
            batch_size_gb=batch_size_gb,
            batch_limit_items=batch_limit_items,
            max_batches=max_batches,
            workers=workers,
            ai_mode=ai_mode,
            scratch_dir=scratch,
        )




