"""
Warstwa trwałości: codzienne migawki (snapshoty) wyników skanu zapisywane
do SQLite. Plik bazy leży w data/history.db i jest commitowany do repo przez
GitHub Actions (patrz .github/workflows/daily_scan.yml) — Streamlit Community
Cloud ma ulotny filesystem, więc "prawdziwa" trwałość danych bierze się z
tego, że baza jest wersjonowana w git, a appka tylko ją czyta.
"""
from __future__ import annotations

import sqlite3
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
