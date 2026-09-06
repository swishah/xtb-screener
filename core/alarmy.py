"""
Sprawdzanie alarmów cenowych podczas codziennego skanu.

PODZIAŁ ODPOWIEDZIALNOŚCI: tabelę `alarmy` zakłada i wypełnia FRONTEND
(`frontend/lib/alarmy.ts`) — tam użytkownik przeciąga linię po wykresie.
Python tę tabelę tylko czyta i oznacza wyzwolone wpisy. Dlatego brak tabeli
NIE jest błędem: znaczy tyle, że nikt jeszcze nie ustawił żadnego alarmu.

DLACZEGO MAKSIMUM I MINIMUM DNIA, A NIE ZAMKNIĘCIE. Skan chodzi raz na dobę,
więc porównywanie z ceną zamknięcia gubiłoby każde przebicie progu, które
w ciągu dnia się cofnęło — a to często właśnie ten moment, o którym chce się
wiedzieć. Skan i tak pobiera pełne OHLC, więc sprawdzenie ekstremów sesji nic
nie kosztuje.

CZEGO TO NIE ZASTĘPUJE: alertu w czasie rzeczywistym. O przebiciu dowiesz się
wieczorem po skanie, nie w sekundzie, w której nastąpiło.
"""
from __future__ import annotations

from datetime import date


def _liczba(wartosc):
    if wartosc is None or isinstance(wartosc, str):
        return None
    try:
        f = float(wartosc)
    except (TypeError, ValueError):
        return None
    return None if f != f else f


def _zakres_sesji(wiersz: dict) -> tuple[float | None, float | None]:
    """
    Maksimum i minimum ostatniej sesji, z zapasowym wariantem na cenę.

    Starsze migawki nie mają tych kolumn, a niektóre instrumenty potrafią nie
    mieć ich nigdy. Wtedy zostaje sama cena — alarm dalej działa, tylko łapie
    wyłącznie przebicia widoczne na zamknięciu.
    """
    maks = _liczba(wiersz.get("Maksimum dnia"))
    mini = _liczba(wiersz.get("Minimum dnia"))
    cena = _liczba(wiersz.get("Cena"))
    if maks is None:
        maks = cena
    if mini is None:
        mini = cena
    return maks, mini


def sprawdz(rows: list[dict], conn) -> list[dict]:
    """
    Oznacza wyzwolone alarmy i zwraca ich opis do powiadomienia.

    `conn` to otwarte połączenie z bazą (z core.db.get_conn), żeby nie
    otwierać drugiego. Zwraca listę słowników opisujących to, co zadziałało.
    """
    try:
        kursor = conn.execute(
            "SELECT id, uzytkownik_id, ticker, nazwa, kierunek, cena, waluta "
            "FROM alarmy WHERE wyzwolony IS NULL"
        )
        czekajace = kursor.fetchall()
    except Exception:  # noqa: BLE001
        # Tabela powstaje dopiero przy pierwszym alarmie ustawionym w appce.
        print("ℹ️ Alarmy: brak tabeli albo brak alarmów — pomijam.")
        return []

    if not czekajace:
        print("ℹ️ Alarmy: nic nie czeka na sprawdzenie.")
        return []

    wg_tickera: dict[str, dict] = {str(r.get("Ticker", "")): r for r in rows}
    dzis = date.today().isoformat()
    wyzwolone: list[dict] = []

    for wiersz in czekajace:
        # Wiersze bywają krotkami albo obiektami z indeksowaniem po nazwie,
        # zależnie od trybu bazy — bierzemy po pozycji, bo to działa w obu.
        (id_alarmu, uzytkownik_id, ticker, nazwa, kierunek, prog, waluta) = (
            wiersz[0], wiersz[1], wiersz[2], wiersz[3], wiersz[4], wiersz[5], wiersz[6]
        )
        dane = wg_tickera.get(str(ticker))
        if not dane:
            continue

        maks, mini = _zakres_sesji(dane)
        prog = _liczba(prog)
        if prog is None:
            continue

        trafienie = None
        if kierunek == "powyzej" and maks is not None and maks >= prog:
            trafienie = maks
        elif kierunek == "ponizej" and mini is not None and mini <= prog:
            trafienie = mini
        if trafienie is None:
            continue

        conn.execute(
            "UPDATE alarmy SET wyzwolony = ?, cena_wyzwolenia = ? WHERE id = ?",
            (dzis, round(float(trafienie), 4), id_alarmu),
        )
        wyzwolone.append({
            "uzytkownik_id": uzytkownik_id,
            "ticker": str(ticker),
            "nazwa": str(nazwa or ""),
            "kierunek": str(kierunek),
            "prog": prog,
            "cena": float(trafienie),
            "waluta": str(waluta or ""),
        })

    print(f"🔔 Alarmy: sprawdzono {len(czekajace)}, zadziałało {len(wyzwolone)}.")
    return wyzwolone


def opis(wyzwolone: list[dict]) -> str:
    """Treść powiadomienia. Pusty string, gdy nie ma o czym powiadamiać."""
    if not wyzwolone:
        return ""
    linie = ["🔔 Alarmy cenowe — zadziałały:"]
    for a in wyzwolone:
        strzalka = "wzrost powyżej" if a["kierunek"] == "powyzej" else "spadek poniżej"
        linie.append(
            f"• {a['ticker']} ({a['nazwa']}): {strzalka} {a['prog']:.2f} "
            f"{a['waluta']} — sesja sięgnęła {a['cena']:.2f}"
        )
    linie.append("")
    linie.append("Szczegóły i wznowienie alarmów: zakładka „Alarmy cenowe” w aplikacji.")
    return "\n".join(linie)
