"""
Warstwa trwałości: codzienne migawki (snapshoty) wyników skanu.

DWA TRYBY PRACY, wybierane automatycznie:

1. ZDALNY (Turso/libSQL) — gdy ustawione są zmienne środowiskowe
   TURSO_DATABASE_URL i TURSO_AUTH_TOKEN. To tryb produkcyjny.
2. LOKALNY (plik data/history.db) — gdy tych zmiennych nie ma. Używany przy
   pracy na własnym komputerze i jako zabezpieczenie, gdyby usługa zdalna
   była niedostępna.

DLACZEGO ZDALNY: wcześniej plik bazy był commitowany do repo przez GitHub
Actions, bo Streamlit Community Cloud ma ulotny filesystem. To rozwiązanie
miało twardy kres — GitHub odrzuca pliki powyżej 100 MB, a baza rosła o
2,53 MB na każdy skan. Przy bazie zdalnej znika i ten limit, i skutek uboczny
starego rozwiązania: watchlist oraz preferencje przestają znikać przy
redeployu, bo appka zapisuje je do trwałej bazy zamiast do ulotnego pliku.

UWAGA dla appki Streamlit: sekrety trzymane w st.secrets trzeba przepisać do
zmiennych środowiskowych PRZED pierwszym użyciem tego modułu — patrz
_zastosuj_sekrety_streamlit() w app.py. Ten moduł celowo nie importuje
streamlita, bo korzysta z niego również skrypt skanujący uruchamiany
w GitHub Actions, gdzie streamlita nie ma.
"""
from __future__ import annotations

import json
import math
import os
import sqlite3
from datetime import date
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "history.db"

# Rozbite na osobne polecenia, bo executescript() istnieje w sqlite3, ale nie
# jest częścią DB-API i klient libsql go nie udostępnia.
SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS snapshots (
        scan_date TEXT NOT NULL,
        ticker TEXT NOT NULL,
        payload TEXT NOT NULL,
        PRIMARY KEY (scan_date, ticker)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_snapshots_ticker ON snapshots(ticker)",
    "CREATE INDEX IF NOT EXISTS idx_snapshots_date ON snapshots(scan_date)",
    """
    CREATE TABLE IF NOT EXISTS watchlist (
        ticker TEXT PRIMARY KEY,
        note TEXT,
        added_date TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS preferences (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """,
    # Instrumenty dopisane ręcznie przez użytkownika — uniwersum ze składów
    # indeksów zawsze będzie niepełne i zawsze się starzeje.
    #
    # ticker jako KLUCZ GŁÓWNY to nie ozdoba: baza sama odrzuca duplikat,
    # więc nawet gdyby sprawdzenie w interfejsie kiedyś zawiodło, ten sam
    # instrument nie trafi na listę dwa razy.
    """
    CREATE TABLE IF NOT EXISTS wlasne_instrumenty (
        ticker TEXT PRIMARY KEY,
        nazwa TEXT NOT NULL,
        typ TEXT NOT NULL,
        dodano TEXT NOT NULL
    )
    """,
]


def polaczenie_zdalne() -> tuple[str, str] | None:
    """Zwraca (url, token) dla trybu zdalnego albo None, gdy działamy lokalnie."""
    url = os.environ.get("TURSO_DATABASE_URL", "").strip()
    token = os.environ.get("TURSO_AUTH_TOKEN", "").strip()
    return (url, token) if url and token else None


def tryb() -> str:
    """'zdalny' albo 'lokalny' — do pokazania w interfejsie i w logach skanu."""
    return "zdalny" if polaczenie_zdalne() else "lokalny"


def get_conn():
    cfg = polaczenie_zdalne()
    if cfg is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
    else:
        import libsql  # import dopiero tutaj — lokalnie pakiet nie jest potrzebny

        url, token = cfg
        conn = libsql.connect(url, auth_token=token)
    for stmt in SCHEMA_STATEMENTS:
        conn.execute(stmt)
    _zatwierdz(conn)
    return conn


def _zatwierdz(conn) -> None:
    """
    Odpowiednik `with conn:` działający w obu trybach. Menedżer kontekstu
    połączenia to rozszerzenie sqlite3, nie część DB-API — klient libsql go
    nie ma, więc zatwierdzamy jawnie.
    """
    try:
        conn.commit()
    except Exception:  # noqa: BLE001
        pass


