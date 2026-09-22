#!/usr/bin/env python3
"""
Audiobook Factory - Fantasy Sound Pack Downloader & Acoustic Synthesizer.
Downloads authentic CC0 fantasy assets and crafts broadcast-standard 48kHz WAV/OGG assets for:
- Witcher Signs: Igni, Aard, Quen, Axii, Yrden
- Monsters: Striga, Ghoul, Wolf
- Combat Foley: Sword draw, sword clash, body thud, armor clank
- Fantasy Ambiences: Crypt/Tomb, Castle Hall Hearth, Bog Swamp, Blizzard Mountain

Automatically indexes and populates both `sound_catalog` and `sound_assets` in SQLite FTS5.
"""

import io
import os
import sys
import shutil
import hashlib
import zipfile
import subprocess
import urllib.request
from pathlib import Path

# Configure Windows UTF-8 stdout
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

SOUND_BANK_DIR = ROOT_DIR / "audiobooks" / "sound_bank"
SFX_DIR = SOUND_BANK_DIR / "sfx"
FOLEY_DIR = SOUND_BANK_DIR / "foley"
AMBIENCE_DIR = SOUND_BANK_DIR / "ambience"

SFX_DIR.mkdir(parents=True, exist_ok=True)
FOLEY_DIR.mkdir(parents=True, exist_ok=True)
AMBIENCE_DIR.mkdir(parents=True, exist_ok=True)

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
HEADERS = {
    "User-Agent": "AudiobookFactory/2.0 (https://github.com/naksh-07/audiobook-maker; audio@audiobook.org)"
}


def get_wikimedia_url(filename: str) -> str:
    fname = filename.replace("File:", "").strip().replace(" ", "_")
    md5 = hashlib.md5(fname.encode("utf-8")).hexdigest()
    return f"https://upload.wikimedia.org/wikipedia/commons/{md5[0]}/{md5[0:2]}/{fname}"


def download_file(url: str, target_path: Path) -> bool:
    """Download file with retry and browser headers."""
    if target_path.exists() and target_path.stat().st_size > 1000:
        print(f"  [-] Already cached: {target_path.name}")
        return True

    print(f"  [*] Downloading {target_path.name} from {url}...")
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read()
            target_path.write_bytes(content)
            print(f"  [+] Saved {target_path.name} ({len(content) / 1024:.1f} KB)")
            return True
    except Exception as e:
        print(f"  [!] Failed to download {target_path.name}: {e}")
        return False


def download_and_extract_zip(url: str, extract_to: Path, prefix: str = "") -> int:
    """Download in-memory zip and extract audio files."""
    extract_to.mkdir(parents=True, exist_ok=True)
    existing = list(extract_to.glob(f"{prefix}_*")) if prefix else list(extract_to.glob("*.ogg"))
    if len(existing) > 5:
        print(f"  [-] Already extracted {len(existing)} sounds into {extract_to.name}/")
        return len(existing)

    print(f"[*] Fetching archive: {url}...")
    req = urllib.request.Request(url, headers=HEADERS)
    extracted = 0
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = resp.read()
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                for member in z.infolist():
                    if member.is_dir() or member.filename.endswith(".sfk"):
                        continue
                    m_path = Path(member.filename)
                    if m_path.suffix.lower() not in (".wav", ".ogg", ".mp3", ".flac"):
                        continue
                    clean_name = f"{prefix}_{m_path.name}" if prefix else m_path.name
                    dest_file = extract_to / clean_name
                    with z.open(member) as src, open(dest_file, "wb") as dst:
                        dst.write(src.read())
                    extracted += 1
        print(f"  [+] Extracted {extracted} sounds into {extract_to.name}/")
        return extracted
    except Exception as e:
        print(f"  [!] Archive extraction failed: {e}")
        return 0


def render_audio(cmd: list, out_path: Path, desc: str = ""):
    """Execute FFmpeg command to render audio asset."""
    if out_path.exists() and out_path.stat().st_size > 1000:
        print(f"  [-] Already generated: {out_path.name}")
        return
    print(f"  [*] Synthesizing {desc or out_path.name}...")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"  [!] FFmpeg error for {out_path.name}: {res.stderr[:200]}")
    else:
        print(f"  [+] Created {out_path.name} ({out_path.stat().st_size / 1024:.1f} KB)")


