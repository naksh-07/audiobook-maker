#!/usr/bin/env python3
"""
Kokoro & Goonj-1-82M TTS Remote Client & Mobile Audio Runner.
Connects from Termux Mobile Companion to Laptop / PC Kokoro & Goonj Speech Server (RTX 4050 GPU).
Zero external pip dependencies (Pure Python 3 Standard Library + FFmpeg integration).
"""

import os
import sys
import json
import time
import shutil
import argparse
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

# Paths & Defaults
SCRIPT_DIR = Path(__file__).resolve().parent
ENV_FILE = SCRIPT_DIR / ".env"


def load_env(env_path: Path = ENV_FILE) -> dict:
    """Load key-value pairs from .env file into environment."""
    env_vars = {}
    if not env_path.exists():
        return env_vars

    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip("'\"")
                env_vars[key] = val
                if key not in os.environ:
                    os.environ[key] = val
    return env_vars


# Load config
load_env()

DEFAULT_API_URL = os.environ.get("KOKORO_API_URL", "http://10.236.21.128:8880").rstrip("/")
DEFAULT_VOICE = os.environ.get("KOKORO_DEFAULT_VOICE", "hi_meera")
DEFAULT_SPEED = float(os.environ.get("KOKORO_DEFAULT_SPEED", "1.0"))
DEFAULT_OUTPUT_DIR = Path(
    os.environ.get("AUDIO_OUTPUT_DIR", "/storage/emulated/0/Documents/Termux/Audio")
)
DEFAULT_AUTO_PLAY = os.environ.get("AUTO_PLAY", "false").lower() in ("true", "1", "yes")
DEFAULT_AUTO_MASTER = os.environ.get("AUTO_MASTER", "false").lower() in ("true", "1", "yes")

KNOWN_VOICES = {
    "hi_meera": {"gender": "Female", "lang": "Hindi", "desc": "Warm, natural Hindi speaker, highly expressive"},
    "hi_shivani": {"gender": "Female", "lang": "Hindi", "desc": "Clear, melodious standard Hindi accent"},
    "hi_atul": {"gender": "Male", "lang": "Hindi", "desc": "Deep, confident male Hindi narrator"},
    "hi_ravi": {"gender": "Male", "lang": "Hindi", "desc": "Conversational, friendly male Hindi voice"},
    "bed_hindi": {"gender": "Neutral", "lang": "Base Hindi", "desc": "Base phonetic Hindi foundational model voice"},
    "en_aman": {"gender": "Male", "lang": "Indian English", "desc": "Clear, modern Indian English tech narrator"},
    "en_ananya": {"gender": "Female", "lang": "Indian English", "desc": "Articulate, natural Indian English female speaker"},
    "en_arjun": {"gender": "Male", "lang": "Indian English", "desc": "Confident Indian English corporate/guide voice"},
    "en_dev": {"gender": "Male", "lang": "Indian English", "desc": "Casual Indian English conversational tone"},
    "en_divya": {"gender": "Female", "lang": "Indian English", "desc": "Gentle, polished Indian English speaker"},
    "en_kabir": {"gender": "Male", "lang": "Indian English", "desc": "Dynamic, energetic Indian English speaker"},
    "en_nisha": {"gender": "Female", "lang": "Indian English", "desc": "Clear conversational Indian English voice"},
    "en_priya": {"gender": "Female", "lang": "Indian English", "desc": "Expressive, bright Indian English voice"},
    "en_sameer": {"gender": "Male", "lang": "Indian English", "desc": "Rich, professional Indian English broadcaster"},
    "en_tara": {"gender": "Female", "lang": "Indian English", "desc": "Friendly storytelling Indian English voice"},
}


