from audiobook_factory.sound_bank import get_sound_bank

bank = get_sound_bank()
spot_queries = [
    "igni", "aard", "quen", "axii", "yrden",
    "striga", "ghoul", "wolf",
    "sword draw", "sword clash", "body thud", "armor clank",
    "crypt", "castle hall", "bog swamp", "blizzard"
]

all_pass = True
for q in spot_queries:
    res = bank.resolve_sound(q)
    name = res.name if res else "NONE"
    exists = res.exists() if res else False
    status = "OK" if exists else "FAIL"
    if not exists:
        all_pass = False
    print(f"[{status}] {q:15} -> {name}")

print("\nSpot-check overall status:", "ALL PASSED!" if all_pass else "FAILURES DETECTED!")