def build_witcher_signs():
    """Synthesize authentic acoustic Witcher signs: Igni, Aard, Quen, Axii, Yrden."""
    print("\n--- 1. Synthesizing Witcher Signs (Igni, Aard, Quen, Axii, Yrden) ---")

    # 1. Igni: Combustion roar, flame burst whoosh, fire crackle
    igni_path = SFX_DIR / "witcher_sign_igni_fire_burst.wav"
    cmd_igni = [
        FFMPEG, "-y",
        "-f", "lavfi", "-i", "anoisesrc=d=2.4:c=pink:r=48000,bandpass=f=480:w=320,volume=3.5",
        "-f", "lavfi", "-i", "sine=f=80:d=2.4",
        "-f", "lavfi", "-i", "anoisesrc=d=2.4:c=white:r=48000,highpass=f=2500,volume=0.4",
        "-filter_complex",
        "[0:a][1:a]amix=inputs=2:weights=1.0 0.6[low];"
        "[low][2:a]amix=inputs=2:weights=1.0 0.5[mix];"
        "[mix]afade=t=in:ss=0:d=0.06,afade=t=out:st=1.2:d=1.2,aresample=48000[out]",
        "-map", "[out]", "-c:a", "pcm_s16le", str(igni_path)
    ]
    render_audio(cmd_igni, igni_path, "Witcher Sign IGNI (Flame Combustion Burst)")

    # 2. Aard: Concussive telekinetic air shockwave + sub-bass blast
    aard_path = SFX_DIR / "witcher_sign_aard_shockwave.wav"
    cmd_aard = [
        FFMPEG, "-y",
        "-f", "lavfi", "-i", "anoisesrc=d=1.8:c=brown:r=48000,lowpass=f=180,volume=4.5",
        "-f", "lavfi", "-i", "sine=f=60:d=1.8",
        "-f", "lavfi", "-i", "anoisesrc=d=1.8:c=pink:r=48000,bandpass=f=350:w=200,volume=2.0",
        "-filter_complex",
        "[0:a][1:a][2:a]amix=inputs=3:weights=1.0 0.8 0.5[mix];"
        "[mix]afade=t=in:ss=0:d=0.03,afade=t=out:st=0.6:d=1.2,bass=g=8:f=80,aresample=48000[out]",
        "-map", "[out]", "-c:a", "pcm_s16le", str(aard_path)
    ]
    render_audio(cmd_aard, aard_path, "Witcher Sign AARD (Concussive Shockwave Blast)")

    # 3. Quen: Protective barrier shield hum + harmonic resonance
    quen_path = SFX_DIR / "witcher_sign_quen_shield_barrier.wav"
    cmd_quen = [
        FFMPEG, "-y",
        "-f", "lavfi", "-i", "sine=f=220:d=3.0",
        "-f", "lavfi", "-i", "sine=f=440:d=3.0",
        "-f", "lavfi", "-i", "anoisesrc=d=3.0:c=pink:r=48000,bandpass=f=800:w=300,volume=1.2",
        "-filter_complex",
        "[0:a][1:a]amix=inputs=2:weights=0.7 0.5[tones];"
        "[tones]flanger=delay=8:depth=4:regen=50:width=80:speed=0.5[chorus];"
        "[chorus][2:a]amix=inputs=2:weights=0.8 0.3[mix];"
        "[mix]afade=t=in:ss=0:d=0.15,afade=t=out:st=1.8:d=1.2,aresample=48000[out]",
        "-map", "[out]", "-c:a", "pcm_s16le", str(quen_path)
    ]
    render_audio(cmd_quen, quen_path, "Witcher Sign QUEN (Protective Forcefield Shield)")

    # 4. Axii: Hypnotic psychic pulse + ethereal bell shimmer
    axii_path = SFX_DIR / "witcher_sign_axii_hypnotic_chime.wav"
    cmd_axii = [
        FFMPEG, "-y",
        "-f", "lavfi", "-i", "sine=f=523.25:d=3.2",
        "-f", "lavfi", "-i", "sine=f=659.25:d=3.2",
        "-f", "lavfi", "-i", "sine=f=783.99:d=3.2",
        "-filter_complex",
        "[0:a][1:a][2:a]amix=inputs=3:weights=0.6 0.5 0.4[triad];"
        "[triad]vibrato=f=4:d=0.3,aecho=0.8:0.88:250|500:0.4|0.2[echo];"
        "[echo]afade=t=in:ss=0:d=0.08,afade=t=out:st=1.8:d=1.4,aresample=48000[out]",
        "-map", "[out]", "-c:a", "pcm_s16le", str(axii_path)
    ]
    render_audio(cmd_axii, axii_path, "Witcher Sign AXII (Hypnotic Psychic Charm Chime)")

    # 5. Yrden: Arcane trap glyph / electric discharge spark
    yrden_path = SFX_DIR / "witcher_sign_yrden_arcane_trap.wav"
    cmd_yrden = [
        FFMPEG, "-y",
        "-f", "lavfi", "-i", "anoisesrc=d=2.0:c=white:r=48000,bandpass=f=2800:w=1200,volume=3.0",
        "-f", "lavfi", "-i", "sine=f=120:d=2.0",
        "-f", "lavfi", "-i", "anoisesrc=d=2.0:c=pink:r=48000,highpass=f=4000,volume=1.5",
        "-filter_complex",
        "[0:a]aphaser=in_gain=0.8:out_gain=0.74:delay=2.5:decay=0.5:speed=2.0:type=t[zap];"
        "[zap][1:a][2:a]amix=inputs=3:weights=1.0 0.5 0.7[mix];"
        "[mix]afade=t=in:ss=0:d=0.02,afade=t=out:st=0.8:d=1.2,aresample=48000[out]",
        "-map", "[out]", "-c:a", "pcm_s16le", str(yrden_path)
    ]
    render_audio(cmd_yrden, yrden_path, "Witcher Sign YRDEN (Arcane Electric Trap Spark)")