def get_server_health(api_url: str = DEFAULT_API_URL, timeout: float = 4.0) -> dict:
    """Detailed server status check and latency measurement via /health."""
    start_time = time.time()
    url = f"{api_url}/health"

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Antigravity-Kokoro-Client/2.0"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            latency_ms = round((time.time() - start_time) * 1000, 2)
            data = json.loads(resp.read().decode("utf-8"))
            data["reachable"] = True
            data["latency_ms"] = latency_ms
            data["api_url"] = api_url
            return data
    except Exception as e:
        latency_ms = round((time.time() - start_time) * 1000, 2)
        # Fallback ping check to root /
        try:
            req_root = urllib.request.Request(
                f"{api_url}/",
                headers={"User-Agent": "Antigravity-Kokoro-Client/2.0"},
                method="GET",
            )
            with urllib.request.urlopen(req_root, timeout=timeout) as resp:
                return {
                    "reachable": True,
                    "status": "online",
                    "model": "Kokoro & Goonj",
                    "latency_ms": round((time.time() - start_time) * 1000, 2),
                    "api_url": api_url,
                }
        except Exception:
            pass

        return {
            "reachable": False,
            "status": "offline",
            "api_url": api_url,
            "latency_ms": latency_ms,
            "error": str(e),
        }


def get_server_voices(api_url: str = DEFAULT_API_URL, timeout: float = 4.0) -> list:
    """Fetch live list of voices from server."""
    url = f"{api_url}/voices"
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Antigravity-Kokoro-Client/2.0"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("voices", [])
    except Exception:
        # Fallback to local known voices
        return [
            {"id": vid, "name": vid, "language": info["lang"]}
            for vid, info in KNOWN_VOICES.items()
        ]