def _zamknij(conn) -> None:
    try:
        conn.close()
    except Exception:  # noqa: BLE001
        pass


def _bez_nan(wartosc):
    """
    Zamienia NaN i nieskończoności na None, rekurencyjnie.

    DLACZEGO TO ISTNIEJE: json.dumps domyślnie zapisuje je jako gołe `NaN`
    i `Infinity`. Python odczyta taki tekst z powrotem bez mrugnięcia, ale to
    NIE JEST poprawny JSON — standard tych literałów nie zna. JSON.parse
    w JavaScripcie odrzuca cały dokument.

    Skutek był taki, że frontend widział 9 instrumentów z 1346, a 1337 cicho
    wypadało. Błąd siedział w danych od początku projektu i nie dało się go
    zauważyć, dopóki bazy nie czytał drugi język.
    """
    if isinstance(wartosc, float) and not math.isfinite(wartosc):
        return None
    if isinstance(wartosc, dict):
        return {k: _bez_nan(v) for k, v in wartosc.items()}
    if isinstance(wartosc, (list, tuple)):
        return [_bez_nan(v) for v in wartosc]
    return wartosc


def save_snapshot(scan_date: str, rows: list[dict]) -> None:
    """
    Zapisuje migawkę. Wiersz, którego nie da się zserializować do POPRAWNEGO
    JSON-a, jest pomijany z komunikatem — zamiast wywalać cały skan (co
    kosztowałoby dzień danych) albo, co gorsza, zapisywać tekst, którego
    frontend nie odczyta.
    """
    do_zapisu = []
    pominiete = []
    for r in rows:
        try:
            # allow_nan=False celowo: gdyby sanityzator czegoś nie złapał,
            # chcemy o tym wiedzieć tutaj, a nie zobaczyć brakujące spółki
            # w interfejsie za trzy tygodnie.
            payload = json.dumps(_bez_nan(r), default=str, allow_nan=False)
        except (ValueError, TypeError) as e:
            pominiete.append(f"{r.get('Ticker', '?')} ({e})")
            continue
        do_zapisu.append((scan_date, r["Ticker"], payload))

    if pominiete:
        print(f"⚠️ Pominięto {len(pominiete)} instrumentów przy zapisie: "
              f"{', '.join(pominiete[:5])}{' ...' if len(pominiete) > 5 else ''}")

    conn = get_conn()
    try:
        conn.executemany(
            "INSERT OR REPLACE INTO snapshots (scan_date, ticker, payload) VALUES (?, ?, ?)",
            do_zapisu,
        )
        _zatwierdz(conn)
    finally:
        _zamknij(conn)


def list_dates() -> list[str]:
    conn = get_conn()
    try:
        dates = [r[0] for r in conn.execute(
            "SELECT DISTINCT scan_date FROM snapshots ORDER BY scan_date DESC"
        ).fetchall()]
    finally:
        _zamknij(conn)
    return dates


def load_snapshot(scan_date: str) -> pd.DataFrame:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT payload FROM snapshots WHERE scan_date = ?", (scan_date,)
        ).fetchall()
    finally:
        _zamknij(conn)
    return pd.DataFrame([json.loads(r[0]) for r in rows])


def load_latest() -> pd.DataFrame:
    dates = list_dates()
    if not dates:
        return pd.DataFrame()
    return load_snapshot(dates[0])


def load_ticker_history(ticker: str) -> pd.DataFrame:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT scan_date, payload FROM snapshots WHERE ticker = ? ORDER BY scan_date",
            (ticker,),
        ).fetchall()
    finally:
        _zamknij(conn)
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
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT scan_date, payload FROM snapshots ORDER BY scan_date"
        ).fetchall()
    finally:
        _zamknij(conn)
    records = []
    for scan_date, payload in rows:
        rec = json.loads(payload)
        rec["scan_date"] = scan_date
        records.append(rec)
    return pd.DataFrame(records)


def add_to_watchlist(ticker: str, note: str = "") -> None:
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO watchlist (ticker, note, added_date) VALUES (?, ?, ?) "
            "ON CONFLICT(ticker) DO UPDATE SET note = excluded.note",
            (ticker, note, date.today().isoformat()),
        )
        _zatwierdz(conn)
    finally:
        _zamknij(conn)