def build_monster_and_combat_assets():
    """Synthesize monsters (Striga, Ghoul, Wolf) and Combat Foley (Draw, Clash, Thud, Armor)."""
    print("\n--- 2. Building Monster SFX & Combat Foley ---")

    # Download raw sources from Wikimedia Commons
    grizzly_raw = SFX_DIR / "grizzly_bear_raw.mp3"
    download_file(get_wikimedia_url("Yellowstone sound library - Grizzly Bears Roar - 001.mp3"), grizzly_raw)

    varecia_raw = SFX_DIR / "varecia_snarl_raw.ogg"
    download_file(get_wikimedia_url("Varecia growl-snort1.ogg"), varencia_path := varecia_raw)

    wolf_raw = SFX_DIR / "wolf_howl_raw.ogg"
    download_file(get_wikimedia_url("Wolf howls.ogg"), wolf_raw)

    # 1. Striga Monster Beast Roar: Processed guttural roar with demonic sub-harmonics
    striga_path = SFX_DIR / "striga_beast_roar.wav"
    if grizzly_raw.exists():
        cmd_striga = [
            FFMPEG, "-y", "-i", str(grizzly_raw),
            "-filter_complex",
            "[0:a]asetrate=48000*0.75,aresample=48000,bass=g=6:f=100,aecho=0.8:0.88:150:0.3[fx];"
            "[fx]afade=t=in:ss=0:d=0.1,afade=t=out:st=2.5:d=1.0[out]",
            "-map", "[out]", "-t", "3.5", "-c:a", "pcm_s16le", str(striga_path)
        ]
        render_audio(cmd_striga, striga_path, "Striga Demonic Beast Roar")
    else:
        # High quality synthesis fallback
        cmd_striga = [
            FFMPEG, "-y",
            "-f", "lavfi", "-i", "anoisesrc=d=3.0:c=pink:r=48000,bandpass=f=350:w=250,volume=3.5",
            "-f", "lavfi", "-i", "sine=f=85:d=3.0",
            "-filter_complex",
            "[0:a][1:a]amix=inputs=2:weights=1.0 0.8[mix];"
            "[mix]tremolo=f=12:d=0.8,bass=g=8:f=90,aecho=0.8:0.88:200:0.4[out]",
            "-map", "[out]", "-c:a", "pcm_s16le", str(striga_path)
        ]
        render_audio(cmd_striga, striga_path, "Striga Demonic Beast Roar (Synthesized)")

    # 2. Ghoul Necrophage Scavenger Snarl & Flesh Rip
    ghoul_path = SFX_DIR / "ghoul_scavenger_snarl.wav"
    if varecia_raw.exists():
        cmd_ghoul = [
            FFMPEG, "-y", "-i", str(varecia_raw),
            "-filter_complex",
            "[0:a]asetrate=48000*0.82,aresample=48000,treble=g=4:f=3000,aecho=0.8:0.7:100:0.25[fx];"
            "[fx]afade=t=in:ss=0:d=0.05,afade=t=out:st=1.2:d=0.8[out]",
            "-map", "[out]", "-t", "2.2", "-c:a", "pcm_s16le", str(ghoul_path)
        ]
        render_audio(cmd_ghoul, ghoul_path, "Ghoul Necrophage Snarl")
    else:
        cmd_ghoul = [
            FFMPEG, "-y",
            "-f", "lavfi", "-i", "anoisesrc=d=2.0:c=brown:r=48000,bandpass=f=600:w=300,volume=3.0",
            "-filter_complex", "[0:a]tremolo=f=18:d=0.9,aresample=48000[out]",
            "-map", "[out]", "-c:a", "pcm_s16le", str(ghoul_path)
        ]
        render_audio(cmd_ghoul, ghoul_path, "Ghoul Snarl (Synthesized)")

    # 3. Wolf Pack Howl
    wolf_path = SFX_DIR / "wolf_pack_howl.wav"
    if wolf_raw.exists():
        cmd_wolf = [
            FFMPEG, "-y", "-i", str(wolf_raw),
            "-filter_complex",
            "[0:a]aresample=48000,highpass=f=200,aecho=0.8:0.85:300:0.35[out]",
            "-map", "[out]", "-t", "5.0", "-c:a", "pcm_s16le", str(wolf_path)
        ]
        render_audio(cmd_wolf, wolf_path, "Wolf Pack Howl")

    # 4. Sword Draw: Sharp steel scabbard friction draw
    sword_draw_path = FOLEY_DIR / "sword_draw_scabbard.wav"
    cmd_draw = [
        FFMPEG, "-y",
        "-f", "lavfi", "-i", "anoisesrc=d=1.2:c=white:r=48000,bandpass=f=3500:w=800,volume=2.5",
        "-f", "lavfi", "-i", "sine=f=2400:d=1.2",
        "-filter_complex",
        "[0:a][1:a]amix=inputs=2:weights=1.0 0.4[mix];"
        "[mix]afade=t=in:ss=0:d=0.08,afade=t=out:st=0.5:d=0.7,aresample=48000[out]",
        "-map", "[out]", "-c:a", "pcm_s16le", str(sword_draw_path)
    ]
    render_audio(cmd_draw, sword_draw_path, "Sword Draw From Scabbard")

    # 5. Sword Clash / Parry: Sharp blade clash with high ring
    sword_clash_path = FOLEY_DIR / "sword_clash_parry.wav"
    cmd_clash = [
        FFMPEG, "-y",
        "-f", "lavfi", "-i", "sine=f=1850:d=1.5",
        "-f", "lavfi", "-i", "sine=f=3200:d=1.5",
        "-f", "lavfi", "-i", "anoisesrc=d=1.5:c=white:r=48000,bandpass=f=4000:w=1500,volume=3.0",
        "-filter_complex",
        "[0:a][1:a][2:a]amix=inputs=3:weights=0.8 0.6 1.0[mix];"
        "[mix]afade=t=in:ss=0:d=0.01,afade=t=out:st=0.2:d=1.3,aresample=48000[out]",
        "-map", "[out]", "-c:a", "pcm_s16le", str(sword_clash_path)
    ]
    render_audio(cmd_clash, sword_clash_path, "Sword Clash Parry")

    # 6. Body Thud / Heavy Fall: Sub-bass stone / ground impact
    body_thud_path = FOLEY_DIR / "body_thud_heavy_fall.wav"
    cmd_thud = [
        FFMPEG, "-y",
        "-f", "lavfi", "-i", "sine=f=55:d=1.2",
        "-f", "lavfi", "-i", "anoisesrc=d=1.2:c=brown:r=48000,lowpass=f=160,volume=4.0",
        "-filter_complex",
        "[0:a][1:a]amix=inputs=2:weights=0.8 1.0[mix];"
        "[mix]afade=t=in:ss=0:d=0.02,afade=t=out:st=0.2:d=1.0,bass=g=9:f=65,aresample=48000[out]",
        "-map", "[out]", "-c:a", "pcm_s16le", str(body_thud_path)
    ]
    render_audio(cmd_thud, body_thud_path, "Body Thud Heavy Fall")

    # 7. Armor Clank / Chainmail: Medieval plate & mail movement
    armor_clank_path = FOLEY_DIR / "armor_clank_chainmail.wav"
    cmd_armor = [
        FFMPEG, "-y",
        "-f", "lavfi", "-i", "anoisesrc=d=1.5:c=white:r=48000,bandpass=f=2200:w=900,volume=2.2",
        "-f", "lavfi", "-i", "sine=f=1200:d=1.5",
        "-filter_complex",
        "[0:a]tremolo=f=15:d=0.7[rattle];"
        "[rattle][1:a]amix=inputs=2:weights=1.0 0.3[mix];"
        "[mix]afade=t=in:ss=0:d=0.05,afade=t=out:st=0.4:d=1.1,aresample=48000[out]",
        "-map", "[out]", "-c:a", "pcm_s16le", str(armor_clank_path)
    ]
    render_audio(cmd_armor, armor_clank_path, "Armor Clank Chainmail")