def convert_wav_to_mp3(wav_path: Path, mp3_path: Path, bitrate: str = "192k") -> Path:
    """Convert WAV to MP3 using system FFmpeg."""
    ffmpeg_bin = shutil.which("ffmpeg") or "/usr/bin/ffmpeg"
    if not os.path.exists(ffmpeg_bin):
        print(f"[!] ffmpeg not found, retaining WAV format.")
        return wav_path

    cmd = [
        ffmpeg_bin,
        "-y",
        "-i",
        str(wav_path),
        "-c:a",
        "libmp3lame",
        "-b:a",
        bitrate,
        str(mp3_path),
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if wav_path.exists() and wav_path != mp3_path:
            try:
                wav_path.unlink()
            except OSError:
                pass
        return mp3_path
    except subprocess.CalledProcessError as e:
        print(f"[!] MP3 conversion failed: {e.stderr.decode('utf-8', errors='ignore')}")
        return wav_path


def apply_audio_master(input_path: Path) -> Path:
    """Run generated audio through audio-master CLI or FFmpeg studio chain."""
    master_bin = shutil.which("audio-master") or "/usr/local/bin/audio-master"
    if os.path.exists(master_bin):
        mastered_path = input_path.with_name(f"{input_path.stem}_mastered.mp3")
        cmd = [master_bin, str(input_path), "--output", str(mastered_path), "--loudnorm"]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return mastered_path
        except subprocess.CalledProcessError:
            pass

    # Direct FFmpeg fallback vocal chain
    ffmpeg_bin = shutil.which("ffmpeg") or "/usr/bin/ffmpeg"
    if not os.path.exists(ffmpeg_bin):
        return input_path

    mastered_path = input_path.with_name(f"{input_path.stem}_mastered.mp3")
    filter_chain = (
        "highpass=f=60,afftdn=nr=8:nf=-35,deesser=i=0.35:m=0.5:f=0.5,"
        "lowpass=f=10500,aresample=resampler=soxr:osr=48000,"
        "loudnorm=I=-16:TP=-1.5:LRA=11"
    )
    cmd = [
        ffmpeg_bin,
        "-y",
        "-i",
        str(input_path),
        "-af",
        filter_chain,
        "-c:a",
        "libmp3lame",
        "-b:a",
        "192k",
        str(mastered_path),
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return mastered_path
    except Exception:
        return input_path


def play_audio(audio_path: Path) -> None:
    """Trigger native Android playback via Termux or ffplay."""
    player = shutil.which("termux-media-player")
    if player:
        print(f"[*] Playing audio via termux-media-player...")
        try:
            subprocess.run([player, "play", str(audio_path)], check=True)
            return
        except Exception as e:
            print(f"[!] termux-media-player error: {e}")

    ffplay = shutil.which("ffplay")
    if ffplay:
        print(f"[*] Playing audio via ffplay...")
        subprocess.run([ffplay, "-nodisp", "-autoexit", str(audio_path)], check=False)
        return

    print(f"[!] Audio saved: {audio_path}")


def synthesize_speech(
    text: str,
    voice: str = DEFAULT_VOICE,
    speed: float = DEFAULT_SPEED,
    api_url: str = DEFAULT_API_URL,
    audio_format: str = "mp3",
    output_path: Path | None = None,
    master: bool = False,
    play: bool = False,
) -> Path:
    """Send synthesis request to laptop Kokoro/Goonj API, process audio, and save."""
    if not text.strip():
        raise ValueError("Text to synthesize cannot be empty.")

    # Determine output path
    if output_path is None:
        if DEFAULT_OUTPUT_DIR.exists() and os.access(DEFAULT_OUTPUT_DIR, os.W_OK):
            target_dir = DEFAULT_OUTPUT_DIR
        else:
            target_dir = SCRIPT_DIR / "audio_out"
        target_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        target_ext = audio_format.lower().lstrip(".")
        output_path = target_dir / f"kokoro_{voice}_{timestamp}.{target_ext}"
    else:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

    endpoint = f"{api_url}/v1/audio/speech"
    payload = {
        "model": "kokoro",
        "input": text,
        "voice": voice,
        "speed": speed,
    }
    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        endpoint,
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Antigravity-Kokoro-Client/2.0",
        },
        method="POST",
    )

    print(f"[*] Request -> {endpoint}")
    print(f"[*] Voice: '{voice}', Speed: {speed}x, Format: {audio_format}")
    start_time = time.time()

    try:
        with urllib.request.urlopen(req, timeout=40.0) as resp:
            audio_bytes = resp.read()
    except urllib.error.HTTPError as e:
        err_content = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Server returned HTTP {e.code}: {err_content}")
    except Exception as e:
        raise ConnectionError(f"Failed to connect to Kokoro server at {api_url}: {e}")

    elapsed = round(time.time() - start_time, 2)
    raw_wav_path = output_path.with_suffix(".wav")
    with open(raw_wav_path, "wb") as f:
        f.write(audio_bytes)

    # Format conversion
    if audio_format.lower() == "mp3":
        final_path = convert_wav_to_mp3(raw_wav_path, output_path)
    else:
        final_path = raw_wav_path

    # Audio mastering if requested
    if master:
        final_path = apply_audio_master(final_path)

    size_kb = round(final_path.stat().st_size / 1024, 1)
    print(f"[+] Audio generated in {elapsed}s ({size_kb} KB) -> {final_path}")

    # Playback
    if play:
        play_audio(final_path)

    return final_path


