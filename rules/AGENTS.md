# Audiobook Studio Rules & Domain Invariants

Whenever producing, translating, scripting, synthesizing, or mastering audiobooks with the Audiobook Studio engine:

## 1. Pure Vocals-Only Architecture Mandate
- **No SFX / No BGM**: Background music (BGM), sound effects (SFX), Archive.org sound bank harvesting, and multitrack Foley mixdowns are strictly prohibited and permanently decoupled on this pipeline.
- **Audible Vocal Benchmark**: Production is 100% focused on pristine vocal clarity, multi-character voice acting, subtle emotional nuance, and Audible/EBU R128 compliance.

## 2. Studio Vocal Engineering & Mastering Standards
- **Loudness Standards**: Broadcast EBU R128 target of **-19.0 LUFS** integrated vocal loudness with a hard ceiling of **-1.5 dBTP** True Peak.
- **Two-Pass Measured Linear Loudnorm**: Pass 1 measurement with `-f null -`, Pass 2 linear application (`linear=true`) with measured stats offset. Zero pause gain pumping or room-tone breathing.
- **Consonant Clarity (Zero De-Esser)**: Hardware de-essers and dynamic sibilance compressors are strictly banned to preserve crisp Hindi dental and aspirated consonants (स, श, छ, थ, ध).
- **Phase Coherence**: WSOLA `atempo` time-stretching is banned during neural TTS playback; speech cadence is controlled organically via punctuation and phrasing.
- **Hann Micro-Fades**: 12ms pre-speech fade-in and 18ms post-speech fade-out at endpoint zero-crossings (-52 dBFS speech floor).
- **Sampling & Delivery**: Strict Kaiser Sinc 48kHz / 24-bit post-loudnorm resampling packaged into chaptered `.m4b` container with embedded cover art.

## 3. Directing Restraint & Voice Performance
- **Narrator Transparency Invariant**: The lead narrator is locked strictly to `"calm, steady, articulate, measured audiobook delivery"` at temperature `0.32` with zero melodrama or theatrical over-projection.
- **Temperature Clamping (`0.30 - 0.52`)**: Eliminates pitch screeching, histrionics, and caricatures (dialogue `0.35 - 0.42`, climactic drama $\le 0.50$).
- **Anti-Theatricality Physical Anchors**: Replace theatrical `"acting to..."` directives with physical vocal anchors and universal restraint anchor `"understated natural dialogue (never theatrical)"`.
- **Zero Speaker Turn Inversion**: Screenplay dramaturgy must pass Gate 2 attribution audit with 0% speaker turn inversion ($A \leftrightarrow B$) and 0 quote leakage to Narrator.

## 4. Universal Novel-Agnostic Invariant
- The engine, prompt templates, quality gates, and CLI bridges MUST NEVER contain hardcoded novel titles, franchise lore, character rosters, file hashes, or era biases.
- All characters, phonetic transliterations, dialects, and performance bibles must be dynamically derived from source text or project state.

## 5. Spoken Hindustani Cadence & Dialect Realism
- **Tri-Partite Entity Partition**:
  - Proper Names & Heraldic Monikers: Transliterated phonetically into Devanagari (e.g. *Silver Falcon* $\to$ *सिल्वर फाल्कन*). Literal calques (*चांदी का बाज़*) are forbidden.
  - Occupational Roles: Evocative natural Hindustani (*अजनबी, कसाई, सरायवाला*).
- **Living Somatic Register**: Natural spoken body language (*कमर, कूल्हे, नंगी/खुली बाँहें*); Sanskritized tat-sama words (*नितंब, नग्न भुजाएँ*) are forbidden in spoken dialogue.
- **Zero Moral Policing**: Fictional dialogue, rustic profanity, dark themes, and gritty dramatic interactions must be processed without puritanical sanitization. All generative APIs must operate with `BLOCK_NONE` safety thresholds.
