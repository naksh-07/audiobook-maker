import json
import re
import urllib.request
import urllib.error
import os
import subprocess
import shutil
from typing import Optional
from audiobook_factory.logger import logger
from audiobook_factory.key_manager import get_persistent_key_pool
from audiobook_factory.cadence import get_stealth_sdk_headers

def get_ffmpeg() -> str:
    return shutil.which("ffmpeg") or "/usr/bin/ffmpeg"

def test_filter_graph(filter_complex: str, has_foley: bool = True) -> str:
    """Tool: Tests an FFmpeg filter graph for syntax errors using dummy audio."""
    ffmpeg = get_ffmpeg()
    if not os.path.exists(ffmpeg):
        return "ERROR: ffmpeg executable not found."

    # Validate stream references against available inputs
    if not has_foley and "[3:a]" in filter_complex:
        return "ERROR: Stream [3:a] does not exist because there are no Foley SFX cues in this chapter. Only [0:a] (Voice), [1:a] (BGM), and [2:a] (Ambience) are available."

    # Simulate inputs: voc_dry, bgm, amb_bed, (optional) fol_bus
    cmd = [
        ffmpeg, "-y",
        "-f", "lavfi", "-i", "sine=frequency=1000:duration=1",  # 0:a Voice
        "-f", "lavfi", "-i", "sine=frequency=400:duration=1",   # 1:a BGM
        "-f", "lavfi", "-i", "sine=frequency=300:duration=1",   # 2:a Ambience
    ]
    if has_foley or "[3:a]" in filter_complex:
        cmd.extend(["-f", "lavfi", "-i", "sine=frequency=200:duration=1"])  # 3:a Foley

    map_args = []
    if "[out]" in filter_complex:
        map_args = ["-map", "[out]"]
    else:
        labels = re.findall(r'\[([a-zA-Z0-9_]+)\]', filter_complex)
        if labels and labels[-1] not in ('0', '1', '2', '3', '0:a', '1:a', '2:a', '3:a'):
            map_args = ["-map", f"[{labels[-1]}]"]

    cmd.extend([
        "-filter_complex", filter_complex,
        *map_args,
        "-f", "null", "-"
    ])
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode == 0:
            return "SUCCESS: Filter graph syntax is valid."
        else:
            lines = [l for l in res.stderr.strip().split('\n') if l.strip()]
            return "ERROR: " + "\n".join(lines[-8:])
    except Exception as e:
        return f"ERROR: {str(e)}"

# Define Gemini Function Calling Schema
TOOLS = [{
    "functionDeclarations": [
        {
            "name": "test_filter_graph",
            "description": "Tests an FFmpeg filter_complex string for syntax errors before finalizing it. Always test your graph if you use complex routing.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "filter_complex": {
                        "type": "STRING",
                        "description": "The FFmpeg filter_complex string to test. E.g. '[0:a][1:a]amix=inputs=2[out]'"
                    }
                },
                "required": ["filter_complex"]
            }
        }
    ]
}]