def main():
    parser = argparse.ArgumentParser(
        prog="kokoro-tts",
        description="Kokoro & Goonj-1-82M TTS Mobile Client (Laptop RTX 4050 Offload)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # ping / status
    status_parser = subparsers.add_parser("status", aliases=["ping", "health"], help="Check server health & GPU status")
    status_parser.add_argument("--url", default=DEFAULT_API_URL, help="Server base URL")

    # voices
    voices_parser = subparsers.add_parser("voices", aliases=["list-voices"], help="List available Goonj & Kokoro voices")
    voices_parser.add_argument("--url", default=DEFAULT_API_URL, help="Server base URL")

    # speak
    speak_parser = subparsers.add_parser("speak", help="Synthesize speech from text")
    speak_parser.add_argument("text", type=str, help="Text to synthesize (Hindi, Hinglish, or English)")
    speak_parser.add_argument("--voice", "-v", default=DEFAULT_VOICE, help=f"Voice name (default: {DEFAULT_VOICE})")
    speak_parser.add_argument("--speed", "-s", type=float, default=DEFAULT_SPEED, help="Speech speed (0.5 to 2.0)")
    speak_parser.add_argument("--url", default=DEFAULT_API_URL, help="Server base URL")
    speak_parser.add_argument("--format", "-f", default="mp3", choices=["mp3", "wav"], help="Audio output format (default: mp3)")
    speak_parser.add_argument("--output", "-o", type=Path, default=None, help="Custom output file path")
    speak_parser.add_argument("--master", "-m", action="store_true", default=DEFAULT_AUTO_MASTER, help="Apply 48kHz studio mastering chain")
    speak_parser.add_argument("--play", "-p", action="store_true", default=DEFAULT_AUTO_PLAY, help="Play audio immediately on phone")

    # set-url
    url_parser = subparsers.add_parser("set-url", help="Update laptop server URL in .env")
    url_parser.add_argument("url", type=str, help="Server URL (e.g. http://10.236.21.128:8880)")

    # Direct shorthand handling if first arg is text rather than subcommand
    raw_args = sys.argv[1:]
    if raw_args and raw_args[0] not in [
        "status", "ping", "health", "voices", "list-voices", "speak", "set-url", "-h", "--help"
    ] and not raw_args[0].startswith("-"):
        raw_args = ["speak"] + raw_args

    args = parser.parse_args(raw_args)

    if not args.command or args.command in ["status", "ping", "health"]:
        url = getattr(args, "url", DEFAULT_API_URL)
        print(f"Connecting to Kokoro & Goonj Speech Server at: {url}")
        h = get_server_health(url)
        if h.get("reachable"):
            print(f"[OK] Server Status: ONLINE")
            print(f"     Model:        {h.get('model', 'Goonj-1-82M / Kokoro')}")
            print(f"     Device:       {h.get('device', 'CUDA').upper()} ({h.get('gpu_name', 'NVIDIA GPU')})")
            print(f"     Voices:       {h.get('voices_loaded', len(h.get('available_voices', [])))} loaded")
            print(f"     Latency:      {h.get('latency_ms')} ms")
        else:
            print(f"[FAIL] Server unreachable at {url}: {h.get('error')}")
            print("       Make sure laptop is awake and server.py is running on PC.")
    elif args.command in ["voices", "list-voices"]:
        url = getattr(args, "url", DEFAULT_API_URL)
        voices = get_server_voices(url)
        print(f"\nAvailable Voices on {url}:")
        print("=" * 65)
        print(f"{'Voice ID':<15} | {'Language':<16} | {'Details'}")
        print("-" * 65)
        for v in voices:
            vid = v.get("id", v.get("name", ""))
            lang = v.get("language", "Multilingual")
            info = KNOWN_VOICES.get(vid, {})
            desc = info.get("desc", f"{info.get('gender', '')} voice")
            print(f"{vid:<15} | {lang:<16} | {desc}")
        print("=" * 65)
        print(f"Default voice: '{DEFAULT_VOICE}' (modify in .env or via -v)")
    elif args.command == "set-url":
        clean_url = args.url.strip().rstrip("/")
        if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
            clean_url = f"http://{clean_url}"

        lines = []
        replaced = False
        if ENV_FILE.exists():
            with open(ENV_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("KOKORO_API_URL="):
                        lines.append(f"KOKORO_API_URL={clean_url}\n")
                        replaced = True
                    else:
                        lines.append(line)
        if not replaced:
            lines.append(f"KOKORO_API_URL={clean_url}\n")

        with open(ENV_FILE, "w", encoding="utf-8") as f:
            f.writelines(lines)
        print(f"[+] Updated KOKORO_API_URL in .env to: {clean_url}")
        h = get_server_health(clean_url)
        if h.get("reachable"):
            print(f"[OK] Connection verified! ({h.get('latency_ms')}ms)")
        else:
            print(f"[!] Server is currently unreachable at {clean_url}")
    elif args.command == "speak":
        try:
            out_file = synthesize_speech(
                text=args.text,
                voice=args.voice,
                speed=args.speed,
                api_url=args.url,
                audio_format=args.format,
                output_path=args.output,
                master=args.master,
                play=args.play,
            )
            print(f"[SUCCESS] Audio saved to: {out_file}")
        except Exception as e:
            print(f"[ERROR] Synthesis failed: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
