#!/usr/bin/env python3
"""
Audiobook Factory - 15 Canonical Golden Sound Design Benchmarks.
================================================================
Commercial cinematic audio drama benchmark scenarios for regression testing.
Demonstrates sound design richness, leitmotif continuity, physical world accuracy,
and narrative restraint comparable to premier full-cast productions (e.g. Pottermore).
"""

from __future__ import annotations
from typing import Dict, Any, List

GOLDEN_BENCHMARK_SCENARIOS: List[Dict[str, Any]] = [
    # 01. Castle Great Hall Banquet
    {
        "benchmark_id": "01_castle_hall_banquet",
        "title": "Castle Great Hall Banquet",
        "environment_id": "castle_great_hall",
        "tension_level": 0.35,
        "dominant_emotion": "festive",
        "characters": ["King", "Knight", "Cupbearer", "Lord"],
        "segments": [
            {
                "segment_index": 1,
                "speaker": "King",
                "text": "Raise your goblets to the realm! Drink until the morning light!",
                "sfx_cues": ["goblet clatter", "cheers"],
                "start_ms": 0,
            },
            {
                "segment_index": 2,
                "speaker": "Narrator",
                "text": "The servants hurried across the stone floor, placing heavy ceramic plates and silver dishes upon the long tables.",
                "sfx_cues": [],
                "start_ms": 4000,
            },
        ],
        "expected_checks": {
            "tableware_isolation": True,
            "walla_present": True,
            "rt60_min": 1800,
        },
    },

    # 02. Solitary Catacomb Infiltration
    {
        "benchmark_id": "02_solitary_catacomb_infiltration",
        "title": "Solitary Catacomb Infiltration",
        "environment_id": "crypt_subterranean",
        "tension_level": 0.70,
        "dominant_emotion": "stealth",
        "characters": ["Rogue"],
        "segments": [
            {
                "segment_index": 1,
                "speaker": "Narrator",
                "text": "She stepped lightly onto the damp flagstones, holding her breath in the ancient silence.",
                "sfx_cues": [],
                "start_ms": 0,
            },
            {
                "segment_index": 2,
                "speaker": "Rogue",
                "text": "Not a sound... The sarcophagus must be just ahead.",
                "sfx_cues": [],
                "start_ms": 5000,
            },
        ],
        "expected_checks": {
            "walla_suppressed": True,
            "restraint_tier": "high",
            "silence_present": True,
        },
    },

    # 03. Dark Forest Wolf Stalking
    {
        "benchmark_id": "03_dark_forest_wolf_stalking",
        "title": "Dark Forest Wolf Stalking",
        "environment_id": "dark_forest",
        "tension_level": 0.75,
        "dominant_emotion": "dread",
        "characters": ["Hunter"],
        "creature_presence": "wolf_pack",
        "segments": [
            {
                "segment_index": 1,
                "speaker": "Narrator",
                "text": "A twig snapped in the undergrowth. From the black canopy came a low, guttural growl.",
                "sfx_cues": ["twig snapped"],
                "start_ms": 0,
            },
        ],
        "expected_checks": {
            "creature_event_present": True,
            "walla_suppressed": True,
        },
    },

    # 04. Duel on the Stormy Ramparts
    {
        "benchmark_id": "04_duel_stormy_ramparts",
        "title": "Duel on the Stormy Ramparts",
        "environment_id": "mountain_pass_blizzard",
        "tension_level": 0.90,
        "dominant_emotion": "furious",
        "characters": ["Warrior1", "Warrior2"],
        "segments": [
            {
                "segment_index": 1,
                "speaker": "Narrator",
                "text": "Rain lashed against the stone parapet as their steel swords clashed with violent fury.",
                "sfx_cues": ["swords clashed"],
                "start_ms": 0,
            },
        ],
        "expected_checks": {
            "hard_sfx_present": True,
            "music_cue_present": True,
        },
    },

    # 05. Ancient Library Research
    {
        "benchmark_id": "05_ancient_library_research",
        "title": "Ancient Library Research",
        "environment_id": "ancient_library",
        "tension_level": 0.25,
        "dominant_emotion": "mysterious",
        "characters": ["Scholar"],
        "segments": [
            {
                "segment_index": 1,
                "speaker": "Narrator",
                "text": "The scholar turned the brittle parchment page, dipping his quill into the dark inkwell.",
                "sfx_cues": ["parchment page", "quill write"],
                "start_ms": 0,
            },
        ],
        "expected_checks": {
            "restraint_tier": "high",
            "walla_suppressed": True,
        },
    },

    # 06. Tavern Brawl Eruption
    {
        "benchmark_id": "06_tavern_brawl_eruption",
        "title": "Tavern Brawl Eruption",
        "environment_id": "tavern_interior",
        "tension_level": 0.85,
        "dominant_emotion": "panic",
        "characters": ["Barkeep", "Brawler1", "Brawler2", "Patrons"],
        "segments": [
            {
                "segment_index": 1,
                "speaker": "Narrator",
                "text": "A wooden chair shattered against the timber wall, and the crowd panicked as brawlers tore through the room.",
                "sfx_cues": ["chair shattered"],
                "start_ms": 0,
            },
        ],
        "expected_checks": {
            "walla_present": True,
            "hard_sfx_present": True,
        },
    },

    # 07. Sacred Temple Incantation
    {
        "benchmark_id": "07_sacred_temple_incantation",
        "title": "Sacred Temple Incantation",
        "environment_id": "castle_great_hall",
        "tension_level": 0.60,
        "dominant_emotion": "reverent",
        "characters": ["HighPriest"],
        "segments": [
            {
                "segment_index": 1,
                "speaker": "HighPriest",
                "text": "By the sacred fire, let the ward be renewed!",
                "sfx_cues": ["incantation", "runes glowed"],
                "start_ms": 0,
            },
        ],
        "expected_checks": {
            "magic_event_present": True,
        },
    },

    # 08. Carriage Chase along Mountain Cliff
    {
        "benchmark_id": "08_carriage_chase_mountain",
        "title": "Carriage Chase along Mountain Cliff",
        "environment_id": "horse_carriage_road",
        "tension_level": 0.88,
        "dominant_emotion": "panic",
        "characters": ["Driver", "Pursuer"],
        "segments": [
            {
                "segment_index": 1,
                "speaker": "Narrator",
                "text": "The wooden wagon crash threw sparks as the rear wheel struck the boulders.",
                "sfx_cues": ["wagon crash"],
                "start_ms": 0,
            },
        ],
        "expected_checks": {
            "hard_sfx_present": True,
        },
    },

    # 09. Intimate Confession by the Hearth
    {
        "benchmark_id": "09_hearth_confession_intimate",
        "title": "Intimate Confession by the Hearth",
        "environment_id": "castle_bedchamber",
        "tension_level": 0.30,
        "dominant_emotion": "intimate",
        "characters": ["Hero", "Companion"],
        "segments": [
            {
                "segment_index": 1,
                "speaker": "Hero",
                "text": "I never intended for you to bear this burden with me.",
                "sfx_cues": [],
                "start_ms": 0,
            },
        ],
        "expected_checks": {
            "walla_suppressed": True,
            "silence_present": True,
        },
    },

    # 10. Cataclysmic Sorcerer Battle
    {
        "benchmark_id": "10_sorcerer_cataclysm_battle",
        "title": "Cataclysmic Sorcerer Battle",
        "environment_id": "castle_great_hall",
        "tension_level": 0.95,
        "dominant_emotion": "terror",
        "characters": ["Archmage", "Warlock"],
        "segments": [
            {
                "segment_index": 1,
                "speaker": "Archmage",
                "text": "The blast shattered the enchanted pillars into dust as raw lightning arced between them.",
                "sfx_cues": ["blast shattered", "lightning strike"],
                "start_ms": 0,
            },
        ],
        "expected_checks": {
            "hard_sfx_present": True,
            "magic_event_present": True,
        },
    },

    # 11. Battlefield Rally and Siege
    {
        "benchmark_id": "11_battlefield_rally_siege",
        "title": "Battlefield Rally and Siege",
        "environment_id": "city_market_square",
        "tension_level": 0.85,
        "dominant_emotion": "rally",
        "characters": ["Commander", "Soldiers"],
        "segments": [
            {
                "segment_index": 1,
                "speaker": "Commander",
                "text": "Hold the line! Stand your ground for the realm!",
                "sfx_cues": ["charge", "rally"],
                "start_ms": 0,
            },
        ],
        "expected_checks": {
            "walla_present": True,
        },
    },

    # 12. Eerie Swamp Fog Journey
    {
        "benchmark_id": "12_eerie_swamp_crossing",
        "title": "Eerie Swamp Fog Journey",
        "environment_id": "swamp_marsh_night",
        "tension_level": 0.65,
        "dominant_emotion": "dread",
        "characters": ["Guide", "Traveler"],
        "segments": [
            {
                "segment_index": 1,
                "speaker": "Narrator",
                "text": "Thick fog clung to the stagnant water as their boots squelched in the deep black mud.",
                "sfx_cues": ["boots squelched"],
                "start_ms": 0,
            },
        ],
        "expected_checks": {
            "walla_suppressed": True,
        },
    },

    # 13. Royal Court Accusation & Silence
    {
        "benchmark_id": "13_royal_court_accusation",
        "title": "Royal Court Accusation & Silence",
        "environment_id": "castle_great_hall",
        "tension_level": 0.80,
        "dominant_emotion": "shock",
        "characters": ["Accuser", "Chancellor", "Courtiers"],
        "segments": [
            {
                "segment_index": 1,
                "speaker": "Accuser",
                "text": "He is a traitor! The seal belongs to the enemy!",
                "sfx_cues": [],
                "start_ms": 0,
            },
        ],
        "expected_checks": {
            "silence_present": True,
        },
    },

    # 14. Striga Crypt Awakening
    {
        "benchmark_id": "14_striga_crypt_awakening",
        "title": "Striga Crypt Awakening",
        "environment_id": "crypt_subterranean",
        "tension_level": 0.92,
        "dominant_emotion": "terror",
        "characters": ["Hunter"],

        "creature_presence": "striga",
        "segments": [
            {
                "segment_index": 1,
                "speaker": "Narrator",
                "text": "From the stone coffin came a bone-chilling shriek as the striga roared in hunger.",
                "sfx_cues": [],
                "start_ms": 0,
            },
        ],
        "expected_checks": {
            "creature_event_present": True,
            "walla_suppressed": True,
        },
    },

    # 15. Quiet Dawn Aftermath
    {
        "benchmark_id": "15_dawn_aftermath_resolution",
        "title": "Quiet Dawn Aftermath",
        "environment_id": "castle_stone_corridor",
        "tension_level": 0.20,
        "dominant_emotion": "peace",
        "characters": ["Survivor"],
        "segments": [
            {
                "segment_index": 1,
                "speaker": "Narrator",
                "text": "Dawn light broke across the battlements, leaving the castle in quiet contemplation.",
                "sfx_cues": [],
                "start_ms": 0,
            },
        ],
        "expected_checks": {
            "restraint_tier": "high",
            "walla_suppressed": True,
            "silence_present": True,
        },
    },

    # 16. Musicless Emotional Scene (Restraint & Subtext)
    {
        "benchmark_id": "16_musicless_emotional_grief",
        "title": "Musicless Emotional Grief",
        "environment_id": "crypt_subterranean",
        "tension_level": 0.15,
        "dominant_emotion": "grief",
        "characters": ["Mourner", "Priest"],
        "segments": [
            {
                "segment_index": 1,
                "speaker": "Mourner",
                "text": "He is gone... and there are no words left in this world.",
                "sfx_cues": [],
                "start_ms": 0,
            },
            {
                "segment_index": 2,
                "speaker": "Priest",
                "text": "May the earth hold his bones in peace.",
                "sfx_cues": [],
                "start_ms": 6000,
            },
        ],
        "expected_checks": {
            "no_music": True,
            "silence_present": True,
            "walla_suppressed": True,
        },
    },

    # 17. Recurring Character Motif with Emotional Variations
    {
        "benchmark_id": "17_recurring_character_motif_variations",
        "title": "Recurring Character Motif Variations",
        "environment_id": "castle_great_hall",
        "tension_level": 0.85,
        "dominant_emotion": "revelation",
        "characters": ["Sorceress", "Warrior"],
        "segments": [
            {
                "segment_index": 1,
                "speaker": "Sorceress",
                "text": "Look upon the mirror! The truth you fled from has found you at last.",
                "dramatic_function": "revelation",
                "sfx_cues": [],
                "start_ms": 0,
            },
            {
                "segment_index": 2,
                "speaker": "Warrior",
                "text": "By the gods... it cannot be.",
                "dramatic_function": "turn",
                "sfx_cues": ["sword hilt clatter"],
                "start_ms": 7000,
            },
        ],
        "expected_checks": {
            "music_present": True,
            "beat_aware_timing": True,
        },
    },

    # 18. Recurring Location with Changing Dramatic State
    {
        "benchmark_id": "18_recurring_location_dramatic_transition",
        "title": "Recurring Location Dramatic Transition",
        "environment_id": "dark_forest",
        "tension_level": 0.65,
        "dominant_emotion": "dread",
        "characters": ["Scout"],
        "segments": [
            {
                "segment_index": 1,
                "speaker": "Narrator",
                "text": "The wind shifted through the high pine needles as distant thunder rumbled.",
                "sfx_cues": ["thunder distant"],
                "start_ms": 0,
            },
            {
                "segment_index": 2,
                "speaker": "Scout",
                "text": "Something is moving between the birch trunks.",
                "sfx_cues": ["branch snap"],
                "start_ms": 6000,
            },
        ],
        "expected_checks": {
            "ambience_layers_min": 2,
            "walla_suppressed": True,
        },
    },

    # 19. Cross-System Reveal Sequence
    {
        "benchmark_id": "19_cross_system_reveal_sequence",
        "title": "Cross-System Reveal Sequence",
        "environment_id": "castle_great_hall",
        "tension_level": 0.90,
        "dominant_emotion": "shock",
        "characters": ["Herald", "King", "Courtiers"],
        "segments": [
            {
                "segment_index": 1,
                "speaker": "Herald",
                "text": "Silence for the Regent! He brings news of the southern front!",
                "sfx_cues": ["staff strike stone"],
                "start_ms": 0,
            },
            {
                "segment_index": 2,
                "speaker": "Narrator",
                "text": "The grand hall fell into stunned stillness as every eye turned to the heavy oak doors.",
                "sfx_cues": [],
                "start_ms": 5000,
            },
        ],
        "expected_checks": {
            "silence_present": True,
            "walla_attenuated_or_suppressed": True,
        },
    },

    # 20. Complex Ensemble with Foley, Walla, Movement and Spatial Choreography
    {
        "benchmark_id": "20_complex_ensemble_spatial_choreography",
        "title": "Complex Ensemble Spatial Choreography",
        "environment_id": "tavern_interior",
        "tension_level": 0.40,
        "dominant_emotion": "festive",
        "characters": ["Barkeeper", "Traveler", "Minstrel", "Brawler", "Patrons"],
        "segments": [
            {
                "segment_index": 1,
                "speaker": "Barkeeper",
                "text": "The barkeep slammed a heavy wooden tankard upon the timber bar. The patrons laughed and cheered as he stepped across the room.",
                "sfx_cues": ["tankard clatter on wood", "footsteps heavy boots"],
                "start_ms": 0,
            },
            {
                "segment_index": 2,
                "speaker": "Traveler",
                "text": "He poured the dark ale and tossed coins upon the wooden table. Keep the change, innkeeper.",
                "sfx_cues": ["coins on table"],
                "start_ms": 6000,
            },
            {
                "segment_index": 3,
                "speaker": "Minstrel",
                "text": "A song of forgotten kings for the brave patrons!",
                "sfx_cues": [],
                "start_ms": 12000,
            },
        ],
        "expected_checks": {
            "walla_present": True,
            "foley_present": True,
            "spatial_diversity": True,
        },
    },
]
