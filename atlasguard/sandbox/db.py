"""Sandbox bank: a local SQLite database with SIMULATED accounts.

No real money or real bank is ever touched. Replace the seed data with your own
scenario by editing `seed()`; everything else reads from the database.

v2 additions: payment history (`payments`), upcoming bills (`obligations`) and a
tamper-evident audit log (each row stores the hash of the previous row).

v2.1 fix (Windows): every `with conn() as c:` block now commits/rolls back AND
closes the connection, so the database file is never left locked.
"""
import datetime as dt
import gc
import hashlib
import os
import random
import sqlite3


def db_path() -> str:
    return os.environ.get("AG_DB", "atlasguard.db")


class _AutoCloseConnection(sqlite3.Connection):
    """`with conn() as c:` commits (or rolls back) and then CLOSES the connection."""

    def __exit__(self, exc_type, exc, tb):
        try:
            return super().__exit__(exc_type, exc, tb)  # commit or rollback
        finally:
            self.close()


def conn() -> sqlite3.Connection:
    c = sqlite3.connect(db_path(), factory=_AutoCloseConnection)
    c.row_factory = sqlite3.Row
    return c


SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts(
  id TEXT PRIMARY KEY, owner TEXT, currency TEXT, balance REAL);
CREATE TABLE IF NOT EXISTS transactions(
  id INTEGER PRIMARY KEY AUTOINCREMENT, account_id TEXT, ts TEXT,
  amount REAL, category TEXT, memo TEXT);
CREATE TABLE IF NOT EXISTS beneficiaries(
  id TEXT PRIMARY KEY, name TEXT, bank TEXT, iban TEXT, currency TEXT, verified INTEGER);
CREATE TABLE IF NOT EXISTS pending_transfers(
  id TEXT PRIMARY KEY, account_id TEXT, beneficiary_id TEXT, provider TEXT,
  send_amount REAL, target_amount REAL, target_currency TEXT, fee REAL,
  token TEXT, status TEXT, created_ts TEXT);
CREATE TABLE IF NOT EXISTS audit_log(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, actor TEXT, tool TEXT,
  tier INTEGER, verdict TEXT, detail TEXT, prev_hash TEXT, hash TEXT);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS payments(
  id INTEGER PRIMARY KEY AUTOINCREMENT, account_id TEXT, beneficiary_id TEXT,
  iban TEXT, amount REAL, currency TEXT, ts TEXT, source TEXT);
CREATE TABLE IF NOT EXISTS obligations(
  id INTEGER PRIMARY KEY AUTOINCREMENT, account_id TEXT, beneficiary_id TEXT,
  label TEXT, amount REAL, currency TEXT, due_date TEXT, source TEXT, status TEXT);