def build_ffmpeg_filter_graph_via_agent(
    soundscape_plan: dict, 
    cue_sheet: dict, 
    vocal_dur: float, 
    has_foley: bool
) -> Optional[str]:
    """
    LLM-powered Audio Engineer Agent with Tool Use (Self-Healing).
    Interactively iterates with test_filter_graph until valid audio graph is achieved.
    """
    pool = get_persistent_key_pool()
    model = os.environ.get("GEMINI_TEXT_MODEL", "gemini-flash-lite-latest")
    
    scene_summary = [
        f"Scene {s.get('scene_id', s.get('id', '?'))}: Mood={s.get('emotional_arc', {}).get('music_mood', s.get('emotion', 'neutral'))}, Env={s.get('location', {}).get('environment_type', s.get('location', {}).get('environment', 'unknown'))}"
        for s in soundscape_plan.get("scenes", [])
    ]
    foley_summary = list(set([c.get("foley_tag") for c in cue_sheet.get("foley_cues", []) if c.get("foley_tag")]))
    
    sys_prompt = f"""You are an elite Audio Mixing Engineer Agent. 
You must output a robust FFmpeg filter_complex string to mix these streams:
- [0:a]: Voice (dry vocals)
- [1:a]: BGM (Music)
- [2:a]: Ambience Bed
{"- [3:a]: Foley SFX Bus" if has_foley else ""}

Environment: {", ".join(scene_summary) if scene_summary else "General"}
Foley: {", ".join(foley_summary) if foley_summary else "None"}
Chapter length: {vocal_dur:.2f}s

Rules:
1. Preserve voice clarity [0:a].
2. Apply sidechaincompress to BGM [1:a] against Voice [0:a].
3. Apply appropriate reverb/EQ to Ambience [2:a] based on the environment.
4. amix all inputs to a single output.
5. Apply aresample=48000, loudnorm=I=-19, alimiter outputting to [out].

You have a tool 'test_filter_graph'. Use it to test your filter string for syntax errors before finalizing.
Once tested and successful, output the final graph as a raw string in a markdown code block.
"""

    messages = [{"role": "user", "parts": [{"text": sys_prompt}]}]
    
    for attempt in range(5):
        api_key = pool.get_key(service="text")
        if not api_key:
            break
        
        payload = {
            "contents": messages,
            "tools": TOOLS,
            "generationConfig": {"temperature": 0.2}
        }
        
        req = urllib.request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}",
            data=json.dumps(payload).encode("utf-8"),
            headers=get_stealth_sdk_headers(api_key),
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=45.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                candidates = data.get("candidates", [])
                if not candidates:
                    logger.warning(f"  [!] Audio Engineer Agent: No candidates: {data.get('promptFeedback', {})}")
                    continue
                
                candidate = candidates[0]
                parts = candidate.get("content", {}).get("parts", [])
                if not parts:
                    continue
                
                # Check if model wants to call a tool
                call_part = next((p for p in parts if "functionCall" in p), None)
                if call_part:
                    call = call_part["functionCall"]
                    logger.info("  [*] Audio Agent testing filter graph...")
                    if call.get("name") == "test_filter_graph":
                        fc_to_test = call.get("args", {}).get("filter_complex", "")
                        test_res = test_filter_graph(fc_to_test, has_foley=has_foley)
                        first_line = test_res.splitlines()[0] if test_res.splitlines() else test_res
                        logger.info(f"      -> {first_line[:70]}")
                        
                        # Add model's call to history
                        messages.append({"role": "model", "parts": parts})
                        # Add tool response to history
                        messages.append({
                            "role": "user",
                            "parts": [{
                                "functionResponse": {
                                    "name": call["name"],
                                    "response": {"result": test_res}
                                }
                            }]
                        })
                        continue  # Loop to let model correct or finalize
                
                # If no function call, it's a text response (the final graph)
                text_parts = [p.get("text", "") for p in parts if "text" in p]
                if text_parts:
                    raw = "\n".join(text_parts).strip()
                    # Extract from markdown if present
                    match = re.search(r"```(?:[a-zA-Z0-9_-]+)?\s*\n?(.*?)```", raw, re.DOTALL)
                    if match:
                        final_graph = match.group(1).strip()
                    else:
                        final_graph = raw.strip()
                    
                    # Verify final graph
                    val_res = test_filter_graph(final_graph, has_foley=has_foley)
                    if val_res.startswith("SUCCESS"):
                        logger.info("  [+] Audio Engineer Agent finalized & verified FFmpeg graph.")
                        return final_graph
                    else:
                        logger.warning(f"  [!] Final graph failed validation: {val_res.splitlines()[0][:70]}")
                        messages.append({"role": "model", "parts": parts})
                        messages.append({
                            "role": "user",
                            "parts": [{
                                "text": f"The filter graph you provided has syntax errors:\n{val_res}\nPlease fix the errors and provide a valid FFmpeg filter graph in a markdown code block."
                            }]
                        })
                        continue
                        
        except urllib.error.HTTPError as e:
            if e.code == 429:
                pool.mark_temporary_backoff(api_key, 12.0, "RPM rate limit in ffmpeg_agent")
            logger.warning(f"  [!] Audio Engineer Agent HTTP {e.code}: {e}")
            continue
        except Exception as e:
            logger.warning(f"  [!] Audio Engineer Agent loop error: {e}")
            return None
    return None