def build_fantasy_ambiences():
    """Synthesize fantasy environmental ambiences: Crypt, Castle Hall, Bog Swamp, Blizzard Mountain."""
    print("\n--- 3. Synthesizing Fantasy Ambiences ---")

    # 1. Crypt / Tomb: Subterranean damp cavern with deep reverb drips
    crypt_path = AMBIENCE_DIR / "amb_crypt_tomb_drips.wav"
    cmd_crypt = [
        FFMPEG, "-y",
        "-f", "lavfi", "-i", "anoisesrc=d=15.0:c=pink:r=48000,lowpass=f=140,volume=1.8",
        "-f", "lavfi", "-i", "sine=f=45:d=15.0",
        "-filter_complex",
        "[0:a][1:a]amix=inputs=2:weights=1.0 0.4[drone];"
        "[drone]aecho=0.8:0.9:500|1000:0.5|0.3,afade=t=in:ss=0:d=2.0,afade=t=out:st=13.0:d=2.0,aresample=48000[out]",
        "-map", "[out]", "-c:a", "pcm_s16le", str(crypt_path)
    ]
    render_audio(cmd_crypt, crypt_path, "Crypt & Tomb Subterranean Bed")

    # 2. Castle Hall Hearth: Warm great hall fireplace crackle
    hearth_raw = AMBIENCE_DIR / "dry_grass_fireplace_raw.ogg"
    download_file(get_wikimedia_url("Dry grass burning in open fireplace.ogg"), hearth_raw)

    castle_path = AMBIENCE_DIR / "amb_castle_hall_hearth.wav"
    if hearth_raw.exists():
        cmd_castle = [
            FFMPEG, "-y", "-i", str(hearth_raw),
            "-filter_complex",
            "[0:a]aecho=0.8:0.85:120|240:0.3|0.15,afade=t=in:ss=0:d=1.5,afade=t=out:st=12.0:d=2.0,aresample=48000[out]",
            "-map", "[out]", "-t", "14.0", "-c:a", "pcm_s16le", str(castle_path)
        ]
        render_audio(cmd_castle, castle_path, "Castle Hall Fireplace Hearth")
    else:
        cmd_castle = [
            FFMPEG, "-y",
            "-f", "lavfi", "-i", "anoisesrc=d=12.0:c=pink:r=48000,bandpass=f=1200:w=800,volume=1.5",
            "-filter_complex", "[0:a]aecho=0.8:0.8:100:0.2,aresample=48000[out]",
            "-map", "[out]", "-c:a", "pcm_s16le", str(castle_path)
        ]
        render_audio(cmd_castle, castle_path, "Castle Hall Fireplace Hearth (Synthesized)")

    # 3. Bog Swamp Night: Murky wetland night, low wind drone, eerie moisture
    bog_path = AMBIENCE_DIR / "amb_bog_swamp_night.wav"
    cmd_bog = [
        FFMPEG, "-y",
        "-f", "lavfi", "-i", "anoisesrc=d=15.0:c=pink:r=48000,bandpass=f=300:w=180,volume=1.6",
        "-f", "lavfi", "-i", "anoisesrc=d=15.0:c=white:r=48000,highpass=f=3500,volume=0.25",
        "-filter_complex",
        "[0:a][1:a]amix=inputs=2:weights=1.0 0.5[mix];"
        "[mix]flanger=delay=15:depth=6:speed=0.2,afade=t=in:ss=0:d=2.0,afade=t=out:st=13.0:d=2.0,aresample=48000[out]",
        "-map", "[out]", "-c:a", "pcm_s16le", str(bog_path)
    ]
    render_audio(cmd_bog, bog_path, "Bog Swamp Night Bed")

    # 4. Blizzard Mountain Gale: Howling arctic wind and biting frost
    blizzard_path = AMBIENCE_DIR / "amb_blizzard_mountain_gale.wav"
    wind_existing = AMBIENCE_DIR / "wind_howl.ogg"
    if wind_existing.exists():
        cmd_blizzard = [
            FFMPEG, "-y", "-i", str(wind_existing),
            "-filter_complex",
            "[0:a]treble=g=5:f=2500,flanger=delay=10:depth=5:speed=0.3,afade=t=in:ss=0:d=1.5,afade=t=out:st=13.0:d=2.0,aresample=48000[out]",
            "-map", "[out]", "-t", "15.0", "-c:a", "pcm_s16le", str(blizzard_path)
        ]
        render_audio(cmd_blizzard, blizzard_path, "Blizzard Mountain Cold Gale")
    else:
        cmd_blizzard = [
            FFMPEG, "-y",
            "-f", "lavfi", "-i", "anoisesrc=d=15.0:c=pink:r=48000,bandpass=f=800:w=500,volume=2.5",
            "-filter_complex", "[0:a]flanger=speed=0.4:depth=8,aresample=48000[out]",
            "-map", "[out]", "-c:a", "pcm_s16le", str(blizzard_path)
        ]
        render_audio(cmd_blizzard, blizzard_path, "Blizzard Mountain Gale (Synthesized)")


