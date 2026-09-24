import sys
import json
import base64
import wave
import subprocess
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from audiobook_factory.key_manager import get_persistent_key_pool
from audiobook_factory.mastering import get_ffmpeg

pool = get_persistent_key_pool()
output_dir = REPO_ROOT / "audiobooks" / "output"
output_dir.mkdir(parents=True, exist_ok=True)
chunk_dir = output_dir / "tavern_demo_chunks"
chunk_dir.mkdir(parents=True, exist_ok=True)

# The screenplay provided by user
segments = [
    {
        "index": 1,
        "speaker": "Narrator",
        "voice": "Aoede",
        "text": "[low, raspy] सराय के भीतर बासी शराब, सीलन भरे ऊन और जम चुकी ठंडी हिंसा की एक ज़हरीली बू फैली थी। कोने के अंधेरे में गेराल्ट चुपचाप बैठा था...",
        "pan": 0.0,
        "pause_after_ms": 500,
    },
    {
        "index": 2,
        "speaker": "Thug Leader",
        "voice": "Puck",
        "text": "[spits, aggressive] ऐ सफेद बाल वाले! बहुत गर्मी है क्या तेरे खून में? अपनी ये लोहे की छड़ नीचे रख, वरना यहीं गांड चीर देंगे तेरी!",
        "pan": -0.5,
        "pause_after_ms": 300,
    },
    {
        "index": 3,
        "type": "action",
        "speaker": "Foley",
        "text": "[knife_drawn]",
        "foley_asset": REPO_ROOT / "audiobooks" / "sound_bank" / "foley" / "OGG" / "knifeSlice.ogg",
        "pan": 0.0,
        "pause_after_ms": 600,
    },
    {
        "index": 4,
        "speaker": "Geralt",
        "voice": "Charon",
        "text": "[growl] हूँ... [cold menace] बकवास बंद करो और दफ़ा हो जाओ, वरना पहली चीख निकलने का भी मौका नहीं मिलेगा।",
        "pan": 0.0,
        "pause_after_ms": 1200,
    },
]

def synthesize_voice(text, voice, out_file):
    models = ["gemini-3.8-flash-tts", "gemini-3.1-flash-tts-preview"]
    payload = {
        "contents": [{"parts": [{"text": text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}
        },
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
        ]
    }
    data = json.dumps(payload).encode("utf-8")
    
    for model in models:
        for attempt in range(3):
            k = pool.get_key("tts")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={k}"
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=25.0) as resp:
                    res = json.loads(resp.read().decode("utf-8"))
                    cand = res.get("candidates", [{}])[0]
                    parts = cand.get("content", {}).get("parts", [])
                    b64 = None
                    for p in parts:
                        if "inlineData" in p:
                            b64 = p["inlineData"]["data"]
                            break
                    if not b64:
                        raise ValueError(f"No audio data: {res}")
                    raw_pcm = base64.b64decode(b64)
                    
                    with wave.open(str(out_file), "wb") as wf:
                        wf.setnchannels(1)
                        wf.setsampwidth(2)
                        wf.setframerate(24000)
                        wf.writeframes(raw_pcm)
                    
                    dur = (len(raw_pcm) / 2) / 24000.0
                    return out_file, dur, model
            except Exception as e:
                print(f"    [!] {model} attempt {attempt+1} failed on key ...{k[-6:]}: {e}", flush=True)
                continue
    raise RuntimeError(f"Failed to synthesize voice for text: {text}")

print("[*] Synthesizing Multi-Cast Screenplay Segments with Gemini 3.8 Flash TTS...\n", flush=True)

rendered_tracks = []
ffmpeg = get_ffmpeg()

