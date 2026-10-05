import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from audiobook_factory.sound_bank import get_sound_bank, SoundAssetStagingError
from audiobook_factory.contracts import CreativeManifest, FoleyCue, MusicCue, AmbienceScene
from audiobook_factory.director.multi_agent_director import MultiAgentDirector
from audiobook_factory.director.agents.micro_foley_agent import MicroFoleyAgent
from audiobook_factory.director.agents.music_supervisor_agent import MusicSupervisorAgent
from audiobook_factory.director.agents.showrunner_agent import ShowrunnerPlan, ActDefinition


class TestDownloadOnDemandAndStaging:
    """Rigorous verification suite for Stage 4.5 Staging Gate and Semantic-First Retrieval."""

    def test_01_strict_semantic_ranking_eliminates_irrelevant_local_matches(self):
        """Verify that FTS5 BM25 match quality strictly dominates and handsaws never beat footsteps."""
        bank = get_sound_bank()
        results = bank.search("footsteps wood", category="FOL", limit=5)
        assert len(results) > 0

        top = results[0]
        # Top match MUST be a footstep asset, NEVER handsaw or sword clash
        assert "saw" not in top["filename"].lower()
        assert "sword" not in top["filename"].lower()
        subcat = (top.get("subcategory") or "").lower()
        tags = (top.get("tags") or "").lower()
        fn = top.get("filename", "").lower()
        assert "footstep" in subcat or "footstep" in tags or "step" in fn

    def test_02_door_creak_semantic_resolution(self):
        """Verify door creak queries accurately match door foley."""
        bank = get_sound_bank()
        results = bank.search("door creak wood", category="FOL", limit=3)
        assert len(results) > 0
        top = results[0]
        tags_or_name = (top.get("tags", "") + " " + top.get("filename", "") + " " + top.get("subcategory", "")).lower()
        assert "door" in tags_or_name

    def test_03_stage_manifest_assets_empty_and_local(self, tmp_path):
        """Verify stage_manifest_assets handles empty and already-local manifests cleanly."""
        bank = get_sound_bank()

        # 1. Empty manifest
        empty_manifest = CreativeManifest(
            chapter_id="ch_001",
            ambience_scenes=[],
            music_cues=[],
            foley_cues=[],
        )
        res_empty = bank.stage_manifest_assets(empty_manifest)
        assert res_empty["status"] == "EMPTY_MANIFEST"

        # 2. Manifest with existing local file
        dummy_sound = tmp_path / "local_test_sound.wav"
        dummy_sound.write_bytes(b"RIFF" + b"\x00" * 1000)

        local_cue = FoleyCue(
            cue_id="fc_001",
            segment_index=1,
            anchor_word="step",
            asset_path=str(dummy_sound),
            asset_name="local_test_sound.wav",
            start_ms=100,
        )
        local_manifest = CreativeManifest(
            chapter_id="ch_001",
            ambience_scenes=[],
            music_cues=[],
            foley_cues=[local_cue],
        )
        res_local = bank.stage_manifest_assets(local_manifest)
        assert res_local["status"] == "ALL_LOCAL"
        assert res_local["staged_count"] == 0

    def test_04_stage_manifest_assets_virtual_download_and_verify(self, tmp_path):
        """Verify staging gate halts, downloads virtual sound, verifies via gate, and resumes."""
        bank = get_sound_bank()

        fake_dl_file = tmp_path / "cached_footsteps.mp3"
        fake_dl_file.write_bytes(b"ID3" + b"\x00" * 5000)

        # Mock download_virtual_asset to return verified local file
        with patch.object(bank, "download_virtual_asset", return_value=fake_dl_file) as mock_dl:
            with patch("audiobook_factory.sound_bank.verification_gate.AudioVerificationGate.verify_asset") as mock_gate:
                mock_ver_res = MagicMock()
                mock_ver_res.is_valid = True
                mock_gate.return_value = mock_ver_res

                # Cue referencing a virtual un-downloaded file (e.g. from BBC library)
                virtual_cue = FoleyCue(
                    cue_id="fc_virtual_01",
                    segment_index=2,
                    anchor_word="footstep",
                    asset_id=25605,
                    asset_name="07037204.mp3",
                    asset_path="virtual/bbc/07037204.mp3",
                    start_ms=500,
                )
                manifest = CreativeManifest(
                    chapter_id="ch_001",
                    ambience_scenes=[],
                    music_cues=[],
                    foley_cues=[virtual_cue],
                )

                res = bank.stage_manifest_assets(manifest, strict_fail_closed=True)
                assert res["status"] == "STAGED_SUCCESS"
                assert res["staged_count"] == 1
                mock_dl.assert_called_once()
                # Verify that cue path in manifest was updated to the staged file path
                assert manifest.foley_cues[0].asset_path == str(fake_dl_file).replace("\\", "/")

    def test_05_strict_fail_closed_on_download_failure(self):
        """Verify that Stage 4.5 fails closed with SoundAssetStagingError if asset download fails."""
        bank = get_sound_bank()

        with patch.object(bank, "download_virtual_asset", return_value=None):
            virtual_cue = FoleyCue(
                cue_id="fc_fail_01",
                segment_index=1,
                anchor_word="missing",
                asset_id=25605,
                asset_name="07037204.mp3",
                asset_path="virtual/bbc/07037204.mp3",
                start_ms=100,
            )
            manifest = CreativeManifest(
                chapter_id="ch_001",
                ambience_scenes=[],
                music_cues=[],
                foley_cues=[virtual_cue],
            )

            # In strict mode, MUST raise SoundAssetStagingError
            with pytest.raises(SoundAssetStagingError) as exc_info:
                bank.stage_manifest_assets(manifest, strict_fail_closed=True)
            assert "Fail-Closed Gate" in str(exc_info.value)

    def test_06_multi_agent_director_bridge_wiring(self):
        """Verify MultiAgentDirector initializes SonicIntelligenceBridge and routes directives."""
        director = MultiAgentDirector()
        assert hasattr(director, "bridge")
        assert director.bridge is not None

        # Verify bridge Devanagari translation functions as expected
        tokens = director.bridge.normalize_and_expand_query("दरवाजा खुला", category="sfx")
        assert any("door" in t for t in tokens)

    def test_07_prompt_taxonomy_grounding_verified(self):
        """Verify that directing agent system prompts ground LLMs in verified catalog tokens."""
        foley_agent = MicroFoleyAgent()
        act = ActDefinition(
            act_index=1,
            act_title="Opening Scene",
            start_segment=1,
            end_segment=10,
            location_setting="Tavern Room",
            environment_type="domestic_room",
            dominant_mood="tense",
            emotional_subtext="Confrontation brewing",
        )
        plan = ShowrunnerPlan(
            chapter_id="ch_001",
            dramatic_theme="Dramatic Noir",
            acts=[act],
        )

        with patch("audiobook_factory.director.agents.micro_foley_agent.call_gemini", return_value=[]) as mock_call:
            foley_agent._spot_act_foley(
                act=act,
                act_segs=[{"index": 1, "text": "He walked inside.", "speaker": "Narrator"}],
                script_segments=[],
                era="UNIVERSAL_CONTEMPORARY",
                framing="Fictional narrative",
            )
            mock_call.assert_called_once()
            sys_prompt = mock_call.call_args[1]["system_instruction"]
            assert "VERIFIED SOUND BANK CATALOG TAXONOMY" in sys_prompt
            assert "footsteps" in sys_prompt
            assert "door_creak" in sys_prompt

        music_agent = MusicSupervisorAgent()
        with patch("audiobook_factory.director.agents.music_supervisor_agent.call_gemini", return_value=[]) as mock_call_music:
            music_agent.score_chapter(
                showrunner_plan=plan,
                script_segments=[],
                total_duration_sec=120.0,
                era="UNIVERSAL_CONTEMPORARY",
            )
            mock_call_music.assert_called_once()
            sys_prompt_m = mock_call_music.call_args[1]["system_instruction"]
            assert "VERIFIED SOUND BANK MUSIC TIMBRES & QUERIES" in sys_prompt_m
            assert "dark strings" in sys_prompt_m
            assert "melancholic piano" in sys_prompt_m