def update_watchlist_note(ticker: str, note: str) -> None:
    conn = get_conn()
    try:
        conn.execute("UPDATE watchlist SET note = ? WHERE ticker = ?", (note, ticker))
        _zatwierdz(conn)
    finally:
        _zamknij(conn)


def remove_from_watchlist(ticker: str) -> None:
    conn = get_conn()
    try:
        conn.execute("DELETE FROM watchlist WHERE ticker = ?", (ticker,))
        _zatwierdz(conn)
    finally:
        _zamknij(conn)


def load_watchlist() -> pd.DataFrame:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT ticker, note, added_date FROM watchlist ORDER BY added_date DESC"
        ).fetchall()
    finally:
        _zamknij(conn)
    return pd.DataFrame(rows, columns=["Ticker", "Notatka", "Dodano"])


def get_preference(key: str, default=None):
    conn = get_conn()
    try:
        row = conn.execute("SELECT value FROM preferences WHERE key = ?", (key,)).fetchone()
    finally:
        _zamknij(conn)
    if row is None:
        return default
    try:
        return json.loads(row[0])
    except Exception:  # noqa: BLE001
        return default


def set_preference(key: str, value) -> None:
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO preferences (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, json.dumps(value)),
        )
        _zatwierdz(conn)
    finally:
        _zamknij(conn)


def delete_preference(key: str) -> None:
    conn = get_conn()
    try:
        conn.execute("DELETE FROM preferences WHERE key = ?", (key,))
        _zatwierdz(conn)
    finally:
        _zamknij(conn)


# =============================================================================
# WŁASNE INSTRUMENTY
#
# Uniwersum budowane ze składów indeksów zawsze będzie niepełne: XTB oferuje
# ~1900 ETF-ów, a my mamy 69; nowe spółki wchodzą na giełdę, stare zmieniają
# nazwy. Ta lista pozwala dopisać instrument bez ruszania kodu — trafia do
# skanu następnego dnia razem z resztą.
# =============================================================================

TYPY_INSTRUMENTOW = ("stock", "etf", "index")


def dodaj_wlasny(ticker: str, nazwa: str, typ: str) -> bool:
    """
    Dopisuje instrument. Zwraca False, gdy już istnieje — świadomie NIE
    nadpisujemy, bo to znaczyłoby ciche zastąpienie nazwy albo typu wpisanego
    wcześniej przez użytkownika.
    """
    ticker = ticker.strip().upper()
    if not ticker or typ not in TYPY_INSTRUMENTOW:
        return False

    conn = get_conn()
    try:
        istnieje = conn.execute(
            "SELECT 1 FROM wlasne_instrumenty WHERE ticker = ?", (ticker,)
        ).fetchone()
        if istnieje:
            return False
        conn.execute(
            "INSERT INTO wlasne_instrumenty (ticker, nazwa, typ, dodano) VALUES (?, ?, ?, ?)",
            (ticker, nazwa.strip() or ticker, typ, date.today().isoformat()),
        )
        _zatwierdz(conn)
        return True
    finally:
        _zamknij(conn)


def usun_wlasny(ticker: str) -> None:
    conn = get_conn()
    try:
        conn.execute(
            "DELETE FROM wlasne_instrumenty WHERE ticker = ?", (ticker.strip().upper(),)
        )
        _zatwierdz(conn)
    finally:
        _zamknij(conn)


def wlasne_instrumenty() -> list[dict]:
    """Lista dopisanych instrumentów, od najnowszego."""
    conn = get_conn()
    try:
        wiersze = conn.execute(
            "SELECT ticker, nazwa, typ, dodano FROM wlasne_instrumenty "
            "ORDER BY dodano DESC, ticker"
        ).fetchall()
    finally:
        _zamknij(conn)
    return [
        {"ticker": w[0], "nazwa": w[1], "typ": w[2], "dodano": w[3]} for w in wiersze
    ]


def wlasne_wg_typu(typ: str) -> dict[str, str]:
    """Mapa {ticker: nazwa} dla jednego typu — w formacie, którego oczekuje skan."""
    return {i["ticker"]: i["nazwa"] for i in wlasne_instrumenty() if i["typ"] == typ}
