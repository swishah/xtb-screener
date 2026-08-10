"""
Warstwa trwałości: codzienne migawki (snapshoty) wyników skanu zapisywane
do SQLite. Plik bazy leży w data/history.db i jest commitowany do repo przez
GitHub Actions (patrz .github/workflows/daily_scan.yml) — Streamlit Community
Cloud ma ulotny filesystem, więc "prawdziwa" trwałość danych bierze się z
tego, że baza jest wersjonowana w git, a appka tylko ją czyta.
"""
from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "history.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    scan_date TEXT NOT NULL,
    ticker TEXT NOT NULL,
    payload TEXT NOT NULL,   -- JSON-serialized row from scanner.analyze_ticker
    PRIMARY KEY (scan_date, ticker)
);
CREATE INDEX IF NOT EXISTS idx_snapshots_ticker ON snapshots(ticker);
CREATE INDEX IF NOT EXISTS idx_snapshots_date ON snapshots(scan_date);

CREATE TABLE IF NOT EXISTS watchlist (
    ticker TEXT PRIMARY KEY,
    note TEXT,
    added_date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS preferences (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    return conn


def save_snapshot(scan_date: str, rows: list[dict]) -> None:
    import json
    conn = get_conn()
    with conn:
        conn.executemany(
            "INSERT OR REPLACE INTO snapshots (scan_date, ticker, payload) VALUES (?, ?, ?)",
            [(scan_date, r["Ticker"], json.dumps(r, default=str)) for r in rows],
        )
    conn.close()


def list_dates() -> list[str]:
    conn = get_conn()
    dates = [r[0] for r in conn.execute("SELECT DISTINCT scan_date FROM snapshots ORDER BY scan_date DESC")]
    conn.close()
    return dates


def load_snapshot(scan_date: str) -> pd.DataFrame:
    import json
    conn = get_conn()
    rows = conn.execute("SELECT payload FROM snapshots WHERE scan_date = ?", (scan_date,)).fetchall()
    conn.close()
    return pd.DataFrame([json.loads(r[0]) for r in rows])


def load_latest() -> pd.DataFrame:
    dates = list_dates()
    if not dates:
        return pd.DataFrame()
    return load_snapshot(dates[0])


def load_ticker_history(ticker: str) -> pd.DataFrame:
    import json
    conn = get_conn()
    rows = conn.execute(
        "SELECT scan_date, payload FROM snapshots WHERE ticker = ? ORDER BY scan_date",
        (ticker,),
    ).fetchall()
    conn.close()
    records = []
    for scan_date, payload in rows:
        rec = json.loads(payload)
        rec["scan_date"] = scan_date
        records.append(rec)
    return pd.DataFrame(records)


def load_all_snapshots() -> pd.DataFrame:
    """
    Wszystkie migawki naraz, w jednej długiej tabeli (kolumna scan_date
    identyfikuje dzień). Podstawa backtestu strategii — pozwala policzyć,
    co by było, gdyby kupić TOP N wg danego score'a w dniu X i sprzedać
    K migawek później.
    """
    import json
    conn = get_conn()
    rows = conn.execute("SELECT scan_date, payload FROM snapshots ORDER BY scan_date").fetchall()
    conn.close()
    records = []
    for scan_date, payload in rows:
        rec = json.loads(payload)
        rec["scan_date"] = scan_date
        records.append(rec)
    return pd.DataFrame(records)


def add_to_watchlist(ticker: str, note: str = "") -> None:
    conn = get_conn()
    with conn:
        conn.execute(
            "INSERT INTO watchlist (ticker, note, added_date) VALUES (?, ?, ?) "
            "ON CONFLICT(ticker) DO UPDATE SET note = excluded.note",
            (ticker, note, date.today().isoformat()),
        )
    conn.close()


def update_watchlist_note(ticker: str, note: str) -> None:
    conn = get_conn()
    with conn:
        conn.execute("UPDATE watchlist SET note = ? WHERE ticker = ?", (note, ticker))
    conn.close()


def remove_from_watchlist(ticker: str) -> None:
    conn = get_conn()
    with conn:
        conn.execute("DELETE FROM watchlist WHERE ticker = ?", (ticker,))
    conn.close()


def load_watchlist() -> pd.DataFrame:
    conn = get_conn()
    rows = conn.execute(
        "SELECT ticker, note, added_date FROM watchlist ORDER BY added_date DESC"
    ).fetchall()
    conn.close()
    return pd.DataFrame(rows, columns=["Ticker", "Notatka", "Dodano"])


def get_preference(key: str, default=None):
    import json
    conn = get_conn()
    row = conn.execute("SELECT value FROM preferences WHERE key = ?", (key,)).fetchone()
    conn.close()
    if row is None:
        return default
    try:
        return json.loads(row[0])
    except Exception:  # noqa: BLE001
        return default


def set_preference(key: str, value) -> None:
    import json
    conn = get_conn()
    with conn:
        conn.execute(
            "INSERT INTO preferences (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, json.dumps(value)),
        )
    conn.close()


def delete_preference(key: str) -> None:
    conn = get_conn()
    with conn:
        conn.execute("DELETE FROM preferences WHERE key = ?", (key,))
    conn.close()
