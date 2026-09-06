"""
Ręczne ustawienie hasła użytkownika — awaryjne wejście do aplikacji.

PO CO TO ISTNIEJE: reset hasła przez e-mail wymaga skonfigurowanego SMTP.
Dopóki go nie ma, zapomniane hasło oznaczałoby brak jakiejkolwiek drogi
powrotu — aplikacja jest w całości za logowaniem. Ten skrypt jest tą drogą.

Uruchamiasz go u siebie na komputerze, z tymi samymi zmiennymi TURSO_*, co
produkcja. Hasło podajesz w ukrytym pytaniu, NIE w argumencie polecenia —
argumenty zostają w historii powłoki i w liście procesów.

    python scripts/ustaw_haslo.py --email ktos@example.com

ZGODNOŚĆ Z FRONTENDEM: format zapisu hasła musi się zgadzać co do znaku
z tym, co robi `frontend/lib/konta.ts`, czyli "scrypt$N$r$p$sól$klucz",
z solą i kluczem w base64, po normalizacji hasła do NFKC. Zgodność jest
sprawdzana testem, który liczy skrót tutaj i weryfikuje go w Node —
patrz opis w CLAUDE.md.
"""
from __future__ import annotations

import argparse
import base64
import getpass
import hashlib
import os
import sys
import unicodedata
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import db  # noqa: E402

# Te same parametry co w lib/konta.ts. Gdyby kiedyś tam wzrosły, tu też muszą.
SCRYPT_N = 16384
SCRYPT_R = 8
SCRYPT_P = 1
DLUGOSC_KLUCZA = 64
MIN_DLUGOSC_HASLA = 10

# Tabela należy do frontendu, ale skrypt musi działać także wtedy, gdy nikt
# jeszcze nie otworzył strony logowania.
TABELA_UZYTKOWNICY = """
CREATE TABLE IF NOT EXISTS uzytkownicy (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    haslo TEXT NOT NULL,
    utworzony TEXT NOT NULL,
    nieudane_proby INTEGER NOT NULL DEFAULT 0,
    zablokowany_do TEXT
)
"""


def zahashuj(haslo: str) -> str:
    """Dokładnie ten sam format co `zahashuj()` w lib/konta.ts."""
    sol = os.urandom(16)
    klucz = hashlib.scrypt(
        unicodedata.normalize("NFKC", haslo).encode("utf-8"),
        salt=sol,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=DLUGOSC_KLUCZA,
        maxmem=128 * SCRYPT_N * SCRYPT_R * 2,
    )
    return "$".join([
        "scrypt",
        str(SCRYPT_N),
        str(SCRYPT_R),
        str(SCRYPT_P),
        base64.b64encode(sol).decode(),
        base64.b64encode(klucz).decode(),
    ])


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ustawia hasło użytkownika aplikacji (wejście awaryjne)."
    )
    parser.add_argument("--email", required=True, help="adres konta")
    parser.add_argument(
        "--utworz",
        action="store_true",
        help="załóż konto, jeśli jeszcze nie istnieje",
    )
    args = parser.parse_args()

    email = args.email.strip().lower()
    print(f"Tryb bazy: {db.tryb()}")
    if db.tryb() == "lokalny":
        print("UWAGA: piszesz do LOKALNEJ kopii bazy, nie do produkcji.")
        print("Ustaw TURSO_DATABASE_URL i TURSO_AUTH_TOKEN, jeśli chodziło o produkcję.")
        if input("Kontynuować mimo to? [tak/nie] ").strip().lower() != "tak":
            return 1

    haslo = getpass.getpass("Nowe hasło (nie będzie widoczne): ")
    if len(haslo) < MIN_DLUGOSC_HASLA:
        print(f"Hasło musi mieć co najmniej {MIN_DLUGOSC_HASLA} znaków.")
        return 1
    if haslo != getpass.getpass("Powtórz hasło: "):
        print("Hasła nie są takie same.")
        return 1

    conn = db.get_conn()
    try:
        conn.execute(TABELA_UZYTKOWNICY)
        kursor = conn.execute(
            "SELECT id FROM uzytkownicy WHERE email = ?", (email,)
        )
        wiersz = kursor.fetchone()

        if wiersz is None:
            if not args.utworz:
                print(f"Nie ma konta o adresie {email}.")
                print("Dodaj --utworz, jeśli chcesz je założyć.")
                return 1
            conn.execute(
                "INSERT INTO uzytkownicy (email, haslo, utworzony) VALUES (?, ?, ?)",
                (email, zahashuj(haslo), datetime.now(timezone.utc).isoformat()),
            )
            print(f"Założono konto {email} i ustawiono hasło.")
        else:
            conn.execute(
                "UPDATE uzytkownicy SET haslo = ?, nieudane_proby = 0, "
                "zablokowany_do = NULL WHERE email = ?",
                (zahashuj(haslo), email),
            )
            print(f"Ustawiono nowe hasło dla {email}.")
            print("Odblokowano też konto, gdyby było zablokowane po nieudanych próbach.")

        # Tak samo jak zmiana hasła w aplikacji: wszystkie urządzenia lecą
        # z sesji. Gdyby ktoś obcy miał ważną sesję, samo hasło by go nie usunęło.
        try:
            conn.execute(
                "DELETE FROM sesje WHERE uzytkownik_id = "
                "(SELECT id FROM uzytkownicy WHERE email = ?)",
                (email,),
            )
            print("Wylogowano wszystkie urządzenia tego konta.")
        except Exception:  # noqa: BLE001
            # Tabela sesji powstaje przy pierwszym logowaniu — jej brak
            # to normalny stan, nie błąd.
            pass

        db._zatwierdz(conn)
    finally:
        db._zamknij(conn)

    print("Gotowe. Zaloguj się nowym hasłem.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