for seg in segments:
    idx = seg["index"]
    speaker = seg["speaker"]
    pan = seg.get("pan", 0.0)
    pause_ms = seg.get("pause_after_ms", 500)
    
    if seg.get("type") == "action":
        foley_src = seg.get("foley_asset")
        staged_wav = chunk_dir / f"seg_{idx:02d}_foley.wav"
        # Convert foley to 48kHz stereo with pause padding
        pad_sec = pause_ms / 1000.0
        cmd = [
            ffmpeg, "-y", "-i", str(foley_src),
            "-af", f"aresample=48000,apad=pad_dur={pad_sec:.3f},volume=-4dB",
            "-c:a", "pcm_s16le", str(staged_wav)
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        rendered_tracks.append(staged_wav)
        print(f"  [+] Seg {idx} | Foley: knifeSlice -> {staged_wav.name}", flush=True)
    else:
        text = seg["text"]
        voice = seg["voice"]
        raw_wav = chunk_dir / f"seg_{idx:02d}_{speaker}_{voice}_raw.wav"
        out_wav, dur, used_model = synthesize_voice(text, voice, raw_wav)
        print(f"  [+] Seg {idx} | {speaker} ({voice}) via {used_model} ({dur:.2f}s)", flush=True)
        
        # Apply Spatial Pan, Voice-specific EQ, and Pause Padding
        staged_wav = chunk_dir / f"seg_{idx:02d}_{speaker}_staged.wav"
        pad_sec = pause_ms / 1000.0
        
        af_filters = ["aresample=48000"]
        if pan != 0.0:
            # Stereo pan using pan filter
            left_gain = max(0.0, min(1.0, 0.5 * (1.0 - pan)))
            right_gain = max(0.0, min(1.0, 0.5 * (1.0 + pan)))
            af_filters.append(f"pan=stereo|c0={left_gain:.2f}*c0|c1={right_gain:.2f}*c0")
        else:
            af_filters.append("pan=stereo|c0=c0|c1=c0")
            
        if speaker == "Geralt":
            # Add warm sub-body & presence to Geralt's growl
            af_filters.append("equalizer=f=120:t=q:w=1.2:g=3.0,equalizer=f=3200:t=q:w=1.4:g=1.5")
        elif speaker == "Thug Leader":
            # High-mid aggressive bite
            af_filters.append("equalizer=f=2400:t=q:w=1.2:g=2.5")
            
        af_filters.append(f"apad=pad_dur={pad_sec:.3f}")
        
        cmd = [
            ffmpeg, "-y", "-i", str(raw_wav),
            "-af", ",".join(af_filters),
            "-c:a", "pcm_s16le", str(staged_wav)
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        rendered_tracks.append(staged_wav)

# Concatenate speech & Foley tracks
concat_list = chunk_dir / "concat_list.txt"
with open(concat_list, "w", encoding="utf-8") as f:
    for trk in rendered_tracks:
        f.write(f"file '{trk.resolve().as_posix()}'\n")

speech_track = chunk_dir / "speech_and_foley_assembled.wav"
cmd_concat = [
    ffmpeg, "-y", "-f", "concat", "-safe", "0",
    "-i", str(concat_list),
    "-c:a", "pcm_s16le", str(speech_track)
]
subprocess.run(cmd_concat, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

# Get speech duration
with wave.open(str(speech_track), "rb") as wf:
    total_speech_dur = wf.getnframes() / float(wf.getframerate())

print(f"\n[*] Assembled vocal & action track: {total_speech_dur:.2f}s", flush=True)

# Add subtle atmospheric tavern bed with ducking
amb_asset = REPO_ROOT / "audiobooks" / "sound_bank" / "ambience" / "tavern_crowd_murmur.ogg"
final_master_wav = output_dir / "geralt_tavern_standoff_master.wav"
final_master_m4a = output_dir / "geralt_tavern_standoff_master.m4a"

print("[*] Mixing Tavern Ambience Bed and Mastering to Broadcast EBU R128 (-19 LUFS)...", flush=True)

# Complex filter: mix speech (input 0) with background ambience (input 1 looped, ducked to -28dB with formant carve)
filter_graph = (
    f"[1:a]aloop=loop=-1:size=2e+09,atrim=0:{total_speech_dur:.2f},"
    f"aresample=48000,volume=-27dB,equalizer=f=2500:t=q:w=1.5:g=-6.0[amb];"
    f"[0:a][amb]amix=inputs=2:duration=first:dropout_transition=0.5,"
    f"loudnorm=I=-19.0:TP=-1.5:LRA=11.0[out]"
)

cmd_master_wav = [
    ffmpeg, "-y",
    "-i", str(speech_track),
    "-i", str(amb_asset),
    "-filter_complex", filter_graph,
    "-map", "[out]",
    "-c:a", "pcm_s16le",
    str(final_master_wav)
]
subprocess.run(cmd_master_wav, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

cmd_master_m4a = [
    ffmpeg, "-y",
    "-i", str(final_master_wav),
    "-c:a", "aac", "-b:a", "192k",
    str(final_master_m4a)
]
subprocess.run(cmd_master_m4a, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

print("\n[SUCCESS] Hollywood Audio Drama Demo Mastered!")
print(f"Master WAV: {final_master_wav} ({final_master_wav.stat().st_size:,} bytes)")
print(f"Master M4A: {final_master_m4a} ({final_master_m4a.stat().st_size:,} bytes)")
