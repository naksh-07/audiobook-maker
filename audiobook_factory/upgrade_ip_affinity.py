import sqlite3

def upgrade_main_sound_bank():
    conn = sqlite3.connect("audiobooks/sound_bank/sound_bank.db")
    c = conn.cursor()
    cols = {col[1] for col in c.execute("PRAGMA table_info(sound_catalog)").fetchall()}

    new_cols = [
        ("franchise_affinity", "TEXT DEFAULT 'generic'"),
        ("lore_tags", "TEXT DEFAULT ''"),
        ("ip_priority", "REAL DEFAULT 0.0"),
    ]
    for col_name, col_type in new_cols:
        if col_name not in cols:
            conn.execute(f"ALTER TABLE sound_catalog ADD COLUMN {col_name} {col_type};")
            print(f"Added column {col_name} to sound_catalog in sound_bank.db")

    # Tag Witcher 3 OST
    c.execute("""
        UPDATE sound_catalog
        SET franchise_affinity = 'the_witcher',
            lore_tags = 'geralt, yennefer, ciri, novigrad, skellige, velen, kaer_morhen, witcher_ost',
            ip_priority = 1.0
        WHERE source_collection = 'Witcher3_OST' OR filepath LIKE '%witcher3_ost%'
    """)
    tagged = c.rowcount
    conn.commit()
    conn.close()
    print(f"Successfully tagged {tagged} Witcher 3 OST tracks in main sound bank with franchise_affinity = 'the_witcher'!")

if __name__ == "__main__":
    upgrade_main_sound_bank()
