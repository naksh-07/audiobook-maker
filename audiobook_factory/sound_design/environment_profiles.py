#!/usr/bin/env python3
"""
Audiobook Factory - Capability 03: Environment & World Sound Profiles.
=====================================================================
Reusable environment sound profiles ensuring that recurring narrative settings
maintain consistent acoustic, surface, and atmospheric identity across scenes.
Extends WorldAcousticProfile from sonic_bible.py without duplicate source of truth.
"""

from __future__ import annotations
import re
from typing import Dict, Any, List, Optional
from audiobook_factory.sound_design.contracts import EnvironmentProfile
from audiobook_factory.sonic_bible import WorldAcousticProfile

# -----------------------------------------------------------------------------
# Standard Canonical Environment Profiles Catalog
# -----------------------------------------------------------------------------

STANDARD_ENVIRONMENTS: Dict[str, EnvironmentProfile] = {
    # 1. Castle Environments
    "castle_great_hall": EnvironmentProfile(
        env_id="castle_great_hall",
        display_name="Castle Great Hall",
        category="indoor",
        default_surfaces=["stone", "heavy_wood", "rug"],
        typical_ambience_layers=["amb_castle_hall_hearth.wav", "wind_howl.ogg"],
        distant_sounds=["distant_guard_footsteps", "distant_banner_flapping"],
        typical_foley=["wood_creak", "goblet_clatter", "chair_drag", "boots_stone"],
        typical_walla="court_whispers",
        typical_weather="indoor_warm",
        typical_creatures=[],
        estimated_rt60_ms=2200,
        occlusion_barrier_hz=1200,
        default_absorption=0.25,
    ),
    "castle_stone_corridor": EnvironmentProfile(
        env_id="castle_stone_corridor",
        display_name="Castle Stone Corridor",
        category="indoor",
        default_surfaces=["stone_flagstone", "cold_masonry"],
        typical_ambience_layers=["dungeon_cave_bed.ogg"],
        distant_sounds=["distant_drip", "wind_whistle_arrowslit"],
        typical_foley=["boots_stone", "torch_sizzle", "key_rattle", "door_creak"],
        typical_walla=None,
        typical_weather=None,
        typical_creatures=["rat_scurry"],
        estimated_rt60_ms=2600,
        occlusion_barrier_hz=1400,
        default_absorption=0.15,
    ),
    "castle_bedchamber": EnvironmentProfile(
        env_id="castle_bedchamber",
        display_name="Private Castle Bedchamber",
        category="indoor",
        default_surfaces=["wood_plank", "heavy_carpet", "cloth_curtains"],
        typical_ambience_layers=["amb_castle_hall_hearth.wav"],
        distant_sounds=["rain_window", "distant_wind"],
        typical_foley=["parchment_quill", "cloth_rustle", "candle_pop", "soft_footsteps"],
        typical_walla=None,
        typical_weather="sheltered",
        typical_creatures=[],
        estimated_rt60_ms=650,
        occlusion_barrier_hz=900,
        default_absorption=0.65,
    ),
    "crypt_catacomb": EnvironmentProfile(
        env_id="crypt_catacomb",
        display_name="Crypt / Ancient Catacombs",
        category="subterranean",
        default_surfaces=["damp_granite", "gravel", "bone_dust"],
        typical_ambience_layers=["amb_crypt_tomb_drips.wav"],
        distant_sounds=["water_drip_resonant", "distant_grate_creak"],
        typical_foley=["boots_gravel", "sarcophagus_grind", "bone_crunch", "torch_flicker"],
        typical_walla=None,
        typical_weather=None,
        typical_creatures=["striga", "ghoul", "carrion_beetle"],
        estimated_rt60_ms=3400,
        occlusion_barrier_hz=600,
        default_absorption=0.10,
    ),

    # 2. Nature & Outdoors
    "deep_forest_night": EnvironmentProfile(
        env_id="deep_forest_night",
        display_name="Deep Forest at Night",
        category="outdoor_nature",
        default_surfaces=["damp_soil", "fallen_leaves", "pine_needles", "moss"],
        typical_ambience_layers=["forest_night_crickets.ogg", "wind_howl.ogg"],
        distant_sounds=["distant_wolf_howl", "owl_hooting", "distant_thunder"],
        typical_foley=["twig_snap", "leaves_rustle", "boot_mud", "branch_brush"],
        typical_walla=None,
        typical_weather="chilly_breeze",
        typical_creatures=["wolf_pack", "nocturnal_bird", "deer"],
        estimated_rt60_ms=300,
        occlusion_barrier_hz=18000,
        default_absorption=0.85,
    ),
    "mountain_pass_blizzard": EnvironmentProfile(
        env_id="mountain_pass_blizzard",
        display_name="Mountain Pass Blizzard",
        category="outdoor_nature",
        default_surfaces=["packed_snow", "deep_drift", "scree_rock", "ice"],
        typical_ambience_layers=["amb_blizzard_mountain_gale.wav"],
        distant_sounds=["avalanche_rumble", "rockfall_distant"],
        typical_foley=["snow_crunch", "cloak_flapping", "heavy_breathing_cold", "ice_crackle"],
        typical_walla=None,
        typical_weather="severe_blizzard",
        typical_creatures=["wyvern_cry", "mountain_goat"],
        estimated_rt60_ms=200,
        occlusion_barrier_hz=18000,
        default_absorption=0.90,
    ),
    "swamp_marsh_night": EnvironmentProfile(
        env_id="swamp_marsh_night",
        display_name="Murky Swamp / Wetland",
        category="outdoor_nature",
        default_surfaces=["wet_mud", "marsh_water", "decaying_wood", "reeds"],
        typical_ambience_layers=["amb_bog_swamp_night.wav"],
        distant_sounds=["bullfrog_croak", "bubble_burst", "nightjar_whistle"],
        typical_foley=["squelch_step", "water_splash_shallow", "reed_parting", "mosquito_buzz"],
        typical_walla=None,
        typical_weather="humid_mist",
        typical_creatures=["water_hag", "drowner", "leech"],
        estimated_rt60_ms=250,
        occlusion_barrier_hz=16000,
        default_absorption=0.80,
    ),

    # 3. Settlements & Human Spaces
    "tavern_interior": EnvironmentProfile(
        env_id="tavern_interior",
        display_name="Bustling Medieval Tavern",
        category="settlement",
        default_surfaces=["beer_stained_wood", "sawdust", "hearth_stone"],
        typical_ambience_layers=["amb_castle_hall_hearth.wav"],
        distant_sounds=["rain_shutter", "carriage_pass"],
        typical_foley=["tankard_slam", "plate_clatter", "bench_scrape", "coin_drop"],
        typical_walla="tavern_murmur",
        typical_weather="indoor_warm",
        typical_creatures=[],
        estimated_rt60_ms=1100,
        occlusion_barrier_hz=1100,
        default_absorption=0.55,
    ),
    "city_market_square": EnvironmentProfile(
        env_id="city_market_square",
        display_name="City Market Square",
        category="settlement",
        default_surfaces=["cobblestone", "packed_dirt", "wooden_stall"],
        typical_ambience_layers=["wind_howl.ogg"],
        distant_sounds=["cathedral_bell", "blacksmith_hammer", "horse_whinny"],
        typical_foley=["boots_cobble", "cloth_awning", "cart_wheel", "coin_pouch"],
        typical_walla="market_bustle",
        typical_weather="open_air",
        typical_creatures=["pigeon_flock", "stray_dog"],
        estimated_rt60_ms=700,
        occlusion_barrier_hz=18000,
        default_absorption=0.45,
    ),
    "ancient_library": EnvironmentProfile(
        env_id="ancient_library",
        display_name="Ancient Library / Archive",
        category="indoor",
        default_surfaces=["polished_wood", "bookshelves", "wool_carpet"],
        typical_ambience_layers=["anoisesrc_room_tone"],
        distant_sounds=["distant_clock_chime", "high_window_creak"],
        typical_foley=["parchment_turn", "leather_tome_close", "quill_scratch", "soft_footsteps"],
        typical_walla=None,
        typical_weather="indoor_quiet",
        typical_creatures=[],
        estimated_rt60_ms=1400,
        occlusion_barrier_hz=800,
        default_absorption=0.70,
    ),
    "academy_classroom": EnvironmentProfile(
        env_id="academy_classroom",
        display_name="Academy Classroom",
        category="indoor",
        default_surfaces=["wood_benches", "chalkboard", "stone_walls"],
        typical_ambience_layers=["anoisesrc_room_tone"],
        distant_sounds=["hallway_footsteps", "distant_bell"],
        typical_foley=["chalk_click", "wooden_bench_shift", "parchment_rustle", "inkpot_clink"],
        typical_walla="classroom_mutter",
        typical_weather="indoor",
        typical_creatures=[],
        estimated_rt60_ms=1300,
        occlusion_barrier_hz=1200,
        default_absorption=0.50,
    ),

    # 4. Travel & Vehicles
    "horse_carriage_road": EnvironmentProfile(
        env_id="horse_carriage_road",
        display_name="Horse Carriage on High Road",
        category="travel_vehicle",
        default_surfaces=["wood_carriage", "leather_seats", "dirt_gravel_road"],
        typical_ambience_layers=["wind_howl.ogg"],
        distant_sounds=["thunder_horizon", "bird_call"],
        typical_foley=["carriage_rattle", "hoofbeat_rhythm", "leather_creak", "whip_crack"],
        typical_walla=None,
        typical_weather="open_wind",
        typical_creatures=["horses"],
        estimated_rt60_ms=250,
        occlusion_barrier_hz=1400,
        default_absorption=0.75,
    ),

    # 5. Modern & Suburban Environments
    "suburban_street_day": EnvironmentProfile(
        env_id="suburban_street_day",
        display_name="Suburban Street (Day)",
        category="settlement",
        default_surfaces=["asphalt", "pavement", "brick", "lawn"],
        typical_ambience_layers=["wind_howl.ogg"],
        distant_sounds=["distant_car_hum", "distant_dog_bark", "gentle_breeze"],
        typical_foley=["car_door", "footsteps_pavement", "gate_latch"],
        typical_walla=None,
        typical_weather="clear_day",
        typical_creatures=["suburban_birds"],
        estimated_rt60_ms=250,
        occlusion_barrier_hz=16000,
        default_absorption=0.85,
    ),
    "suburban_street_night": EnvironmentProfile(
        env_id="suburban_street_night",
        display_name="Quiet Suburban Street (Night)",
        category="settlement",
        default_surfaces=["asphalt", "pavement", "hedgerow", "brick"],
        typical_ambience_layers=["07042032.mp3", "forest_night_crickets.ogg"],
        distant_sounds=["distant_owl", "night_breeze", "distant_motorcycle"],
        typical_foley=["lighter_click", "cat_purr", "soft_footsteps"],
        typical_walla=None,
        typical_weather="night_breeze",
        typical_creatures=["owl", "cat"],
        estimated_rt60_ms=200,
        occlusion_barrier_hz=18000,
        default_absorption=0.90,
    ),
    "domestic_room": EnvironmentProfile(
        env_id="domestic_room",
        display_name="Domestic Living Room / Kitchen",
        category="indoor",
        default_surfaces=["carpet", "plaster_wall", "wood_table", "curtains"],
        typical_ambience_layers=["amb_castle_hall_hearth.wav"],
        distant_sounds=["clock_tick", "refrigerator_hum"],
        typical_foley=["cup_clink", "newspaper_rustle", "chair_shift", "door_open"],
        typical_walla=None,
        typical_weather="indoor_cozy",
        typical_creatures=[],
        estimated_rt60_ms=400,
        occlusion_barrier_hz=800,
        default_absorption=0.75,
    ),
    "office_commercial": EnvironmentProfile(
        env_id="office_commercial",
        display_name="Commercial Office / Busy Workplace",
        category="indoor",
        default_surfaces=["carpet_tile", "acoustic_tile_ceiling", "drywall", "glass"],
        typical_ambience_layers=["07039098.mp3"],
        distant_sounds=["typewriter_click", "phone_ring", "office_murmur"],
        typical_foley=["paper_shuffle", "chair_swivel", "door_shut"],
        typical_walla="office_whisper_walla",
        typical_weather="indoor_conditioned",
        typical_creatures=[],
        estimated_rt60_ms=550,
        occlusion_barrier_hz=1200,
        default_absorption=0.65,
    ),
    # 6. Ruins, Sci-Fi & Cyberpunk Environments
    "stone_ruins_exterior": EnvironmentProfile(
        env_id="stone_ruins_exterior",
        display_name="Crumbling Stone Ruins (Exterior)",
        category="outdoor_nature",
        default_surfaces=["cracked_granite", "rubble", "overgrown_weeds", "dry_dirt"],
        typical_ambience_layers=["wind_howl.ogg", "amb_castle_hall_hearth.wav"],
        distant_sounds=["distant_crow_caw", "stone_crumble", "wind_gust"],
        typical_foley=["boots_gravel", "rubble_kick", "scabbard_creak", "torch_flicker"],
        typical_walla=None,
        typical_weather="chilly_wind",
        typical_creatures=["crows", "ravens", "monster_growl"],
        estimated_rt60_ms=450,
        occlusion_barrier_hz=16000,
        default_absorption=0.75,
    ),
    "spaceship_bridge": EnvironmentProfile(
        env_id="spaceship_bridge",
        display_name="Spaceship Command Bridge",
        category="indoor",
        default_surfaces=["metal_bulkhead", "composite_deck", "console_glass"],
        typical_ambience_layers=["anoisesrc_room_tone"],
        distant_sounds=["warp_core_pulse", "distant_airlock_cycle"],
        typical_foley=["console_chirp", "comm_beep", "hydraulic_door", "boot_deck"],
        typical_walla="crew_chatter",
        typical_weather="indoor_conditioned",
        typical_creatures=[],
        estimated_rt60_ms=450,
        occlusion_barrier_hz=800,
        default_absorption=0.60,
    ),
    "cyberpunk_alley_rain": EnvironmentProfile(
        env_id="cyberpunk_alley_rain",
        display_name="Cyberpunk Alley in Rain",
        category="settlement",
        default_surfaces=["wet_asphalt", "grate_metal", "brick"],
        typical_ambience_layers=["rain_gentle.ogg", "wind_howl.ogg"],
        distant_sounds=["distant_siren", "neon_hum", "flying_traffic"],
        typical_foley=["puddle_splash", "cyberware_whirr", "trash_kick"],
        typical_walla="distant_crowd",
        typical_weather="acid_rain",
        typical_creatures=[],
        estimated_rt60_ms=350,
        occlusion_barrier_hz=14000,
        default_absorption=0.80,
    ),
    "room_tone": EnvironmentProfile(
        env_id="room_tone",
        display_name="Neutral Room Tone",
        category="indoor",
        default_surfaces=["wood", "plaster", "carpet"],
        typical_ambience_layers=[],
        distant_sounds=[],
        typical_foley=["wood_creak", "cloth_rustle"],
        typical_walla=None,
        typical_weather="sheltered",
        typical_creatures=[],
        estimated_rt60_ms=450,
        occlusion_barrier_hz=1000,
        default_absorption=0.70,
    ),
}


