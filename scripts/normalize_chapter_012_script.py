import json
import shutil
import hashlib
from pathlib import Path

def normalize_chapter_12():
    script_path = Path("audiobooks/projects/witcher1/scripts/chapter_012_hi_script.json")
    bak_path = Path("audiobooks/projects/witcher1/scripts/chapter_012_hi_script.json.pre_norm_bak")
    
    if not bak_path.exists():
        shutil.copy2(script_path, bak_path)
        print(f"[*] Backed up original to {bak_path}")

    with open(script_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    segments = data if isinstance(data, list) else data.get("segments", [])
    print(f"[*] Processing {len(segments)} segments...")

    # Canonical speaker mapping
    SPEAKER_MAP = {
        # Chireadan variants
        "Chiredan": "Chireadan",
        "Chiridan": "Chireadan",
        "Shiradan": "Chireadan",
        "Vesemir": "Chireadan",
        # Krepp variants
        "Krep": "Krepp",
        "Priest": "Krepp",
        "Nenneke": "Krepp",  # In Ch 12, Nenneke's lines are actually Priest Krepp lecturing on Djinns
        # Neville variants
        "Mayor_Neville": "Neville",
        "King_Foltest": "Neville",  # In Ch 12, Foltest's lines are Mayor Neville
        "Velerad": "Neville",       # In Ch 12, Velerad's lines are Mayor Neville
        # Erdil variants
        "Eredil": "Erdil",
        # Guard variants
        "Gatekeeper": "Guard",
        "Door_Guard": "Guard",
        "Falwick": "Guard",         # In Ch 12, Falwick's lines are Beau Barent's gate butler
    }

    modified_count = 0
    unique_speakers_after = set()

    for idx, seg in enumerate(segments, 1):
        old_speaker = seg.get("speaker", "Narrator")
        new_speaker = SPEAKER_MAP.get(old_speaker, old_speaker)
        
        if new_speaker != old_speaker:
            seg["speaker"] = new_speaker
            modified_count += 1
            
        unique_speakers_after.add(new_speaker)

        # Ensure index is sequential 1-based
        seg["index"] = idx

        # Generate deterministic immutable uid if missing
        txt_hash = hashlib.sha256(seg.get("text", "").strip().encode("utf-8")).hexdigest()[:8]
        seg["uid"] = f"c012_s{idx:04d}_{txt_hash}"

    # Save normalized script
    output_obj = {
        "script_version": "2.0",
        "chapter_index": 12,
        "title": "THE LAST WISH (Part I) / आखिरी इच्छा",
        "total_segments": len(segments),
        "segments": segments
    }

    with open(script_path, "w", encoding="utf-8") as f:
        json.dump(output_obj, f, indent=2, ensure_ascii=False)

    print(f"[+] Canonical normalization complete! Modified {modified_count} speaker attributions.")
    print(f"[+] Final unique speakers ({len(unique_speakers_after)}):")
    for s in sorted(unique_speakers_after):
        print(f"    - {s}")

if __name__ == "__main__":
    normalize_chapter_12()
