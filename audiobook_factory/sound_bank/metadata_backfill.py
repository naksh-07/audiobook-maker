#!/usr/bin/env python3
"""
Audiobook Factory - BBC Sound Effects Metadata Backfill Engine.
Deterministically extracts physical acoustic properties (action_type, exciter, resonator)
from raw archive titles and descriptions to make the 32,000+ BBC sound catalog
100% discoverable by physical semantic queries.
"""

from __future__ import annotations
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, TYPE_CHECKING

from audiobook_factory.logger import logger

if TYPE_CHECKING:
    from audiobook_factory.sound_bank import SoundBank


ACTION_PATTERNS: List[Tuple[str, str]] = [
    (r"\b(footstep|footsteps|walk|walking|steps|tread|stride)\b", "walk"),
    (r"\b(running|runs?|sprint|jog)\b", "run"),
    (r"\b(opening|opens?|unlatch)\b", "open"),
    (r"\b(closing|closes?|shut)\b", "close"),
    (r"\b(slam|slamming|slams?|bang)\b", "slam"),
    (r"\b(creak|creaking|creaks?|squeak)\b", "creak"),
    (r"\b(pour|pouring|pours?|spill)\b", "pour"),
    (r"\b(stir|stirring|stirs?)\b", "stir"),
    (r"\b(clink|clinking|clinks?|chime)\b", "clink"),
    (r"\b(rustle|rustling|rustles?)\b", "rustle"),
    (r"\b(crackle|crackling|crackles?)\b", "crackle"),
    (r"\b(drip|dripping|drips?|droplet)\b", "drip"),
    (r"\b(splash|splashing|splashes?)\b", "splash"),
    (r"\b(cough|coughing|coughs?)\b", "cough"),
    (r"\b(laugh|laughing|laughs?|laughter|giggle)\b", "laugh"),
    (r"\b(crying|cries?|sob|sobbing|weep)\b", "cry"),
    (r"\b(bark|barking|barks?|howl)\b", "bark"),
    (r"\b(knock|knocking|knocks?|tap|tapping)\b", "knock"),
    (r"\b(strike|strikes?|hit|impact|thud)\b", "strike"),
    (r"\b(approach|approaching|approaches?)\b", "approach"),
    (r"\b(depart|departing|departs?)\b", "depart"),
    (r"\b(tick|ticking|ticks?)\b", "tick"),
    (r"\b(rumble|rumbling|rumbles?)\b", "rumble"),
    (r"\b(hum|humming|hums?)\b", "hum"),
    (r"\b(scrape|scraping|scrapes?)\b", "scrape"),
    (r"\b(whistle|whistling|whistles?)\b", "whistle"),
    (r"\b(slide|sliding|slides?)\b", "slide"),
    (r"\b(rattle|rattling|rattles?)\b", "rattle"),
    (r"\b(ambient|ambience|atmosphere|background|bed)\b", "ambient_bed"),
]

EXCITER_PATTERNS: List[Tuple[str, str]] = [
    (r"\b(footstep|footsteps|shoes?|boots?|feet|leather|heels?)\b", "leather"),
    (r"\b(wood|wooden|timber|board|plank)\b", "wood"),
    (r"\b(water|rain|stream|river|waves?|drizzle|shower)\b", "water"),
    (r"\b(glass|bottle|window|pane|mirror)\b", "glass"),
    (r"\b(metal|iron|steel|tin|brass|metallic|chain|key)\b", "metal"),
    (r"\b(paper|page|book|sheet|parchment|letter)\b", "paper"),
    (r"\b(cloth|fabric|coat|dress|jacket|trousers|textile)\b", "cloth"),
    (r"\b(fire|flame|hearth|campfire|bonfire|embers)\b", "fire"),
    (r"\b(wind|breeze|gale|draft|gust)\b", "air"),
    (r"\b(ceramic|porcelain|china|cup|mug|plate|saucer|dish)\b", "ceramic"),
    (r"\b(engine|motor|car|vehicle|bus|truck|traffic)\b", "motor"),
    (r"\b(clock|watch|pendulum)\b", "clock"),
    (r"\b(bell|chime|doorbell)\b", "bell"),
    (r"\b(bird|birds|gull|sparrow|crow|pigeon|owl)\b", "bird"),
    (r"\b(dog|dogs|canine|hound|puppy)\b", "dog"),
    (r"\b(cat|cats|kitten|feline)\b", "cat"),
    (r"\b(horse|horses|hooves|trot|gallop)\b", "horse"),
]

