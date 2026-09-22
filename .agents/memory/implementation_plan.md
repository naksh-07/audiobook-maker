# [Implementation Plan] Audiobook Factory Agentic/MCP Refactor

## 🎯 Goal
Refactor `audiobook-maker` from a deterministic, rigid Python pipeline into an **Agentic / MCP-driven Architecture**. The core logic and decision-making will shift from Python dictionaries and regex hacks directly to LLM Agents, while retaining strict control over TTS model choices (Gemini 3.1 Flash only) and treating key exhaustion as a valid halting condition.

---

## 🛑 User Review Required
> [!IMPORTANT]  
> The plan proposes turning the Audio Engineering and Foley processes into an **FFmpeg MCP server** interaction. The Agent will dynamically generate filter graphs based on scene emotion. Does this align with the level of control you want, or would you prefer the agent to pick from a wider, dynamic set of presets instead of raw graph generation?

> [!NOTE]  
> As requested, **TTS Key Exhaustion is treated as a feature**. The pipeline will NOT attempt to fall back to smaller/inferior TTS models. It will cleanly checkpoint its state and sleep/exit until the Midnight PT rollover.

---

## 🛠️ Proposed Changes

### 1. The Orchestrator (Supervisor Agent)
Instead of a strict `for` loop executing functions linearly, the Orchestrator becomes an Agentic loop powered by an LLM with access to internal MCP Tools.

#### [MODIFY] [orchestrator.py](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/orchestrator.py)
- **Delete** the rigid sequence (`Translator -> ScriptBuilder -> FoleyMiner -> TTS -> Mastering`).
- **Implement** a `Supervisor Agent` loop that uses tools. 
- **Graceful Halt**: If the `TTS Dispatcher` raises `AllKeysExhaustedTodayError`, the Supervisor cleanly saves a progress checkpoint (e.g., `checkpoint.json`) and pauses execution, informing the user instead of throwing a fatal stack trace.

---

### 2. JSON Truncation Healing (Script & Translators)

#### [MODIFY] [script_builder.py](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/script_builder.py)
- **Delete** the regex-based JSON recovery (`repaired[:last_brace + 1] + "\n]"`).
- **Implement**: When a JSON decoding error occurs (due to `MAX_TOKENS` truncation), the tool will trigger a **"Data Healer"** LLM call. It will pass the truncated response back with the prompt: *"The JSON array was truncated mid-generation. Continue outputting valid JSON exactly from the last valid character."* 
- Merge the chunks natively in Python.

---

### 3. Foley & Audio Engineering (The FFmpeg MCP)

#### [MODIFY] [foley_miner.py](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/foley_miner.py)
- **Delete** the hardcoded `ACOUSTIC_PRESETS` (e.g., `"tavern_interior": "freeverb=roomsize=0.45"`).
- **Delete** the hardcoded keyword tags (`"sword_draw"`, `"door_creak"`).

#### [NEW] [audiobook_factory/ffmpeg_agent.py](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/ffmpeg_agent.py)
- Integrate or build a lightweight **FFmpeg MCP Server**.
- Give the LLM an `execute_ffmpeg_graph` tool. 
- The LLM acts as the **Audio Engineer**. It will read a scene (e.g., "A tense standoff in a hollow, dripping cave"), and autonomously design the `ffmpeg -filter_complex` graph to apply the exact reverb, lowpass EQ, and sidechain parameters needed, then execute it via the MCP tool.

---

### 4. Semantic Extraction
#### [MODIFY] [extractor.py](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/extractor.py)
- **Delete** arbitrary character-limit string splitting.
- **Implement** Semantic Chunking. An LLM reads ahead to find natural scene breaks or chapter boundaries and slices the text accordingly, ensuring context isn't severed awkwardly mid-sentence.

---

## ✅ Verification Plan

### Automated Tests
- Run `pytest tests/test_script_builder.py` with mock truncated JSON to ensure the LLM healing loop perfectly reconstructs the data.
- Run `pytest tests/test_ffmpeg_agent.py` to ensure the agent outputs syntactically valid FFmpeg filter graphs.

### Manual Verification
- Deliberately exhaust the key pool to verify that the Supervisor Agent catches the `AllKeysExhaustedTodayError`, checkpoints its state, and halts gracefully without crashing.
- Generate a sample scene using the new Audio Engineer Agent to ensure the dynamic FFmpeg graph sounds realistic compared to the old hardcoded presets.
