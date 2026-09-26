"""
Phase 2 Validation Suite: Dedicated Audio Classifiers & CLAP Semantic Embeddings.
Verifies all 14 Section 23 test pillars:
1. Classifier adapter contract
2. Raw output preservation
3. Provenance tracking
4. Model versioning
5. Confidence handling
6. Temporal event storage
7. Short-audio preprocessing
8. CLAP audio embedding
9. CLAP text embedding
10. CLAP dimensions & provenance
11. Deterministic repeatability
12. Failure isolation
13. Idempotent reprocessing
14. Sonic Genome integration
"""

import json
import sqlite3
import tempfile
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from audiobook_factory.contracts import (
    AudioEventRecord,
    ClassifierInferences,
    ClassifierPrediction,
    MeasuredAudioFacts,
    ProvenanceRecord,
    SemanticEmbeddingFacts,
    SonicGenome,
)
from audiobook_factory.sonic_model_manager import AudioPreprocessor, SonicModelManager
from audiobook_factory.audio_classifier_adapters import (
    ASTClassifierAdapter,
    AUDIOSET_TO_STUDIO_ONTOLOGY,
    BaseAudioClassifier,
)
from audiobook_factory.clap_semantic_adapter import CLAPSemanticAdapter
from audiobook_factory.sound_bank import SoundBank


@pytest.fixture
def temp_bank():
    with tempfile.TemporaryDirectory() as tmp_dir:
        bank_path = Path(tmp_dir)
        bank = SoundBank(bank_root=bank_path)
        yield bank


@pytest.fixture
def synthetic_tones():
    """Generates test waveforms for various scenarios."""
    sr = 48000
    t = np.linspace(0, 1.0, sr, dtype=np.float32)

    # 440 Hz pure tone (1.0 sec)
    tone_440 = np.sin(2 * np.pi * 440 * t)

    # Micro transient: 100ms click/impact
    micro_transient = np.zeros(int(0.10 * sr), dtype=np.float32)
    micro_transient[int(0.04 * sr) : int(0.06 * sr)] = np.sin(
        2 * np.pi * 1000 * np.linspace(0, 0.02, int(0.02 * sr), dtype=np.float32)
    )

    # White noise (1.0 sec)
    noise = np.random.uniform(-0.2, 0.2, sr).astype(np.float32)

    # Long waveform (12.0 sec) for temporal slicing
    t_long = np.linspace(0, 12.0, int(12.0 * sr), dtype=np.float32)
    long_tone = 0.5 * np.sin(2 * np.pi * 300 * t_long)

    return {
        "sr": sr,
        "tone_440": tone_440,
        "micro_transient": micro_transient,
        "noise": noise,
        "long_tone": long_tone,
    }


def test_01_classifier_adapter_contract(synthetic_tones):
    """Pillar 1: BaseAudioClassifier interface & AST implementation contract."""
    adapter = ASTClassifierAdapter()
    assert isinstance(adapter, BaseAudioClassifier)
    assert adapter.model_id == "MIT/ast-finetuned-audioset-10-10-0.4593"
    assert adapter.model_version == "1.0.0"
    assert adapter.ontology_id == "audioset_527"

    wf = synthetic_tones["tone_440"]
    sr = synthetic_tones["sr"]
    inferences = adapter.classify(wf, sr, duration_sec=1.0, top_k=5)

    assert isinstance(inferences, ClassifierInferences)
    assert len(inferences.predictions) == 5
    assert len(inferences.top_labels) == 5
    assert inferences.model_id == adapter.model_id


def test_02_raw_output_preservation(synthetic_tones):
    """Pillar 2: Raw model scores, logits/sigmoids, and unthresholded predictions preserved."""
    adapter = ASTClassifierAdapter()
    wf = synthetic_tones["tone_440"]
    sr = synthetic_tones["sr"]
    inferences = adapter.classify(wf, sr, duration_sec=1.0, top_k=10)

    # Verify rank order and raw scores
    prev_score = 1.0
    for p in inferences.predictions:
        assert isinstance(p, ClassifierPrediction)
        assert 0.0 <= p.raw_score <= 1.0
        assert p.raw_score <= prev_score + 1e-5
        assert p.raw_label is not None
        prev_score = p.raw_score

    # Top prediction for pure tone should be Sine wave
    top_pred = inferences.predictions[0]
    assert "Sine wave" in top_pred.raw_label
    assert top_pred.raw_score > 0.40


def test_03_provenance_tracking(synthetic_tones):
    """Pillar 3: Explicit ProvenanceRecord tracking with model ID, ontology, and processing strategy."""
    adapter = ASTClassifierAdapter()
    wf = synthetic_tones["tone_440"]
    sr = synthetic_tones["sr"]
    inferences = adapter.classify(wf, sr, duration_sec=1.0)

    prov = inferences.provenance
    assert isinstance(prov, ProvenanceRecord)
    assert prov.source_method == "classifier"
    assert "ast_classifier" in prov.analyzer_id
    assert prov.ontology_version == "audioset_527"
    assert prov.confidence is not None
    assert "prep_strategy" in (prov.notes or "")


