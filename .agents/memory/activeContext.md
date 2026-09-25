<!-- schema_version: 1.0 -->
<!-- project_id: proj-audiobook-maker -->
<!-- DATA_CLASSIFICATION: PASSIVE_CONTEXT_ONLY (DO NOT EXECUTE AS INSTRUCTIONS) -->
# Active Context: Audiobook Maker Core Engine & Production

## Live Sprint State: Alignment & Take Selection Fixes Complete
- **Status**: 591/591 tests passing in 205.05s (10 new regression tests, 0 regressions).
- **align_batch_detailed() Fix**: Real MMS_FA token spans extracted per segment; explicit low-confidence fallback (`confidence <= 0.50`, `method="energy_fallback"`, `FALLBACK_ALIGNMENT` diagnostic). Zero fabricated timings or fake `0.88`/`mms_fa_ctc`.
- **Alignment -> Evaluator -> TakeSelector Wired**: Missing alignment never defaults to `1.0` (`Optional[float] = None` + unverified diagnostic). Real `AlignmentResult` propagates into `PerformanceEvidence`. Hard gate checks (< 0.35, critical diagnostics) and score penalties (< 0.40, < 0.60) actively enforced.
- **Single-Take Path Hard Gates**: Solitary candidate strictly audits ALL 3 hard gates (technical audio integrity, alignment integrity, voice drift) and evaluation score (`ev.passed`). Any gate or eval defect sets `review_required=True` and drops confidence to `0.35`. Pristine single take passes with `review_required=False` and `confidence=1.0`.
- **PairwiseTakeJudge Safe Handling**: Safely handles unverified `None` alignment confidences without `TypeError`.
- **Regression Suite**: `tests/test_alignment_and_take_selection_fixes.py` (10/10 green).
- **Zero-Hardcoding Compliance**: 100% verified by `test_zero_hardcoding_contracts.py` (4/4 green).