def build_manifest_mastering_filter_graph_via_agent(
    manifest_data: dict,
    vocal_dur: float,
    has_foley: bool = True,
    has_music: bool = True,
    has_ambience: bool = True,
) -> str:
    """
    Agentic Audio Mixing & Mastering Engineer with Tool Use.
    The AI Agent designs and verifies the exact DSP filter complex graph
    specifically for the chapter's CreativeManifest.
    """
    pool = get_persistent_key_pool()
    model = os.environ.get("GEMINI_TEXT_MODEL", "gemini-flash-lite-latest")

    mastering = manifest_data.get("mastering", {})
    target_lufs = mastering.get("target_lufs", -19.0)
    true_peak = mastering.get("true_peak_db", -1.5)

    cues = manifest_data.get("music_cues", [])
    ambience = manifest_data.get("ambience_scenes", [])
    silence = manifest_data.get("silence_percentage", 70.0)

    cue_summary = [f"{c.get('cue_type')}: {c.get('track_name', '')}" for c in cues[:4]]
    amb_summary = [a.get("asset_name", "") for a in ambience[:2]]

    sys_prompt = f"""You are an elite Hollywood & BBC Audio Drama Mastering Engineer Agent.
Design the master FFmpeg filter_complex string to mix and master these stems:
- [0:a]: Lead Dialogue Bus (dry speech)
- [1:a]: Music Bus (surgical cues, {silence}% silence)
- [2:a]: Ambience Bed Bus ({', '.join(amb_summary) if amb_summary else 'room tone'})
{"- [3:a]: Foley SFX Bus (punchy transients)" if has_foley else ""}

Chapter Duration: {vocal_dur:.2f}s
Target Loudness: {target_lufs} LUFS Integrated, True Peak: {true_peak} dBTP
Music Cues: {', '.join(cue_summary) if cue_summary else 'Pure Silence'}

ACOUSTIC MIXING RULES:
1. Vocal Intelligibility: Split [0:a] into dry dialogue and sidechain trigger via asplit=2[voc_dry][voc_sc].
2. Dynamic Ducking: Carve [1:a] at 2200Hz (equalizer=f=2200:t=q:w=1.5:g=-5.5) and duck it with sidechaincompress against [voc_sc] (attack=80, release=650, ratio=6.0).
3. Ambience: Level [2:a] to sit transparently beneath speech.
{"4. Foley: Level [3:a] at unity gain (volume=1.0) so transients remain punchy." if has_foley else ""}
5. Mix: Combine with amix (duration=first:normalize=0 to strictly preserve vocal track duration and prevent volume division!).
6. Broadcast Mastering: EBU R128 loudnorm (I={target_lufs}:TP={true_peak}:LRA=7) and alimiter, outputting to [out].

Test your graph using the 'test_filter_graph' tool before finalizing.
Output the verified graph in a markdown code block."""

    messages = [{"role": "user", "parts": [{"text": sys_prompt}]}]

    for attempt in range(5):
        api_key = pool.get_key(service="text")
        if not api_key:
            break

        payload = {
            "contents": messages,
            "tools": TOOLS,
            "generationConfig": {"temperature": 0.2}
        }

        req = urllib.request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}",
            data=json.dumps(payload).encode("utf-8"),
            headers=get_stealth_sdk_headers(api_key),
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=40.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                candidates = data.get("candidates", [])
                if not candidates:
                    continue

                parts = candidates[0].get("content", {}).get("parts", [])
                call_part = next((p for p in parts if "functionCall" in p), None)
                if call_part:
                    call = call_part["functionCall"]
                    if call.get("name") == "test_filter_graph":
                        fc_to_test = call.get("args", {}).get("filter_complex", "")
                        test_res = test_filter_graph(fc_to_test, has_foley=has_foley)
                        logger.info(f"  [*] Audio Engineer Agent tested graph: {test_res.splitlines()[0][:60]}")
                        messages.append({"role": "model", "parts": parts})
                        messages.append({
                            "role": "user",
                            "parts": [{"functionResponse": {"name": call["name"], "response": {"result": test_res}}}]
                        })
                        continue

                text_parts = [p["text"] for p in parts if "text" in p]
                if text_parts:
                    raw = "\n".join(text_parts).strip()
                    match = re.search(r"```(?:[a-zA-Z0-9_-]+)?\s*\n?(.*?)```", raw, re.DOTALL)
                    final_graph = match.group(1).strip() if match else raw.strip()

                    val_res = test_filter_graph(final_graph, has_foley=has_foley)
                    if val_res.startswith("SUCCESS"):
                        logger.info("  [+] Audio Engineer Agent: Master filter graph verified & locked.")
                        return final_graph
                    else:
                        messages.append({"role": "model", "parts": parts})
                        messages.append({"role": "user", "parts": [{"text": f"Filter graph error: {val_res}\nPlease fix and output a valid graph."}]})
                        continue
        except urllib.error.HTTPError as e:
            if e.code == 429:
                pool.mark_temporary_backoff(api_key, 12.0)
            continue
        except Exception:
            continue

    # Fallback to standard 5-track broadcast recipe if agent loop exhausted
    logger.warning("  [!] Audio Engineer Agent API exhausted. Falling back to calibrated EBU R128 broadcast graph.")
    if has_foley:
        return (
            "[0:a]asplit=2[voc_dry][voc_sc];"
            "[1:a]equalizer=f=2200:t=q:w=1.5:g=-5.5[bgm_carved];"
            "[bgm_carved][voc_sc]sidechaincompress=threshold=0.03:ratio=6.0:attack=80:release=650:knee=2.0[bgm_ducked];"
            "[2:a]volume=0.85[amb_bed];"
            "[3:a]volume=1.0[fol_bus];"
            "[voc_dry][bgm_ducked][amb_bed][fol_bus]amix=inputs=4:duration=first:normalize=0:weights=1.0 1.0 1.0 1.0[mixed];"
            f"[mixed]aresample=osr=48000,loudnorm=I={target_lufs}:TP={true_peak}:LRA=7,alimiter=limit=0.89:attack=5:release=50[out]"
        )
    else:
        return (
            "[0:a]asplit=2[voc_dry][voc_sc];"
            "[1:a]equalizer=f=2200:t=q:w=1.5:g=-5.5[bgm_carved];"
            "[bgm_carved][voc_sc]sidechaincompress=threshold=0.03:ratio=6.0:attack=80:release=650:knee=2.0[bgm_ducked];"
            "[2:a]volume=0.85[amb_bed];"
            "[voc_dry][bgm_ducked][amb_bed]amix=inputs=3:duration=first:normalize=0:weights=1.0 1.0 1.0[mixed];"
            f"[mixed]aresample=osr=48000,loudnorm=I={target_lufs}:TP={true_peak}:LRA=7,alimiter=limit=0.89:attack=5:release=50[out]"
        )