"""


def now() -> dt.datetime:
    return dt.datetime.now().replace(microsecond=0)


def _wipe_all_tables() -> None:
    """Fallback for Windows: if the file cannot be deleted, drop every table instead."""
    c = sqlite3.connect(db_path())
    try:
        names = [r[0] for r in c.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        for n in names:
            c.execute(f'DROP TABLE IF EXISTS "{n}"')
        c.commit()
    finally:
        c.close()


def init_db(reset: bool = False, seed_data: bool = True) -> None:
    if reset and os.path.exists(db_path()):
        gc.collect()  # drop any unreferenced connections still holding the file
        try:
            os.remove(db_path())
        except PermissionError:
            _wipe_all_tables()
    with conn() as c:
        c.executescript(SCHEMA)
        has = c.execute("SELECT COUNT(*) n FROM accounts").fetchone()["n"]
    if seed_data and not has:
        seed()


def seed(rng_seed: int = 7) -> None:
    rnd = random.Random(rng_seed)
    today = now()
    uni_iban = "DE89 3704 0044 0532 0130 00"
    landlord_iban = "DE02 1203 0000 0000 2020 51"
    with conn() as c:
        c.execute("INSERT INTO accounts VALUES('ACC-001','Student (demo)','PKR',?)", (1_450_000.0,))
        c.executemany(
            "INSERT INTO beneficiaries VALUES(?,?,?,?,?,?)",
            [
                ("BEN-UNI", "Example University Bursar", "Example Bank AG", uni_iban, "EUR", 1),
                ("BEN-LANDLORD", "Mr. Landlord Example", "Example Savings", landlord_iban, "EUR", 1),
            ],
        )
        c.executemany(
            "INSERT OR REPLACE INTO settings VALUES(?,?)",
            [("daily_limit_pkr", "2000000"), ("new_beneficiary_limit_pkr", "500000")],
        )
        # Payment HISTORY (kept separate from `transactions` so it does not distort the
        # budget forecast): tuition every ~30 days, rent every ~30 days, in EUR.
        for days_ago, ben, iban, amt in [
            (85, "BEN-UNI", uni_iban, 3000.0), (55, "BEN-UNI", uni_iban, 3000.0),
            (25, "BEN-UNI", uni_iban, 3000.0),
            (70, "BEN-LANDLORD", landlord_iban, 400.0), (40, "BEN-LANDLORD", landlord_iban, 400.0),
            (10, "BEN-LANDLORD", landlord_iban, 400.0),
        ]:
            ts = (today - dt.timedelta(days=days_ago)).isoformat()
            c.execute("INSERT INTO payments(account_id,beneficiary_id,iban,amount,currency,ts,source) "
                      "VALUES(?,?,?,?,?,?,?)", ("ACC-001", ben, iban, amt, "EUR", ts, "history"))
        # ~100 days of plausible activity (PKR): monthly family remittance in,
        # rent + utilities out, daily small spending.
        for d in range(100, 0, -1):
            ts = today - dt.timedelta(days=d)
            if ts.day == 1:
                c.execute("INSERT INTO transactions(account_id,ts,amount,category,memo) VALUES(?,?,?,?,?)",
                          ("ACC-001", ts.isoformat(), 300_000, "remittance_in", "Family support"))
                c.execute("INSERT INTO transactions(account_id,ts,amount,category,memo) VALUES(?,?,?,?,?)",
                          ("ACC-001", ts.isoformat(), -110_000, "rent", "Monthly rent"))
            if rnd.random() < 0.8:
                amt = -round(rnd.uniform(1_500, 9_000), 2)
                cat = rnd.choice(["groceries", "transport", "food", "misc"])
                c.execute("INSERT INTO transactions(account_id,ts,amount,category,memo) VALUES(?,?,?,?,?)",
                          ("ACC-001", ts.isoformat(), amt, cat, cat))


def get_setting(key: str, default: str = "0") -> str:
    with conn() as c:
        r = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return r["value"] if r else default


# ---------------- tamper-evident audit log ----------------
def _hash(prev: str, ts: str, actor: str, tool: str, tier: int, verdict: str, detail: str) -> str:
    raw = "|".join([prev or "", ts, actor, tool, str(tier), verdict, detail])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def audit(actor: str, tool: str, tier: int, verdict: str, detail: str) -> None:
    ts = now().isoformat()
    detail = (detail or "")[:2000]
    with conn() as c:
        last = c.execute("SELECT hash FROM audit_log ORDER BY id DESC LIMIT 1").fetchone()
        prev = (last["hash"] if last and last["hash"] else "")
        h = _hash(prev, ts, actor, tool, tier, verdict, detail)
        c.execute("INSERT INTO audit_log(ts,actor,tool,tier,verdict,detail,prev_hash,hash) "
                  "VALUES(?,?,?,?,?,?,?,?)", (ts, actor, tool, tier, verdict, detail, prev, h))


def verify_audit_log() -> dict:
    """Recompute the hash chain. Any edited, deleted or reordered row breaks it."""
    with conn() as c:
        rows = c.execute("SELECT * FROM audit_log ORDER BY id").fetchall()
    prev = ""
    for r in rows:
        expected = _hash(prev, r["ts"], r["actor"], r["tool"], r["tier"], r["verdict"], r["detail"])
        if (r["prev_hash"] or "") != prev or r["hash"] != expected:
            return {"ok": False, "entries": len(rows), "first_bad_id": r["id"]}
        prev = r["hash"]
    return {"ok": True, "entries": len(rows), "first_bad_id": None}