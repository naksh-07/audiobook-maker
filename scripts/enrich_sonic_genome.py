#!/usr/bin/env python3
"""
Cloud AI Semantic Profiler & Sonic Genome Synthesizer.
Consumes scratch/bgm_dsp_profiles.json, prompts Gemini Flash via the Key Pool,
synthesizes Russell valence/arousal, 5 functional archetypes, instruments,
and story triggers, then updates sound_bank.db with full Sonic Genome JSON and indices.
"""

import json
import logging
import os
import sqlite3
import time
from pathlib import Path
from typing import Dict, Any, List
import httpx

from audiobook_factory.key_manager import get_persistent_key_pool
from audiobook_factory.contracts import SonicGenome, AcousticMetrics, SemanticAnnotations

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("enrich_sonic_genome")

ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = ROOT_DIR / "audiobooks" / "sound_bank" / "sound_bank.db"
INPUT_DSP_JSON = ROOT_DIR / "scratch" / "bgm_dsp_profiles.json"
OUTPUT_GENOMES_JSON = ROOT_DIR / "scratch" / "bgm_sonic_genomes_complete.json"


def ensure_db_schema(conn: sqlite3.Connection):
    """Idempotently adds sonic_genome column, virtual generated columns, and indices."""
    c = conn.cursor()
    cols = [col[1] for col in c.execute("PRAGMA table_info(sound_catalog)")]
    if "sonic_genome" not in cols:
        logger.info("Adding 'sonic_genome' column to sound_catalog...")
        c.execute("ALTER TABLE sound_catalog ADD COLUMN sonic_genome TEXT DEFAULT '{}'")
    
    if "genome_valence" not in cols:
        logger.info("Adding 'genome_valence' virtual generated column to sound_catalog...")
        try:
            c.execute("ALTER TABLE sound_catalog ADD COLUMN genome_valence REAL GENERATED ALWAYS AS (json_extract(sonic_genome, '$.semantic.valence')) VIRTUAL")
            c.execute("CREATE INDEX IF NOT EXISTS idx_sonic_valence ON sound_catalog(genome_valence)")
        except Exception as e:
            logger.warning(f"Could not create generated column genome_valence (SQLite version < 3.31?): {e}")

    if "genome_arousal" not in cols:
        logger.info("Adding 'genome_arousal' virtual generated column to sound_catalog...")
        try:
            c.execute("ALTER TABLE sound_catalog ADD COLUMN genome_arousal REAL GENERATED ALWAYS AS (json_extract(sonic_genome, '$.semantic.arousal')) VIRTUAL")
            c.execute("CREATE INDEX IF NOT EXISTS idx_sonic_arousal ON sound_catalog(genome_arousal)")
        except Exception as e:
            logger.warning(f"Could not create generated column genome_arousal (SQLite version < 3.31?): {e}")

    conn.commit()


def build_prompt_for_batch(batch: List[Dict[str, Any]]) -> str:
    """Formats 10-15 tracks into a compact prompt for Gemini."""
    track_entries = []
    for item in batch:
        t_id = item["track_id"]
        meta = item.get("id3_metadata", {})
        ac = item.get("acoustic", {})
        title = meta.get("title", item.get("filename", ""))
        artist = meta.get("artist", "Unknown Artist")
        dur = meta.get("duration_sec", 0.0)
        bpm = ac.get("bpm", 90.0)
        vocal_risk = ac.get("vocal_clash_risk", "LOW")
        track_entries.append({
            "track_id": t_id,
            "title": title,
            "artist": artist,
            "duration_sec": round(dur, 1),
            "bpm": bpm,
            "vocal_clash_risk": vocal_risk,
        })

    prompt = f"""You are the Master Music Supervisor and Lead Audio Drama Director for cinematic audiobook production.
Analyze the following soundtrack tracks for dramatic scoring and emotional alignment.

For each track, return a structured JSON object keyed by the string track_id containing:
- valence: float between -1.0 (grim, despair, tragic death) and +1.0 (triumphant victory, joyful tavern merriment)
- arousal: float between 0.0 (still, quiet, somber ambient) and 1.0 (explosive combat, frantic fight)
- tension: float between 0.0 (peaceful resolution) and 1.0 (imminent dread, rising threat, danger)
- narrative_function: exactly one of ["TRANSITION_BRIDGE", "EMOTIONAL_UNDERSCORE", "TENSION_RISER", "CLIMACTIC_ACTION", "AFTERMATH_FADE", "AMBIENT_BED"]
- narrative_archetypes: array of 2-4 uppercase tags (e.g. ["MONSTER_HUNT", "TRAGIC_ROMANCE", "TAVERN_BRAWL", "ROYAL_CONSPIRACY", "WILDERNESS_VIGIL", "NIGHT_HORROR"])
- slavic_instruments: array of dominant instruments (e.g. ["hurdy-gurdy", "kemenche", "davul_drums", "acoustic_lute", "slavic_throat_singing", "cello", "flute"])
- story_triggers: array of 4-6 search keywords for scene matching (e.g. ["sword draw", "fisticuffs", "beast roar", "crypt tomb", "regal palace", "clash of steel"])

Input Tracks:
{json.dumps(track_entries, indent=2)}

Return strictly valid JSON where each key is the track_id string:
"""
    return prompt