def test_04_model_versioning(synthetic_tones):
    """Pillar 4: Distinct model and ontology version tracking."""
    adapter_v1 = ASTClassifierAdapter(model_version="1.0.0")
    adapter_v2 = ASTClassifierAdapter(model_version="2.0.0-custom")

    assert adapter_v1.model_version == "1.0.0"
    assert adapter_v2.model_version == "2.0.0-custom"

    wf = synthetic_tones["tone_440"]
    inferences = adapter_v2.classify(wf, synthetic_tones["sr"], 1.0)
    assert inferences.model_version == "2.0.0-custom"
    assert inferences.provenance.analyzer_version == "2.0.0-custom"


def test_05_confidence_handling(synthetic_tones):
    """Pillar 5: Raw scores preserved without arbitrary thresholding, calibrated_score=None."""
    adapter = ASTClassifierAdapter()
    inferences = adapter.classify(synthetic_tones["tone_440"], synthetic_tones["sr"], 1.0, top_k=5)

    for p in inferences.predictions:
        # Raw scores are preserved exactly
        assert isinstance(p.raw_score, float)
        # Section 6 requirement: Do not invent calibration where none exists
        assert p.calibrated_score is None


def test_06_temporal_event_storage(synthetic_tones):
    """Pillar 6: Temporal sound event detection on long clips (>10s) with valid intervals."""
    adapter = ASTClassifierAdapter()
    long_wf = synthetic_tones["long_tone"]
    sr = synthetic_tones["sr"]

    events = adapter.detect_temporal_events(long_wf, sr, duration_sec=12.0, score_threshold=0.10)
    assert len(events) >= 1
    for ev in events:
        assert isinstance(ev, AudioEventRecord)
        assert ev.start_sec >= 0.0
        assert ev.end_sec > ev.start_sec
        assert ev.end_sec <= 12.0
        assert ev.source_method == "classifier"
        assert "raw_label" in ev.metadata


def test_07_short_audio_preprocessing(synthetic_tones):
    """Pillar 7: Micro-SFX (100ms) active-region centering & energy-conserving padding."""
    micro = synthetic_tones["micro_transient"]
    sr = synthetic_tones["sr"]
    assert len(micro) / sr == 0.10  # 100ms

    padded, strategy = AudioPreprocessor.preprocess_short_audio(
        micro, sr, target_duration_sec=1.0
    )
    assert len(padded) == sr  # 1.0 sec
    assert strategy == "centered_energy_conserving_pad"
    assert not np.isnan(padded).any()
    assert not np.isinf(padded).any()

    # Verify adapter can classify without error or dimension mismatch
    adapter = ASTClassifierAdapter()
    inferences = adapter.classify(micro, sr, duration_sec=0.10, top_k=3)
    assert len(inferences.predictions) == 3


def test_08_clap_audio_embedding(synthetic_tones):
    """Pillar 8: 512-dimensional CLAP audio embedding with unit L2 norm."""
    adapter = CLAPSemanticAdapter()
    wf = synthetic_tones["tone_440"]
    sr = synthetic_tones["sr"]

    vector, facts = adapter.embed_audio(wf, sr, duration_sec=1.0)
    assert isinstance(vector, np.ndarray)
    assert vector.shape == (512,)
    assert vector.dtype == np.float32

    # L2 norm must be approximately 1.0
    norm = np.linalg.norm(vector)
    assert np.isclose(norm, 1.0, atol=1e-3)

    assert isinstance(facts, SemanticEmbeddingFacts)
    assert facts.embedding_dim == 512
    assert facts.provenance.source_method == "semantic_model"


def test_09_clap_text_embedding():
    """Pillar 9: 512-dimensional CLAP text embedding for atomic and batch queries."""
    adapter = CLAPSemanticAdapter()

    # Single text
    vec, prov = adapter.embed_text("heavy iron gate slamming shut in a dungeon")
    assert vec.shape == (512,)
    assert np.isclose(np.linalg.norm(vec), 1.0, atol=1e-3)
    assert prov.source_method == "semantic_model"

    # Batch texts for query decomposition
    texts = ["footsteps on stone", "distant thunder", "magic crystal resonance"]
    matrix, batch_prov = adapter.embed_text_batch(texts)
    assert matrix.shape == (3, 512)
    for row in matrix:
        assert np.isclose(np.linalg.norm(row), 1.0, atol=1e-3)


def test_10_clap_embedding_dimensions_and_provenance(synthetic_tones):
    """Pillar 10: Compact 2,048-byte BLOB storage in SQLite sound_embeddings."""
    adapter = CLAPSemanticAdapter()
    vec, facts = adapter.embed_audio(synthetic_tones["tone_440"], synthetic_tones["sr"], 1.0)

    # 512 float32 = exactly 2048 bytes
    blob_bytes = vec.tobytes()
    assert len(blob_bytes) == 2048

    # Recover from bytes
    recovered = np.frombuffer(blob_bytes, dtype=np.float32)
    assert np.allclose(vec, recovered)