RESONATOR_PATTERNS: List[Tuple[str, str]] = [
    (r"\b(wood|wooden|floor|hardwood|floorboards?|parquet)\b", "wood"),
    (r"\b(gravel|pebbles?|stones?|rocky)\b", "gravel"),
    (r"\b(carpet|rug|matting)\b", "carpet"),
    (r"\b(stone|cobblestones?|concrete|asphalt|pavement|sidewalk|street)\b", "stone"),
    (r"\b(tile|tiles|tiled|marble)\b", "tile"),
    (r"\b(grass|lawn|turf|meadow|field)\b", "grass"),
    (r"\b(mud|muddy|dirt|earth)\b", "mud"),
    (r"\b(puddle|shallow water|water)\b", "water"),
    (r"\b(room|interior|hall|corridor|bedroom|kitchen|office)\b", "room"),
    (r"\b(exterior|outdoor|forest|woods|park|beach)\b", "exterior"),
]


class BBCMetadataBackfillEngine:
    """Extracts physical and dramatic metadata for BBC Sound Effects catalog entries."""

    @staticmethod
    def extract_physical_tags(title: str, description: str, filename: str) -> Dict[str, str]:
        """
        Deterministically inspects title, description, and filename to extract
        action_type, exciter, and resonator.
        """
        combined = f"{title or ''} {description or ''} {filename or ''}".lower()
        extracted: Dict[str, str] = {}

        # 1. Action type extraction
        for pattern, action in ACTION_PATTERNS:
            if re.search(pattern, combined, re.IGNORECASE):
                extracted["action_type"] = action
                break

        # 2. Exciter extraction
        for pattern, exciter in EXCITER_PATTERNS:
            if re.search(pattern, combined, re.IGNORECASE):
                extracted["exciter"] = exciter
                break

        # 3. Resonator extraction
        for pattern, resonator in RESONATOR_PATTERNS:
            if re.search(pattern, combined, re.IGNORECASE):
                extracted["resonator"] = resonator
                break

        return extracted

    @classmethod
    def run_backfill(
        cls,
        bank: Optional[SoundBank] = None,
        dry_run: bool = False,
        limit: Optional[int] = None,
        batch_size: int = 1000,
    ) -> Dict[str, Any]:
        """
        Scans BBC Sound Effects tracks in sound_catalog and updates empty physical columns.
        """
        if bank is None:
            from audiobook_factory.sound_bank import get_sound_bank
            bank = get_sound_bank()
        stats = {
            "total_candidates": 0,
            "updated_count": 0,
            "actions_assigned": 0,
            "exciters_assigned": 0,
            "resonators_assigned": 0,
            "dry_run": dry_run,
        }

        query = """
            SELECT id, filename, title, description, exciter, resonator, action_type
            FROM sound_catalog
            WHERE source_collection = 'BBC_Sound_Effects'
              AND (exciter = '' OR exciter IS NULL OR action_type = '' OR action_type IS NULL)
        """
        if limit:
            query += f" LIMIT {int(limit)}"

        with bank._get_conn() as conn:
            cur = conn.execute(query)
            rows = cur.fetchall()
            stats["total_candidates"] = len(rows)

            updates: List[Tuple[str, str, str, int]] = []
            for row in rows:
                row_id = row["id"]
                fn = row["filename"] or ""
                title = row["title"] or ""
                desc = row["description"] or ""
                curr_exc = row["exciter"] or ""
                curr_res = row["resonator"] or ""
                curr_act = row["action_type"] or ""

                tags = cls.extract_physical_tags(title, desc, fn)

                new_act = curr_act or tags.get("action_type", "")
                new_exc = curr_exc or tags.get("exciter", "")
                new_res = curr_res or tags.get("resonator", "")

                if new_act != curr_act or new_exc != curr_exc or new_res != curr_res:
                    if new_act and not curr_act:
                        stats["actions_assigned"] += 1
                    if new_exc and not curr_exc:
                        stats["exciters_assigned"] += 1
                    if new_res and not curr_res:
                        stats["resonators_assigned"] += 1

                    updates.append((new_exc, new_res, new_act, row_id))

            stats["updated_count"] = len(updates)

            if not dry_run and updates:
                logger.info(f"Applying {len(updates)} metadata updates to sound_catalog...")
                for i in range(0, len(updates), batch_size):
                    batch = updates[i : i + batch_size]
                    conn.executemany(
                        """
                        UPDATE sound_catalog
                        SET exciter = ?, resonator = ?, action_type = ?
                        WHERE id = ?
                        """,
                        batch,
                    )
                    conn.commit()

        if not dry_run and stats["updated_count"] > 0:
            logger.info("Rebuilding SQLite FTS5 search index...")
            bank.rebuild_search_index()

        return stats
