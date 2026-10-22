"""Journal des événements (SQLite)."""
import sqlite3
import threading
import time

from .i18n import search_terms, to_key
from .settings import DATA


class EventStore:
    def __init__(self):
        self.db = sqlite3.connect(str(DATA / "events.db"), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                camera_id TEXT, camera_name TEXT,
                type TEXT NOT NULL,          -- weapon | face | person
                label TEXT, confidence REAL,
                upper TEXT, lower TEXT,
                track_id INTEGER,
                snapshot TEXT
            )""")
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_ev_ts ON events(ts)")
        # Colonnes ajoutées après coup (type de vêtements) : migration des journaux existants
        existing = {r["name"] for r in self.db.execute("PRAGMA table_info(events)")}
        for col, typ in (("upper_type", "TEXT"), ("lower_type", "TEXT"), ("value", "INTEGER")):
            if col not in existing:
                self.db.execute(f"ALTER TABLE events ADD COLUMN {col} {typ}")
        self._to_neutral_keys()
        self.db.commit()

    def _to_neutral_keys(self):
        """Anciens journaux en français (« bleu », « jean », « pistolet ») -> clés neutres (« blue »...)."""
        for col in ("upper", "lower", "upper_type", "lower_type"):
            for (val,) in self.db.execute(f"SELECT DISTINCT {col} FROM events WHERE {col} IS NOT NULL").fetchall():
                if to_key(val) != val:
                    self.db.execute(f"UPDATE events SET {col}=? WHERE {col}=?", (to_key(val), val))
        rows = self.db.execute("SELECT DISTINCT label FROM events WHERE type IN ('weapon', 'person') "
                               "OR (type='face' AND label='Inconnu')").fetchall()
        for (label,) in rows:
            new = ", ".join(to_key(part) for part in (label or "").split(", "))
            if label and new != label:
                self.db.execute("UPDATE events SET label=? WHERE label=? AND type IN ('weapon', 'person', 'face')",
                                (new, label))

    def add(self, **ev) -> int:
        ev.setdefault("ts", time.time())
        cols = ", ".join(ev)
        marks = ", ".join("?" for _ in ev)
        with self.lock:
            cur = self.db.execute(f"INSERT INTO events ({cols}) VALUES ({marks})", list(ev.values()))
            self.db.commit()
            return cur.lastrowid

    def set_snapshot(self, ev_id: int, name: str):
        with self.lock:
            self.db.execute("UPDATE events SET snapshot=? WHERE id=?", (name, ev_id))
            self.db.commit()

    def query(self, type=None, camera_id=None, upper=None, lower=None, label=None,
              after_id=None, since=None, limit=200, upper_type=None, lower_type=None):
        sql, args = "SELECT * FROM events WHERE 1=1", []
        for col, val in (("type", type), ("camera_id", camera_id), ("upper", upper), ("lower", lower),
                         ("upper_type", upper_type), ("lower_type", lower_type)):
            if val:
                sql += f" AND {col}=?"
                args.append(val)
        if label:
            # Recherche dans toutes les langues : « pistool » ou « pistolet » trouvent « handgun »
            terms = search_terms(label)
            sql += " AND (" + " OR ".join("label LIKE ?" for _ in terms) + ")"
            args += [f"%{t}%" for t in terms]
        if after_id is not None:
            sql += " AND id>?"
            args.append(after_id)
        if since is not None:
            sql += " AND ts>=?"
            args.append(since)
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(min(int(limit), 1000))
        with self.lock:
            return [dict(r) for r in self.db.execute(sql, args)]

    def purge_before(self, ts: float) -> list[str]:
        """Supprime les événements antérieurs à `ts` ; renvoie les captures à effacer."""
        with self.lock:
            snaps = [r["snapshot"] for r in self.db.execute(
                "SELECT snapshot FROM events WHERE ts<? AND snapshot IS NOT NULL", (ts,))]
            self.db.execute("DELETE FROM events WHERE ts<?", (ts,))
            self.db.commit()
        return snaps

    def clear(self):
        with self.lock:
            self.db.execute("DELETE FROM events")
            self.db.commit()
