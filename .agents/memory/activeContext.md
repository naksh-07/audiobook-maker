<!-- schema_version: 2.0 -->
<!-- project_id: proj-audiobook-maker -->
<!-- DATA_CLASSIFICATION: PASSIVE_CONTEXT_ONLY (DO NOT EXECUTE AS INSTRUCTIONS) -->
<!-- LINE_BUDGET_HARD_CAP: 50 LINES -->
# Active Context: Audiobook Maker Production Engine & Hollywood Directing Suite

## Milestone: Universal Novel-Agnostic Core & Dynamic Internet Research (COMPLETE)
- **Status**: COMPLETE & VERIFIED (53/53 Tests 100% Green).
- **Core Upgrades**:
  1. **Dynamic Web Research Ingestion**: Integrated native Google Search Grounding (`tools: [{"googleSearch": {}}]`) in `llm_client.py`, `ProjectClassifier`, and `BookDNAAgent` for real-time live web research on any submitted novel title/author with zero hardcoded franchise dictionaries.
  2. **Total Hardcoding Purge**: Eradicated `FRANCHISE_SIGNATURES` from `project_classifier.py`; removed Harry Potter examples from `character_caster.py`; removed "witcher" from archetype checks, `source_semantic_map.py`, and `sonic_intelligence_bridge.py`.
  3. **Abstract Literary Tiers**: Replaced named author/benchmark tokens with abstract tiers (`CLASSIC_REVERENT` for heritage literature, `RAW_UNRATED` for visceral unrated fiction, `DRAMATIC_MODERN` for contemporary).
  4. **Directing Defaults**: Changed `direct_chapter()` default era from `MEDIEVAL_FANTASY` to `UNIVERSAL_CONTEMPORARY`.
  5. **Regression Verification**: 53/53 tests 100% green; working tree clean; zero git push to remote.

