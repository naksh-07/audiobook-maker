import subprocess
import json
from pathlib import Path

def test_bgm_and_soundscape():
    manifest_path = Path("audiobooks/projects/witcher1/manifests/chapter_011_manifest.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    print("=== BGM CUES IN MANIFEST ===")
    for c in manifest.get("music_cues", []):
        print(f"Cue: {c.get('cue_id')} | Track: {c.get('track_name')} | Vol: {c.get('volume_db')} dB | Dur: {c.get('duration_ms')} ms")

    print("\n=== MASTERING CONFIG ===")
    m = manifest.get("mastering", {})
    print(f"Target LUFS: {m.get('target_lufs')}")
    print(f"Ducking attenuation: {m.get('ducking_attenuation_db')} dB")
    print(f"Ducking attack: {m.get('ducking_attack_ms')} ms")
    print(f"Ducking release: {m.get('ducking_release_ms')} ms")
    print(f"Spectral carve: {m.get('spectral_carve_hz')} Hz @ {m.get('spectral_carve_gain_db')} dB")

    print("\n=== AMBIENCE SCENES ===")
    for a in manifest.get("ambience_scenes", []):
        print(f"Scene: {a.get('asset_name')} | Target LUFS: {a.get('target_lufs')}")

    print("\n=== FOLEY CUES ===")
    print(f"Total Foley Cues: {len(manifest.get('foley_cues', []))}")

if __name__ == "__main__":
    test_bgm_and_soundscape()