def unpack_curated_cc0_packs():
    """Unpack Kenney CC0 RPG sounds into foley/kenney/."""
    print("\n--- 4. Unpacking Kenney CC0 Foley & Weapons ---")
    kenney_url = "https://opengameart.org/sites/default/files/RPGsounds_Kenney.zip"
    kenney_dir = FOLEY_DIR / "kenney"
    download_and_extract_zip(kenney_url, kenney_dir, prefix="kenney")


def index_and_hydrate_sound_bank():
    """Index all sounds into `sound_catalog` and `sound_assets` tables with semantic synonyms."""
    print("\n--- 5. Indexing & Harmonizing Sound Catalog & Sound Assets ---")
    from audiobook_factory.sound_bank import SoundBank
    from audiobook_factory.sound_bank_ingest import UniversalSoundBankIngester

    # 1. SoundBank indexing (sound_catalog & FTS)
    bank = SoundBank(bank_root=SOUND_BANK_DIR)
    stats_catalog = bank.scan_and_index()
    print(f"[+] Sound Catalog Indexed: {stats_catalog}")

    # 2. UniversalSoundBankIngester indexing (sound_assets & FTS with EBU R128 LUFS/Peak)
    print("[*] Ingesting into sound_assets with EBU R128 LUFS and True Peak DSP metrics...")
    ingester = UniversalSoundBankIngester(db_path=bank.db_path)
    res_ingest = ingester.ingest_directory(SOUND_BANK_DIR, recursive=True)
    print(f"[+] Sound Assets Ingested: {res_ingest['ingested']} indexed, {res_ingest['failed']} failed")

    # 3. Verification Spot-Check
    print("\n--- 6. Running Verification Spot-Checks ---")
    spot_queries = [
        "igni", "aard", "quen", "axii", "yrden",
        "striga", "ghoul", "wolf",
        "sword draw", "sword clash", "body thud", "armor clank",
        "crypt", "castle hall", "bog swamp", "blizzard"
    ]
    all_resolved = True
    for q in spot_queries:
        resolved = bank.resolve_sound(q)
        status = "✅ PASS" if (resolved and resolved.exists()) else "❌ FAIL"
        if not (resolved and resolved.exists()):
            all_resolved = False
        print(f"  [{status}] Query: '{q:15}' -> {resolved.name if resolved else 'None'}")

    return all_resolved


def main():
    print("=" * 80)
    print("🎬 AUDIOBOOK FACTORY: FANTASY SOUND PACK HYDRATION & ACOUSTIC HARMONIZATION")
    print("=" * 80)

    unpack_curated_cc0_packs()
    build_witcher_signs()
    build_monster_and_combat_assets()
    build_fantasy_ambiences()
    success = index_and_hydrate_sound_bank()

    print("\n" + "=" * 80)
    if success:
        print("🎉 ALL FANTASY SOUNDS HYDRATED, STANDARDIZED & VERIFIED!")
    else:
        print("⚠️ SOME QUERIES COULD NOT BE RESOLVED. CHECK LOGS ABOVE.")
    print("=" * 80)


if __name__ == "__main__":
    main()
