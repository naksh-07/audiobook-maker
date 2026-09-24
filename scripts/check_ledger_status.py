import sqlite3
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
conn = sqlite3.connect(ROOT_DIR / "audiobooks" / "key_pool_state.db")
c = conn.cursor()

print("Status groups:", c.execute("SELECT status, count(key_hash), sum(total_calls_today) FROM key_quota_ledger GROUP BY status").fetchall())
print("\nRecent 10 active keys:")
for r in c.execute("SELECT key_preview, total_calls_today, failed_calls_today, last_error, last_used FROM key_quota_ledger WHERE status='ACTIVE' ORDER BY last_used DESC LIMIT 10").fetchall():
    print(r)
