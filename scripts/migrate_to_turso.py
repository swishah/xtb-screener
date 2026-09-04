"""
Jednorazowa migracja: lokalny plik data/history.db  ->  baza zdalna (Turso).

URUCHOMIENIE (z katalogu projektu, po ustawieniu sekretów):

    set TURSO_DATABASE_URL=libsql://twoja-baza.turso.io
    set TURSO_AUTH_TOKEN=...
    python scripts/migrate_to_turso.py

Skrypt jest BEZPIECZNY do wielokrotnego uruchomienia: zapis idzie przez
INSERT OR REPLACE po kluczu (scan_date, ticker), więc powtórzenie migracji
nadpisze te same wiersze zamiast je zdublować. Pliku lokalnego NIE kasuje
ani nie modyfikuje — zostaje jako kopia zapasowa.

Na końcu porównuje liczbę wierszy po obu stronach i mówi wprost, czy się
zgadza. Bez tej kontroli migracja "wygląda na udaną" nawet gdy część danych
nie dojechała.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.db import DB_PATH, SCHEMA_STATEMENTS, polaczenie_zdalne  # noqa: E402

PACZKA = 500  # wierszy na jedną transakcję — kompromis między szybkością a pamięcią


def main() -> int:
    cfg = polaczenie_zdalne()
    if cfg is None:
        print("BŁĄD: brak TURSO_DATABASE_URL / TURSO_AUTH_TOKEN w zmiennych środowiskowych.")
        print("      Bez nich nie ma dokąd migrować — ustaw je i uruchom ponownie.")
        return 1

    if not DB_PATH.exists():
        print(f"BŁĄD: nie znaleziono lokalnej bazy {DB_PATH}")
        return 1

    import libsql

    url, token = cfg
    zrodlo = sqlite3.connect(DB_PATH)
    cel = libsql.connect(url, auth_token=token)

    print(f"Źródło: {DB_PATH}")
    print(f"Cel:    {url}\n")

    for stmt in SCHEMA_STATEMENTS:
        cel.execute(stmt)
    cel.commit()
    print("Schemat utworzony.\n")

    razem = 0
    for tabela, kolumny in (
        ("snapshots", ("scan_date", "ticker", "payload")),
        ("watchlist", ("ticker", "note", "added_date")),
        ("preferences", ("key", "value")),
    ):
        ile = zrodlo.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]
        if ile == 0:
            print(f"  {tabela}: pusto, pomijam")
            continue

        pola = ", ".join(kolumny)
        znaki = ", ".join("?" * len(kolumny))
        sql = f"INSERT OR REPLACE INTO {tabela} ({pola}) VALUES ({znaki})"

        kursor = zrodlo.execute(f"SELECT {pola} FROM {tabela}")
        przeniesione = 0
        while True:
            paczka = kursor.fetchmany(PACZKA)
            if not paczka:
                break
            cel.executemany(sql, paczka)
            cel.commit()
            przeniesione += len(paczka)
            print(f"  {tabela}: {przeniesione}/{ile}", end="\r", flush=True)
        print(f"  {tabela}: {przeniesione}/{ile}   ")
        razem += przeniesione

    print(f"\nPrzeniesiono {razem} wierszy. Sprawdzam zgodność...\n")

    zgadza_sie = True
    for tabela in ("snapshots", "watchlist", "preferences"):
        a = zrodlo.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]
        b = cel.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]
        status = "OK" if a == b else "NIEZGODNOŚĆ"
        if a != b:
            zgadza_sie = False
        print(f"  {tabela:<12} lokalnie: {a:>6}   zdalnie: {b:>6}   {status}")

    # Dodatkowa kontrola: liczba migawek musi się zgadzać co do jednej,
    # bo to od niej zależą backtesty.
    da = len(zrodlo.execute("SELECT DISTINCT scan_date FROM snapshots").fetchall())
    db_ = len(cel.execute("SELECT DISTINCT scan_date FROM snapshots").fetchall())
    print(f"  {'migawek':<12} lokalnie: {da:>6}   zdalnie: {db_:>6}   "
          f"{'OK' if da == db_ else 'NIEZGODNOŚĆ'}")
    if da != db_:
        zgadza_sie = False

    zrodlo.close()
    try:
        cel.close()
    except Exception:  # noqa: BLE001
        pass

    if zgadza_sie:
        print("\nMigracja zakończona poprawnie. Plik lokalny zostaje nietknięty jako kopia.")
        return 0
    print("\nUWAGA: liczby się nie zgadzają — NIE usuwaj lokalnej bazy.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