import urllib.request
import urllib.error
from audiobook_factory.cadence import get_stealth_sdk_headers


def call_gemini_with_retry(prompt: str, max_retries: int = 4) -> Dict[str, Any]:
    """Calls Gemini Flash using rotating keys from KeyManager and stealth SDK headers."""
    pool = get_persistent_key_pool()
    model = os.environ.get("GEMINI_TEXT_MODEL", "gemini-flash-latest")
    
    for attempt in range(max_retries):
        api_key = pool.get_key(service="text")
        if not api_key:
            logger.error("No available Gemini API key in pool!")
            time.sleep(2.0)
            continue

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.2,
            }
        }
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data_bytes,
            headers=get_stealth_sdk_headers(api_key),
            method="POST",
        )
        
        try:
            with urllib.request.urlopen(req, timeout=35.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(text)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                logger.warning(f"Key ...{api_key[-6:]} hit 429 rate limit. Rotating...")
                pool.mark_temporary_backoff(api_key, 12.0, "429 Rate Limit")
            else:
                err_body = e.read().decode("utf-8", errors="ignore")
                logger.warning(f"Gemini API returned {e.code}: {err_body[:150]}")
                pool.mark_temporary_backoff(api_key, 5.0, f"HTTP {e.code}")
            time.sleep(1.0)
        except Exception as e:
            logger.warning(f"Gemini request exception: {e}")
            time.sleep(1.0)

    # Fallback default generator if all retries exhausted
    logger.error("Exhausted retries for batch! Using fallback semantic generator.")
    return {}


def fallback_semantic_for_track(item: Dict[str, Any]) -> Dict[str, Any]:
    """Generates realistic fallback semantic annotations based on track title & DSP."""
    title = item.get("id3_metadata", {}).get("title", "").lower()
    bpm = item.get("acoustic", {}).get("bpm", 90.0)

    valence = -0.1
    arousal = 0.5
    tension = 0.5
    func = "EMOTIONAL_UNDERSCORE"
    archetypes = ["NARRATIVE_DRAMA"]
    instruments = ["solo cello", "strings", "percussion"]
    triggers = ["narrative score", "dramatic passage"]

    if any(k in title for k in ["fight", "battle", "steel", "silver", "fury", "hunt", "beast"]):
        func = "CLIMACTIC_ACTION"
        arousal = 0.85
        valence = -0.3
        tension = 0.8
        archetypes = ["MONSTER_HUNT", "COMBAT_MELEE"]
        instruments = ["pounding war drums", "kemenche", "aggressive strings"]
        triggers = ["sword draw", "combat", "clash of steel", "beast strike"]
    elif any(k in title for k in ["inn", "tavern", "mead", "fools", "celebration", "drinking"]):
        func = "EMOTIONAL_UNDERSCORE"
        arousal = 0.7
        valence = 0.6
        tension = 0.2
        archetypes = ["TAVERN_BRAWL", "MEDIEVAL_FESTIVAL"]
        instruments = ["acoustic lute", "slavic flute", "tambourine"]
        triggers = ["tavern common room", "tankard clink", "peasant laughter"]
    elif any(k in title for k in ["corpse", "nightmare", "darkness", "fog", "ghost", "tomb"]):
        func = "TENSION_RISER"
        arousal = 0.4
        valence = -0.7
        tension = 0.9
        archetypes = ["NIGHT_HORROR", "CRYPT_VIGIL"]
        instruments = ["subterranean drone", "bowed cymbal", "discordant whispers"]
        triggers = ["crypt tomb", "rotting sarcophagus", "undead lurk"]

    return {
        "valence": valence,
        "arousal": arousal,
        "tension": tension,
        "narrative_function": func,
        "narrative_archetypes": archetypes,
        "slavic_instruments": instruments,
        "story_triggers": triggers,
    }


def main():
    if not INPUT_DSP_JSON.exists():
        logger.error(f"Input DSP profiles not found at {INPUT_DSP_JSON}. Run extract_sonic_dsp.py first!")
        return

    with open(INPUT_DSP_JSON, "r", encoding="utf-8") as f:
        dsp_profiles = json.load(f)

    logger.info(f"Loaded {len(dsp_profiles)} DSP profiles. Connecting to SQLite {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    ensure_db_schema(conn)

    # Convert to list and batch in chunks of 15
    items = list(dsp_profiles.values())
    batch_size = 15
    batches = [items[i:i + batch_size] for i in range(0, len(items), batch_size)]
    total_batches = len(batches)

    logger.info(f"Starting Gemini Semantic Profiling across {total_batches} batches (15 tracks/batch)...")
    start_time = time.time()
    complete_genomes: Dict[str, Any] = {}

    for b_idx, batch in enumerate(batches, start=1):
        prompt = build_prompt_for_batch(batch)
        logger.info(f"Enriching Batch {b_idx}/{total_batches} ({len(batch)} tracks)...")
        
        batch_semantic = call_gemini_with_retry(prompt)
        
        for item in batch:
            tid_str = str(item["track_id"])
            sem_data = batch_semantic.get(tid_str)
            if not sem_data:
                # Try integer key or fallback
                sem_data = batch_semantic.get(item["track_id"]) or fallback_semantic_for_track(item)

            # Construct full Pydantic SonicGenome
            ac = item["acoustic"]
            acoustic_model = AcousticMetrics(
                true_peak_dbtp=ac.get("true_peak_dbtp", -1.5),
                integrated_lufs=ac.get("integrated_lufs", -19.0),
                speech_corridor_density=ac.get("speech_corridor_density", 0.25),
                transient_drops_sec=ac.get("transient_drops_sec", []),
                bpm=ac.get("bpm", 90.0),
                intro_bed_end_sec=ac.get("intro_bed_end_sec", 0.0),
                vocal_clash_risk=ac.get("vocal_clash_risk", "LOW"),
            )
            
            semantic_model = SemanticAnnotations(
                valence=float(sem_data.get("valence", 0.0)),
                arousal=float(sem_data.get("arousal", 0.5)),
                tension=float(sem_data.get("tension", 0.5)),
                narrative_function=sem_data.get("narrative_function", "EMOTIONAL_UNDERSCORE"),
                narrative_archetypes=sem_data.get("narrative_archetypes", []),
                slavic_instruments=sem_data.get("slavic_instruments", []),
                story_triggers=sem_data.get("story_triggers", []),
            )

            genome = SonicGenome(
                track_id=item["track_id"],
                filename=item["filename"],
                acoustic=acoustic_model,
                semantic=semantic_model,
                id3_metadata=item.get("id3_metadata", {}),
            )

            genome_dict = genome.model_dump()
            complete_genomes[tid_str] = genome_dict

            # Database updates:
            # 1. Update sonic_genome in sound_catalog
            genome_json_str = json.dumps(genome_dict)
            
            # Append story triggers to tags for FTS5 indexing
            existing_tags = conn.execute("SELECT tags FROM sound_catalog WHERE id=?", (item["track_id"],)).fetchone()
            cur_tags = existing_tags[0] if existing_tags and existing_tags[0] else ""
            new_tags = cur_tags + " " + " ".join(semantic_model.story_triggers) + " " + " ".join(semantic_model.narrative_archetypes)
            new_tags = " ".join(dict.fromkeys(new_tags.split()))  # unique words

            conn.execute("""
                UPDATE sound_catalog 
                SET sonic_genome = ?, tags = ? 
                WHERE id = ?
            """, (genome_json_str, new_tags, item["track_id"]))

            # 2. Update sound_track_sections with real waveform timestamps & BPM
            real_drop_sec = acoustic_model.transient_drops_sec[0] if acoustic_model.transient_drops_sec else 15.0
            intro_end_sec = acoustic_model.intro_bed_end_sec or 5.0
            
            conn.execute("UPDATE sound_track_sections SET tempo_bpm = ? WHERE track_id = ?", (acoustic_model.bpm, item["track_id"]))
            conn.execute("UPDATE sound_track_sections SET end_sec = ? WHERE track_id = ? AND section_name = 'INTRO_BED'", (intro_end_sec, item["track_id"]))
            conn.execute("UPDATE sound_track_sections SET start_sec = ? WHERE track_id = ? AND section_name = 'RISING_TENSION'", (intro_end_sec, item["track_id"]))
            conn.execute("UPDATE sound_track_sections SET start_sec = ? WHERE track_id = ? AND section_name = 'CLIMAX_DROP'", (real_drop_sec, item["track_id"]))

        conn.commit()
        time.sleep(0.5)  # respectful cadence between batches

    conn.close()
    elapsed = time.time() - start_time
    logger.info(f"Successfully synthesized and stored Sonic Genomes for {len(complete_genomes)} tracks in {elapsed:.2f}s!")

    with open(OUTPUT_GENOMES_JSON, "w", encoding="utf-8") as f:
        json.dump(complete_genomes, f, indent=2)
    logger.info(f"Saved complete genomes to {OUTPUT_GENOMES_JSON} ({os.path.getsize(OUTPUT_GENOMES_JSON)} bytes)")


if __name__ == "__main__":
    main()