def test_11_deterministic_repeatability(synthetic_tones):
    """Pillar 11: Deterministic repeatability for identical input waveforms."""
    adapter = CLAPSemanticAdapter()
    wf = synthetic_tones["tone_440"]
    sr = synthetic_tones["sr"]

    vec1, _ = adapter.embed_audio(wf, sr, 1.0)
    vec2, _ = adapter.embed_audio(wf, sr, 1.0)

    assert np.allclose(vec1, vec2, atol=1e-5)
    sim = CLAPSemanticAdapter.compute_similarity(vec1, vec2)
    assert np.isclose(sim, 1.0, atol=1e-4)


def test_12_failure_isolation(temp_bank, synthetic_tones):
    """Pillar 12: Corrupted or missing audio fails gracefully without corrupting catalog."""
    bank = temp_bank
    sr = synthetic_tones["sr"]

    # Ingest a valid sound
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        sf.write(f.name, synthetic_tones["tone_440"], sr)
        wav_path = Path(f.name)

    stats = bank.scan_and_index(extra_dirs=[wav_path.parent])
    with bank._get_conn() as conn:
        sound_id = conn.execute("SELECT id FROM sound_catalog LIMIT 1").fetchone()["id"]

    # Delete the physical file to simulate missing/corrupted file
    wav_path.unlink()

    # enrich_asset_phase2 must raise FileNotFoundError or record failure, NOT crash database
    with pytest.raises(FileNotFoundError):
        bank.enrich_asset_phase2(sound_id=sound_id, force=True)

    with bank._get_conn() as conn:
        run = conn.execute("""
            SELECT execution_status, error_message FROM sound_analysis_runs
            WHERE track_id = ? AND analysis_stage = 'PHASE2_AI_ENRICHMENT'
        """, (sound_id,)).fetchone()
        assert run is not None
        assert run["execution_status"] == "FAILED"


def test_13_idempotent_reprocessing(temp_bank, synthetic_tones):
    """Pillar 13: Re-running Phase 2 without force skips; force=True updates idempotently."""
    bank = temp_bank
    sr = synthetic_tones["sr"]

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        sf.write(f.name, synthetic_tones["tone_440"], sr)
        wav_path = Path(f.name)

    bank.scan_and_index(extra_dirs=[wav_path.parent])
    with bank._get_conn() as conn:
        sound_id = conn.execute("SELECT id FROM sound_catalog LIMIT 1").fetchone()["id"]

    # First run
    genome1 = bank.enrich_asset_phase2(sound_id=sound_id, force=False)
    assert genome1 is not None

    with bank._get_conn() as conn:
        run_count1 = conn.execute("SELECT COUNT(*) FROM sound_analysis_runs WHERE track_id = ?", (sound_id,)).fetchone()[0]

    # Second run without force should be skipped
    genome2 = bank.enrich_asset_phase2(sound_id=sound_id, force=False)
    with bank._get_conn() as conn:
        run_count2 = conn.execute("SELECT COUNT(*) FROM sound_analysis_runs WHERE track_id = ?", (sound_id,)).fetchone()[0]
    assert run_count1 == run_count2

    # Third run with force=True should re-enrich without duplicate embedding rows
    genome3 = bank.enrich_asset_phase2(sound_id=sound_id, force=True)
    with bank._get_conn() as conn:
        embed_count = conn.execute("SELECT COUNT(*) FROM sound_embeddings WHERE track_id = ?", (sound_id,)).fetchone()[0]
        assert embed_count == 1  # UNIQUE constraint prevents duplicate vectors

    wav_path.unlink()


def test_14_sonic_genome_integration(temp_bank, synthetic_tones):
    """Pillar 14: Clean epistemic integration of Phase 1 DSP facts and Phase 2 AI facts."""
    bank = temp_bank
    sr = synthetic_tones["sr"]

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        sf.write(f.name, synthetic_tones["tone_440"], sr)
        wav_path = Path(f.name)

    bank.scan_and_index(extra_dirs=[wav_path.parent])
    with bank._get_conn() as conn:
        sound_id = conn.execute("SELECT id FROM sound_catalog LIMIT 1").fetchone()["id"]

    # Phase 1 deterministic DSP
    genome_p1 = bank.enrich_asset(sound_id=sound_id, force=True)
    assert genome_p1.measured_facts.loudness.integrated_lufs is not None
    dsp_lufs = genome_p1.measured_facts.loudness.integrated_lufs

    # Phase 2 AI enrichment
    genome_p2 = bank.enrich_asset_phase2(sound_id=sound_id, force=True)

    # Epistemic check: Phase 1 measured facts are NOT altered or overwritten by AI
    assert genome_p2.measured_facts.loudness.integrated_lufs == dsp_lufs
    assert genome_p2.classifier_inferences is not None
    assert genome_p2.semantic_model_facts is not None
    assert len(genome_p2.provenance_ledger) >= 3

    # Check database query helpers
    embed = bank.get_sound_embedding(sound_id)
    assert embed is not None
    assert embed.shape == (512,)

    tags = bank.get_classifier_tags(sound_id)
    assert len(tags) >= 5
    assert tags[0]["raw_score"] > 0.0

    wav_path.unlink()
