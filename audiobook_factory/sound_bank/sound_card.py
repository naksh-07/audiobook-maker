#!/usr/bin/env python3
"""
Audiobook Factory - Sound Bank Agent Sound Card Formatter.
Constructs high-density textual cards allowing LLM creative director agents
to reason about physical, acoustic, dramatic, and mix properties without listening.
"""

from __future__ import annotations
from typing import Any, Dict


class SoundCardMixin:
    """Agent Sound Card formatting and extraction mixin for SoundBank."""

    def format_agent_sound_card(self, candidate_or_id: Any) -> str:
        """
        Formats an explainable Agent Sound Card from a candidate dictionary, asset ID, or AgentSoundCard.
        """
        if hasattr(candidate_or_id, "to_agent_markdown"):
            return candidate_or_id.to_agent_markdown()

        if isinstance(candidate_or_id, int):
            return self.get_agent_sound_card(candidate_or_id)

        cand = candidate_or_id
        aid = cand.get("id", 0)
        fname = cand.get("filename", "")
        title = cand.get("title") or fname
        cat = cand.get("category", "SFX")
        subcat = cand.get("subcategory", "General")
        dur = float(cand.get("duration_sec") or 0.0)
        status = "LOCAL (Cached)" if cand.get("is_downloaded") else "VIRTUAL (JIT Ready)"

        exc = cand.get("exciter") or "unspecified"
        res = cand.get("resonator") or "unspecified"
        act = cand.get("action_type") or "unspecified"
        surf = cand.get("surface") or "unspecified"

        lufs = cand.get("integrated_lufs") or cand.get("dsp_lufs") or -23.0
        peak = cand.get("true_peak_db") or cand.get("dsp_peak") or -1.5
        w_style = cand.get("wave_style") or "general"
        d_role = cand.get("dramatic_role") or "general"
        fg_str = float(cand.get("foreground_strength") or 0.5)

        v_risk = cand.get("voice_masking_risk") or "LOW"
        w_compat = float(cand.get("whisper_compatibility") or 0.5)
        duck_db = -16.0 if v_risk == "SEVERE" else (-12.0 if v_risk == "MODERATE" else -6.0)

        why_matched = cand.get("why_matched") or []
        why_str = ""
        if why_matched:
            why_lines = "\n  - " + "\n  - ".join(why_matched)
            why_str = f"\n- **Why Matched**:{why_lines}"

        card = (
            f"### 🎵 Sound Asset Card: [{cat}] {title} (ID: {aid})\n"
            f"- **File / Source**: `{fname}` | {cand.get('source_collection') or 'SoundBank'} ({cand.get('license', 'Royalty-Free')})\n"
            f"- **Duration**: {dur:.2f}s | **Status**: {status}\n"
            f"- **Sonic Genome**:\n"
            f"  - Exciter: `{exc}` | Resonator: `{res}`\n"
            f"  - Action: `{act}` | Surface: `{surf}`\n"
            f"  - Acoustic: `{w_style}` | LUFS: {lufs:.1f} | True Peak: {peak:.1f} dBTP\n"
            f"  - Dramatic: `{d_role}` | Foreground Strength: {fg_str:.2f}\n"
            f"  - Voice Masking Risk: `{v_risk}` (Whisper Safe: {w_compat:.2f})\n"
            f"- **Mix Recommendation**: Ducking {duck_db:.0f} dB"
            f"{why_str}"
        )
        return card

    def get_agent_sound_card(self, asset_id: int) -> str:
        """
        Formats a compact, high-density Agent Sound Card for any asset in the catalog.
        Allows the AI creative director to reason about sounds without listening to audio.
        """
        with self._get_conn() as conn:
            cur = conn.execute("""
                SELECT c.*,
                       a.integrated_lufs as dsp_lufs,
                       a.true_peak_db as dsp_peak,
                       a.spectral_centroid_hz as dsp_centroid
                FROM sound_catalog c
                LEFT JOIN sound_assets a ON (a.filepath = c.filepath OR a.filename = c.filename)
                WHERE c.id = ?
            """, (asset_id,))
            row = cur.fetchone()
            if not row:
                return f"[Sound Card] Asset ID {asset_id} not found in catalog."
            cand = dict(row)

        aid = cand["id"]
        fname = cand["filename"]
        title = cand.get("title") or fname
        cat = cand.get("category", "SFX")
        subcat = cand.get("subcategory", "General")
        dur = float(cand.get("duration_sec") or 0.0)
        status = "LOCAL (Cached)" if cand.get("is_downloaded") else "VIRTUAL (JIT Ready)"

        exc = cand.get("exciter") or "unspecified"
        res = cand.get("resonator") or "unspecified"
        act = cand.get("action_type") or "unspecified"
        surf = cand.get("surface") or "unspecified"

        lufs = cand.get("dsp_lufs") or -23.0
        peak = cand.get("dsp_peak") or -1.5
        w_style = cand.get("wave_style") or "general"
        d_role = cand.get("dramatic_role") or "general"
        fg_str = float(cand.get("foreground_strength") or 0.5)

        v_risk = cand.get("voice_masking_risk") or "LOW"
        w_compat = float(cand.get("whisper_compatibility") or 0.5)
        duck_db = -16.0 if v_risk == "SEVERE" else (-12.0 if v_risk == "MODERATE" else -6.0)

        card = (
            f"=== AGENT SOUND CARD: [ID: {aid}] {title} ===\n"
            f"TYPE:      {cat} / {subcat} | Status: {status} ({dur:.2f}s)\n"
            f"PHYSICAL:  exciter: {exc} | resonator: {res} | action: {act} | surface: {surf}\n"
            f"ACOUSTIC:  wave_style: {w_style} | LUFS: {lufs:.1f} | Peak: {peak:.1f} dBTP\n"
            f"DRAMATIC:  role: {d_role} | foreground_strength: {fg_str:.2f} | mood: {cand.get('mood', 'default')}\n"
            f"MIX:       voice_masking: {v_risk} | whisper_compat: {w_compat:.2f} | rec_ducking: {duck_db:.0f}dB\n"
            f"BEST USE:  {cand.get('description') or cand.get('tags') or 'dramatic underscore & action'}\n"
            f"AVOID:     {'whispered dialogue' if w_compat < 0.4 else 'dense overlapping dialogue' if v_risk == 'SEVERE' else 'none'}\n"
            f"SOURCE:    {cand.get('source_collection') or 'SoundBank'} ({cand.get('license', 'Royalty-Free')})"
        )
        return card

    def get_agent_sound_card_v3(self, sound_id: int) -> Any:
        """
        Retrieves the typed Phase 3 AgentSoundCard with full epistemic transparency.
        """
        from audiobook_factory.sonic_intelligence_engine import SonicIntelligenceEngine
        engine = SonicIntelligenceEngine(sound_bank=self)
        return engine.get_sound_card(sound_id)