class EnvironmentProfileRegistry:
    """
    Registry and resolver for reusable environment profiles.
    Allows project-specific custom profiles while supplying standard canonical defaults.
    """

    def __init__(self, custom_profiles: Optional[Dict[str, EnvironmentProfile]] = None):
        self._profiles: Dict[str, EnvironmentProfile] = dict(STANDARD_ENVIRONMENTS)
        if custom_profiles:
            self._profiles.update(custom_profiles)

    def register_profile(self, profile: EnvironmentProfile) -> None:
        """Register or overwrite an environment profile."""
        self._profiles[profile.env_id.lower().strip()] = profile

    def get_profile(self, env_id: str) -> Optional[EnvironmentProfile]:
        """Fetch environment profile by exact or fuzzy slug."""
        if not env_id:
            return None
        q = env_id.lower().strip()
        if q in self._profiles:
            return self._profiles[q]

        # Fuzzy substring match
        for key, p in self._profiles.items():
            if key in q or q in key:
                return p
        return None

    def resolve_from_text(self, text_or_tags: str) -> EnvironmentProfile:
        """
        Infers the best matching environment profile from narrative text, location string,
        or acoustic environment tags with zero hallucinations.
        """
        raw = text_or_tags.lower()

        # Modern / Suburban / Domestic keyword mapping rules
        if any(w in raw for w in ("suburban", "driveway", "pavement", "sidewalk", "street", "road", "suburb")):
            if any(nw in raw for nw in ("night", "dark", "midnight", "crickets", "evening", "रास्ता", "रात")):
                return self._profiles["suburban_street_night"]
            return self._profiles["suburban_street_day"]
        if any(w in raw for w in ("office", "desk", "cubicle", "workplace", "corporate", "दफ्तर")):
            return self._profiles["office_commercial"]
        if any(w in raw for w in ("living room", "kitchen", "breakfast", "table", "chair", "house", "home", "bedroom", "कमरा", "घर", "मेज")):
            return self._profiles["domestic_room"]

        # Sci-Fi / Cyberpunk keyword mapping rules
        if any(w in raw for w in ("spaceship", "bridge", "warp", "airlock", "bulkhead", "console", "orbit", "starship")):
            return self._profiles["spaceship_bridge"]
        if any(w in raw for w in ("cyberpunk", "neon", "cyber", "acid rain", "implant", "megacorp", "alleyway")):
            return self._profiles["cyberpunk_alley_rain"]

        # Fantasy / Historical / Period keyword mapping rules
        if any(w in raw for w in ("ruins", "stone_ruins", "rubble", "crumbling", "खंडहर", "मलबा", "सुराख़")):
            return self._profiles["stone_ruins_exterior"]
        if any(w in raw for w in ("tavern", "inn", "pub", "bar", "tankard", "brawl", "मदिरालय", "सराय")):
            return self._profiles["tavern_interior"]
        if any(w in raw for w in ("crypt", "catacomb", "tomb", "sarcophagus", "necropolis", "तहखाना")):
            return self._profiles["crypt_catacomb"]
        if any(w in raw for w in ("swamp", "bog", "marsh", "mire", "wetland", "दलदल")):
            return self._profiles["swamp_marsh_night"]
        if any(w in raw for w in ("blizzard", "snow", "mountain_pass", "avalanche", "glacier", "बर्फ़")):
            return self._profiles["mountain_pass_blizzard"]
        if any(w in raw for w in ("forest", "woods", "trees", "canopy", "grove", "wilderness", "जंगल")):
            return self._profiles["deep_forest_night"]
        if any(w in raw for w in ("market", "bazaar", "square", "stalls", "plaza", "बाज़ार")):
            return self._profiles["city_market_square"]
        if any(w in raw for w in ("corridor", "hallway", "dungeon", "passage", "गलियारा")):
            return self._profiles["castle_stone_corridor"]
        if any(w in raw for w in ("great hall", "throne", "castle_hall", "banquet", "दरबार")):
            return self._profiles["castle_great_hall"]
        if any(w in raw for w in ("bedchamber", "chamber", "study")):
            return self._profiles["castle_bedchamber"]
        if any(w in raw for w in ("library", "archive", "scrolls", "tomes", "ग्रंथालय")):
            return self._profiles["ancient_library"]
        if any(w in raw for w in ("classroom", "lecture", "academy", "school", "कक्षा")):
            return self._profiles["academy_classroom"]
        if any(w in raw for w in ("carriage", "coach", "wagon", "cart", "बग्गी", "गाड़ी")):
            return self._profiles["horse_carriage_road"]

        # Default fallback - neutral room tone (never force suburban domestic room)
        return self._profiles.get("room_tone", self._profiles["domestic_room"])

    def to_world_acoustic_profile(self, env_id: str) -> WorldAcousticProfile:
        """Converts an EnvironmentProfile into a WorldAcousticProfile for SonicBible interoperability."""
        prof = self.get_profile(env_id) or self._profiles.get("room_tone", self._profiles["domestic_room"])
        space_type = "indoor_large" if prof.category == "indoor" else ("subterranean" if prof.category == "subterranean" else "outdoor_open")
        return WorldAcousticProfile(
            env_id=prof.env_id,
            display_name=prof.display_name,
            space_type=space_type,
            estimated_rt60_ms=prof.estimated_rt60_ms,
            high_freq_damping=prof.default_absorption,
            early_reflections_level_db=-14.0,
            reverb_tail_level_db=-18.0,
            ir_preset="hall" if prof.estimated_rt60_ms > 1800 else "room",
        )


_GLOBAL_REGISTRY: Optional[EnvironmentProfileRegistry] = None

# Ergonomic alias
EnvironmentRegistry = EnvironmentProfileRegistry

def get_environment_registry() -> EnvironmentProfileRegistry:
    """Returns singleton instance of EnvironmentProfileRegistry."""
    global _GLOBAL_REGISTRY
    if _GLOBAL_REGISTRY is None:
        _GLOBAL_REGISTRY = EnvironmentProfileRegistry()
    return _GLOBAL_REGISTRY
