#!/usr/bin/env python3
"""
Kokoro TTS Remote Client & Mobile Test Runner.
Connects from Termux Mobile Companion to Laptop / PC Kokoro TTS Server.
Zero external pip dependencies (Pure Python 3 Standard Library).
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

# Defaults & Environment Paths
ENV_FILE = Path(__file__).resolve().parent / ".env"


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

DEFAULT_API_URL = os.environ.get("KOKORO_API_URL", "http://127.0.0.1:8880").rstrip("/")
DEFAULT_VOICE = os.environ.get("KOKORO_DEFAULT_VOICE", "af_heart")
DEFAULT_SPEED = float(os.environ.get("KOKORO_DEFAULT_SPEED", "1.0"))
DEFAULT_OUTPUT_DIR = Path(
    os.environ.get("AUDIO_OUTPUT_DIR", "/storage/emulated/0/Documents/Termux/Audio")
)
DEFAULT_AUTO_PLAY = os.environ.get("AUTO_PLAY", "false").lower() in ("true", "1", "yes")
DEFAULT_AUTO_MASTER = os.environ.get("AUTO_MASTER", "false").lower() in ("true", "1", "yes")


def check_server(api_url: str = DEFAULT_API_URL, timeout: float = 3.0) -> bool:
    """Ping remote Kokoro TTS server health endpoint."""
    endpoints = [
        f"{api_url}/health",
        f"{api_url}/v1/models",
        f"{api_url}/",
        f"{api_url}/docs",
    ]

    for url in endpoints:
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Antigravity-Kokoro-Client/1.0"},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status in (200, 204, 301, 302):
                    return True
        except (urllib.error.URLError, TimeoutError, ConnectionRefusedError, OSError):
            continue

    return False


def get_server_status(api_url: str = DEFAULT_API_URL) -> dict:
    """Detailed server status check and latency measurement."""
    start_time = time.time()
    reachable = False
    status_code = None
    response_body = ""

    test_url = f"{api_url}/v1/models"
    try:
        req = urllib.request.Request(
            test_url,
            headers={"User-Agent": "Antigravity-Kokoro-Client/1.0"},
        )
        with urllib.request.urlopen(req, timeout=4.0) as resp:
            latency_ms = round((time.time() - start_time) * 1000, 2)
            status_code = resp.status
            reachable = True
            response_body = resp.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as e:
        latency_ms = round((time.time() - start_time) * 1000, 2)
        status_code = e.code
        reachable = True  # Server responded even if 404/405
    except Exception as e:
        latency_ms = round((time.time() - start_time) * 1000, 2)
        return {
            "reachable": False,
            "api_url": api_url,
            "latency_ms": latency_ms,
            "error": str(e),
        }

    return {
        "reachable": reachable,
        "api_url": api_url,
        "status_code": status_code,
        "latency_ms": latency_ms,
        "response_preview": response_body[:200] if response_body else "",
    }


def synthesize_speech(
    text: str,
    voice: str = DEFAULT_VOICE,
    speed: float = DEFAULT_SPEED,
    api_url: str = DEFAULT_API_URL,
    audio_format: str = "wav",
    output_path: Path | None = None,
    master: bool = False,
    play: bool = False,
) -> Path:
    """Send synthesis request to laptop Kokoro API, save audio file, and optionally master/play."""
    if not text.strip():
        raise ValueError("Text to synthesize cannot be empty.")

    # Target output file
    if output_path is None:
        if DEFAULT_OUTPUT_DIR.exists() and os.access(DEFAULT_OUTPUT_DIR, os.W_OK):
            target_dir = DEFAULT_OUTPUT_DIR
        else:
            target_dir = Path(__file__).resolve().parent / "audio_out"
        target_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_path = target_dir / f"kokoro_{voice}_{timestamp}.{audio_format}"

    # OpenAI-compatible /v1/audio/speech payload
    endpoint = f"{api_url}/v1/audio/speech"
    payload = {
        "model": "kokoro",
        "input": text,
        "voice": voice,
        "speed": speed,
        "response_format": audio_format,
    }
    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        endpoint,
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Antigravity-Kokoro-Client/1.0",
        },
        method="POST",
    )

    print(f"[*] Sending TTS request to {endpoint}...")
    print(f"[*] Voice: '{voice}', Speed: {speed}, Format: {audio_format}")
    start_time = time.time()

    try:
        with urllib.request.urlopen(req, timeout=30.0) as resp:
            audio_bytes = resp.read()
    except urllib.error.HTTPError as e:
        err_content = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Server returned HTTP {e.code}: {err_content}")
    except Exception as e:
        raise ConnectionError(f"Failed to connect to Kokoro server at {api_url}: {e}")

    elapsed = round(time.time() - start_time, 2)
    with open(output_path, "wb") as f:
        f.write(audio_bytes)

    size_kb = round(len(audio_bytes) / 1024, 1)
    print(f"[+] Received {size_kb} KB audio in {elapsed}s -> {output_path}")

    # Optional mastering with audio-master
    if master:
        output_path = apply_audio_master(output_path)

    # Optional playback
    if play:
        play_audio(output_path)

    return output_path


def apply_audio_master(input_path: Path) -> Path:
    """Run generated audio through audio-master CLI (48kHz sinc resampler + EBU R128)."""
    master_bin = shutil.which("audio-master") or "/usr/local/bin/audio-master"
    if not os.path.exists(master_bin):
        print(f"[!] Warning: audio-master binary not found at {master_bin}, skipping mastering.")
        return input_path

    mastered_path = input_path.with_name(f"{input_path.stem}_mastered.wav")
    print(f"[*] Running audio mastering via {master_bin}...")
    cmd = [master_bin, str(input_path), "--output", str(mastered_path), "--loudnorm"]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"[+] Audio mastered successfully -> {mastered_path}")
        return mastered_path
    except subprocess.CalledProcessError as e:
        print(f"[!] Audio mastering failed: {e.stderr.decode('utf-8', errors='ignore')}")
        return input_path


def play_audio(audio_path: Path) -> None:
    """Trigger native Android playback via Termux."""
    player = shutil.which("termux-media-player")
    if player:
        print(f"[*] Playing audio via termux-media-player...")
        try:
            subprocess.run([player, "play", str(audio_path)], check=True)
            return
        except Exception as e:
            print(f"[!] termux-media-player error: {e}")

    # Fallback to ffplay or mpv if installed
    ffplay = shutil.which("ffplay")
    if ffplay:
        print(f"[*] Playing audio via ffplay...")
        subprocess.run([ffplay, "-nodisp", "-autoexit", str(audio_path)], check=False)
        return

    print(f"[!] No mobile audio player found. File saved at: {audio_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Kokoro TTS Mobile Client & Testing Harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Command: ping
    ping_parser = subparsers.add_parser("ping", help="Check laptop Kokoro server connection")
    ping_parser.add_argument("--url", default=DEFAULT_API_URL, help="Server base URL")

    # Command: speak
    speak_parser = subparsers.add_parser("speak", help="Synthesize text to speech")
    speak_parser.add_argument("text", type=str, help="Text to synthesize")
    speak_parser.add_argument("--voice", "-v", default=DEFAULT_VOICE, help="Voice name (default: af_heart)")
    speak_parser.add_argument("--speed", "-s", type=float, default=DEFAULT_SPEED, help="Speech speed (default: 1.0)")
    speak_parser.add_argument("--url", default=DEFAULT_API_URL, help="Server base URL")
    speak_parser.add_argument("--format", "-f", default="wav", choices=["wav", "mp3"], help="Audio format")
    speak_parser.add_argument("--output", "-o", type=Path, default=None, help="Output file path")
    speak_parser.add_argument("--master", action="store_true", default=DEFAULT_AUTO_MASTER, help="Apply audio-master filter chain")
    speak_parser.add_argument("--play", action="store_true", default=DEFAULT_AUTO_PLAY, help="Play audio immediately on mobile")

    # Command: set-url
    url_parser = subparsers.add_parser("set-url", help="Update laptop server address in .env")
    url_parser.add_argument("url", type=str, help="Laptop Kokoro server URL (e.g. http://192.168.1.50:8880)")

    args = parser.parse_args()

    if not args.command or args.command == "ping":
        url = getattr(args, "url", DEFAULT_API_URL)
        print(f"Checking Kokoro TTS server at: {url}")
        status = get_server_status(url)
        if status.get("reachable"):
            print(f"[OK] Server is REACHABLE (Latency: {status['latency_ms']}ms, HTTP {status.get('status_code')})")
        else:
            print(f"[WAIT] Server not reachable yet: {status.get('error', 'Connection failed')}")
            print(f"-> When Kokoro is running on your laptop, configure with:")
            print(f"   python3 kokoro_client.py set-url <LAPTOP_IP:PORT>")
    elif args.command == "set-url":
        clean_url = args.url.strip().rstrip("/")
        if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
            clean_url = f"http://{clean_url}"

        lines = []
        replaced = False
        if ENV_FILE.exists():
            with open(ENV_FILE, "r") as f:
                for line in f:
                    if line.startswith("KOKORO_API_URL="):
                        lines.append(f"KOKORO_API_URL={clean_url}\n")
                        replaced = True
                    else:
                        lines.append(line)
        if not replaced:
            lines.append(f"KOKORO_API_URL={clean_url}\n")

        with open(ENV_FILE, "w") as f:
            f.writelines(lines)
        print(f"[+] Updated KOKORO_API_URL in .env to: {clean_url}")
        # Test connection immediately
        status = get_server_status(clean_url)
        if status.get("reachable"):
            print(f"[OK] Connection verified! (Latency: {status['latency_ms']}ms)")
        else:
            print(f"[!] Note: Server at {clean_url} is currently offline or unreachable.")
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
            print(f"[DONE] Audio ready: {out_file}")
        except Exception as e:
            print(f"[ERROR] Synthesis failed: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
